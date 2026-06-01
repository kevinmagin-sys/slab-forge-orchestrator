# run_trial.py
import asyncio
import json
import uuid
import threading
from sqlalchemy import Table, Column, String, MetaData
from config.database import engine
from protocols.slab_002 import process_vision_payload
from protocols.slab_005 import persist_asset_allocation
from routers.cascade import get_all_router_states, router_job_registry
from routers.dispatcher import AssetIdentificationJob, DispatchTarget, JobDispatcher

# Start the global telemetry consumer so telemetry_queue events emitted by
# network/protocol modules are processed by the central writer.
try:
    from protocols.deploy_init_002 import background_logging_consumer
except Exception:
    background_logging_consumer = None

# 1. Initialize Database Schema for the Trial
metadata = MetaData()
surplus_assets = Table(
    "surplus_assets",
    metadata,
    Column("id", String, primary_key=True),
    Column("status", String),
    Column("assigned_pipeline", String),
    Column("updated_at", String)
)

def setup_mock_db(asset_id_str):
    metadata.create_all(engine)
    # Use a transactional engine.begin() context so the insert is committed
    with engine.begin() as conn:
        conn.execute(
            surplus_assets.insert().values(
                id=asset_id_str,
                status="UNALLOCATED",
                assigned_pipeline="NONE",
                updated_at="INIT"
            )
        )


async def execute_trial():
    print("--- Starting Application Trial ---\n")
    
    # Generate a deterministic ID for tracking
    test_asset_id = uuid.uuid4()
    setup_mock_db(str(test_asset_id))
    print(f"[DB LOG] Initialized mock asset record with ID: {test_asset_id}")

    # Simulate an incoming payload from an industrial camera step (SLAB-002)
    mock_vision_payload = json.dumps({
        "serial_number": "SN-98432-X",
        "part_status": "SURPLUS",
        "dimensions": "12x8x4",
        "confidence_score": 0.92
    })
    
    print("\n[STEP 1] Processing incoming Vision Payload...")
    vision_status = process_vision_payload(mock_vision_payload)
    print(f"[RESULT] Vision Verification Status: {vision_status}")

    # Simulate routing and committing the asset status to storage (SLAB-005)
    print("\n[STEP 2] Attempting secure row-level database allocation...")
    try:
        persist_asset_allocation(
            asset_id=str(test_asset_id), 
            new_status="ALLOCATED", 
            target_pipeline="ROUTE_TO_INVENTORY"
        )
        print("[RESULT] Database transaction successfully committed.")
    except Exception as e:
        print(f"[ERROR] Transaction failed: {e}")

    print("\n[STEP 3] Routing mixed batch jobs through centralized dispatcher...")

    # Reset any prior state registry entries for a clean batch run.
    router_job_registry.clear()

    dispatcher = JobDispatcher(max_workers=3)

    async def echo_socket_handler(reader, writer):
        data = await reader.readline()
        writer.write(b"SOCKET_ACK\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(echo_socket_handler, "127.0.0.1", 0)
    listen_host, listen_port = server.sockets[0].getsockname()
    print(f"DISPATCHER: Local socket target listening on {(listen_host, listen_port)}")

    job_batch = [
        AssetIdentificationJob(
            job_id="job-001",
            serial_number="SN-001",
            target_type=DispatchTarget.WEB_SCRAPE,
            target_endpoint="http://localhost:8080/target_dashboard",
        ),
        AssetIdentificationJob(
            job_id="job-002",
            serial_number="SN-002",
            target_type=DispatchTarget.SOCKET,
            target_endpoint=f"{listen_host}:{listen_port}",
        ),
        AssetIdentificationJob(
            job_id="job-003",
            serial_number="SN-003",
            target_type=DispatchTarget.WEB_SCRAPE,
            target_endpoint="http://localhost:8080/target_dashboard",
        ),
        AssetIdentificationJob(
            job_id="job-004",
            serial_number="SN-004",
            target_type=DispatchTarget.SOCKET,
            target_endpoint=f"{listen_host}:{listen_port}",
        ),
        AssetIdentificationJob(
            job_id="job-005",
            serial_number="SN-005",
            target_type=DispatchTarget.SOCKET,
            target_endpoint=f"{listen_host}:{listen_port}",
        ),
    ]

    async with server:
        dispatch_results = await dispatcher.dispatch_batch(job_batch)

    print("\n[STEP 4] Dispatcher batch results:")
    for job_id, result in dispatch_results.items():
        print(f" - {job_id}: {result}")

    print("\n[STEP 5] Consolidated dispatcher state summary:")
    final_states = get_all_router_states()

    completed = []
    failed = []
    for job_id, state in final_states.items():
        if state.state == state.state.COMPLETED:
            completed.append(job_id)
        else:
            failed.append(job_id)
        print(f" - {job_id}: {state.state.value} (retries={state.retries}, last_error={state.last_error})")

    print("\nSummary:")
    print(f"  COMPLETED: {len(completed)}")
    print(f"  FAILED: {len(failed)}")

    print("\n--- Trial Execution Completed Successfully ---")


if __name__ == "__main__":
    # Spin up the global telemetry consumer in a daemon thread (if available).
    if background_logging_consumer is not None:
        t = threading.Thread(target=background_logging_consumer, daemon=True)
        t.start()

    asyncio.run(execute_trial())
