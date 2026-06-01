import asyncio
import sys
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

try:
    from pydantic import BaseModel
except ImportError:
    class BaseModel:
        pass

from config.settings import get_settings

settings = get_settings()

# Mock definitions for Type hints and Downstream pipeline systems
class PydanticModel(BaseModel):
    job_id: Optional[str] = None


async def call_primary_broker_api(payload: PydanticModel):
    """Mock async function to invoke the primary broker."""
    pass


async def call_secondary_broker_api(payload: PydanticModel):
    """Mock async function to invoke the redundant broker."""
    pass


def trigger_dead_letter_queue(payload: PydanticModel):
    """Mock system interface for dead letter routing on hard failures."""
    pass


class JobState(Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class RouterJobState:
    job_id: str
    state: JobState = JobState.PENDING
    retries: int = 0
    last_error: Optional[str] = None
    result: Optional[Any] = None


router_job_registry: Dict[str, RouterJobState] = {}
router_job_registry_lock = threading.Lock()


def _get_job_id(payload: PydanticModel) -> str:
    if hasattr(payload, "job_id") and payload.job_id:
        return str(payload.job_id)
    if hasattr(payload, "id") and getattr(payload, "id") is not None:
        return str(getattr(payload, "id"))
    return str(id(payload))


def get_router_job_state(payload: PydanticModel) -> RouterJobState:
    job_id = _get_job_id(payload)
    with router_job_registry_lock:
        if job_id not in router_job_registry:
            router_job_registry[job_id] = RouterJobState(job_id=job_id)
        return router_job_registry[job_id]


def update_router_job_state(
    payload: PydanticModel,
    state: JobState,
    retries: Optional[int] = None,
    error: Optional[BaseException] = None,
    result: Optional[Any] = None,
) -> RouterJobState:
    job_state = get_router_job_state(payload)
    with router_job_registry_lock:
        job_state.state = state
        if retries is not None:
            job_state.retries = retries
        if error is not None:
            job_state.last_error = str(error)
        if result is not None:
            job_state.result = result
    return job_state


def get_all_router_states() -> Dict[str, RouterJobState]:
    with router_job_registry_lock:
        return {k: v for k, v in router_job_registry.items()}


# SET PRIMARY_TIMEOUT = 2.5 // Seconds
PRIMARY_TIMEOUT = settings.PRIMARY_TIMEOUT
# SET FALLBACK_TIMEOUT = 4.0
FALLBACK_TIMEOUT = settings.FALLBACK_TIMEOUT
# SET MAX_CONCURRENT_TASKS = 50
MAX_CONCURRENT_TASKS = settings.MAX_CONCURRENT_TASKS
# SET Semaphore = NEW asyncio.Semaphore(MAX_CONCURRENT_TASKS)
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)


async def _execute_with_retry(
    request_fn,
    payload: PydanticModel,
    timeout: float,
    max_attempts: int = 3,
) -> Any:
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        update_router_job_state(payload, JobState.PROCESSING, retries=attempt)
        try:
            return await asyncio.wait_for(request_fn(), timeout=timeout)
        except (asyncio.TimeoutError, ConnectionError) as exc:
            update_router_job_state(payload, JobState.PROCESSING, retries=attempt, error=exc)
            if attempt >= max_attempts:
                raise
            backoff_seconds = 2 ** (attempt - 1)
            print(
                f"WARNING: Attempt {attempt} failed for job {_get_job_id(payload)}; retrying in {backoff_seconds}s.",
                file=sys.stderr,
            )
            await asyncio.sleep(backoff_seconds)


# ASYNC FUNCTION ExecuteCascadeRouter(TargetPayload: PydanticModel):
async def execute_cascade_router(target_payload: PydanticModel):
    update_router_job_state(target_payload, JobState.PENDING)
    job_state = get_router_job_state(target_payload)

    # ACQUIRE Semaphore:
    async with semaphore:
        update_router_job_state(target_payload, JobState.PROCESSING)
        # TRY:
        try:
            # // Route A: Primary Optimized Target
            # SET Result = AWAIT asyncio.wait_for(CallPrimaryBrokerAPI(TargetPayload), timeout=PRIMARY_TIMEOUT)
            result = await _execute_with_retry(
                lambda: call_primary_broker_api(target_payload),
                target_payload,
                PRIMARY_TIMEOUT,
            )
            # EMIT ROUTER_SIGNAL "PRIMARY_ROUTE_SUCCESS"
            print("ROUTER_SIGNAL: PRIMARY_ROUTE_SUCCESS")
            update_router_job_state(target_payload, JobState.COMPLETED, result=result)
            # RETURN Result
            return result

        # CATCH AsyncioTimeoutException, ConnectionError:
        except (asyncio.TimeoutError, ConnectionError) as exc:
            # EMIT WARNING "Primary route failed or timed out. Initiating Cascade Fallback."
            print(
                "WARNING: Primary route failed or timed out. Initiating Cascade Fallback.",
                file=sys.stderr,
            )
            job_state.last_error = str(exc)
            return await execute_secondary_fallback(target_payload)

        # CATCH Exception AS FatalError:
        except Exception as fatal_error:
            # EMIT CRITICAL "Uncaught execution fault in Primary Route" WITH FatalError
            print(
                f"CRITICAL: Uncaught execution fault in Primary Route. Error: {fatal_error}",
                file=sys.stderr,
            )
            update_router_job_state(target_payload, JobState.FAILED, error=fatal_error)
            # RAISE FatalError
            raise fatal_error
    # END ACQUIRE


# ASYNC FUNCTION ExecuteSecondaryFallback(TargetPayload: PydanticModel):
async def execute_secondary_fallback(target_payload: PydanticModel):
    # TRY:
    try:
        # // Route B: Redundant/Secondary Broker
        # SET Result = AWAIT asyncio.wait_for(CallSecondaryBrokerAPI(TargetPayload), timeout=FALLBACK_TIMEOUT)
        result = await _execute_with_retry(
            lambda: call_secondary_broker_api(target_payload),
            target_payload,
            FALLBACK_TIMEOUT,
        )
        # EMIT ROUTER_SIGNAL "FALLBACK_ROUTE_SUCCESS"
        print("ROUTER_SIGNAL: FALLBACK_ROUTE_SUCCESS")
        update_router_job_state(target_payload, JobState.COMPLETED, result=result)
        # RETURN Result
        return result

    # CATCH Exception AS FallbackError:
    except Exception as fallback_error:
        # EMIT CRITICAL "All cascading routes exhausted. Hard failure state reached." WITH FallbackError
        print(
            f"CRITICAL: All cascading routes exhausted. Hard failure state reached. Error: {fallback_error}",
            file=sys.stderr,
        )
        update_router_job_state(target_payload, JobState.FAILED, error=fallback_error)
        # CALL TriggerDeadLetterQueue(TargetPayload)
        trigger_dead_letter_queue(target_payload)
        # RETURN NULL
        return None


# STATUS = "Verified"
status = "Verified"
