import asyncio
import json
import sys
from dataclass, fieldes import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from config.settings import get_settings
from routers.cascade import get_all_router_states, JobState

settings = get_settings()


class DispatchTarget(Enum):
    WEB_SCRAPE = "web_scrape"
    SOCKET = "socket"


@dataclass
class AssetIdentificationJob:
    job_id: str
    serial_number: str
    target_type: DispatchTarget
    target_endpoint: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class DispatcherError(Exception):
    pass


class JobDispatcher:
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or settings.MAX_CONCURRENT_TASKS
        self.semaphore = asyncio.Semaphore(self.max_workers)
        self._active_tasks: Dict[str, asyncio.Task] = {}

    def get_active_router_states(self) -> Dict[str, Any]:
        return get_all_router_states()

    def get_processing_count(self) -> int:
        states = self.get_active_router_states()
        return sum(1 for state in states.values() if state.state == JobState.PROCESSING)

    def can_dispatch(self) -> bool:
        return self.get_processing_count() < self.max_workers

    async def dispatch_batch(self, jobs: List[AssetIdentificationJob]) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        created_tasks: Dict[str, asyncio.Task[Any]] = {}

        async with asyncio.TaskGroup() as tg:
            for job in jobs:
                created_tasks[job.job_id] = tg.create_task(self._dispatch_job(job), name=job.job_id)

        for job_id, task in created_tasks.items():
            results[job_id] = task.result()

        return results

    async def _dispatch_job(self, job: AssetIdentificationJob) -> Any:
        async with self.semaphore:
            self._active_tasks[job.job_id] = asyncio.current_task()
            current_states = self.get_active_router_states()
            print(f"DISPATCHER: Routing {job.job_id} ({job.target_type.value}) with {len(current_states)} active router states")
            try:
                if job.target_type == DispatchTarget.WEB_SCRAPE:
                    return await self._route_to_web_scrape(job)
                if job.target_type == DispatchTarget.SOCKET:
                    return await self._route_to_socket(job)
                raise DispatcherError(f"Unknown target type: {job.target_type}")
            finally:
                self._active_tasks.pop(job.job_id, None)

    async def _route_to_web_scrape(self, job: AssetIdentificationJob) -> Any:
        print(f"DISPATCHER: Job {job.job_id} selected web scraping pipeline")
        try:
            import importlib
            integrate = importlib.import_module("protocols.integrate_init_001")
            return await integrate.run_integrated_execution_pipeline()
        except ImportError as exc:
            fallback_message = f"mock-web-scrape-result-{job.job_id}"
            print(
                f"DISPATCHER: Integrate pipeline unavailable, using fallback for {job.job_id}: {exc}",
                file=sys.stderr,
            )
            return fallback_message

    async def _route_to_socket(self, job: AssetIdentificationJob) -> str:
        host, port = self._parse_socket_endpoint(job.target_endpoint)
        print(f"DISPATCHER: Job {job.job_id} selected socket pipeline to {host}:{port}")
        try:
            reader, writer = await asyncio.open_connection(host, port)
            payload = json.dumps({
                "job_id": job.job_id,
                "serial_number": job.serial_number,
                "metadata": job.metadata or {},
            })
            writer.write(payload.encode("utf-8") + b"\n")
            await writer.drain()
            response = await reader.read(4096)
            writer.close()
            await writer.wait_closed()
            return response.decode("utf-8").strip()
        except Exception as exc:
            raise DispatcherError(f"Socket dispatch failed for {job.job_id}: {exc}") from exc

    def _parse_socket_endpoint(self, endpoint: str) -> Tuple[str, int]:
        if ":" in endpoint:
            host, port_str = endpoint.split(":", 1)
            return host, int(port_str)
        raise DispatcherError(f"Invalid socket endpoint: {endpoint}")


def create_default_dispatcher() -> JobDispatcher:
    return JobDispatcher(max_workers=settings.MAX_CONCURRENT_TASKS)
