# run_trial.py
import asyncio
import json
import uuid
from sqlalchemy import Table, Column, String, MetaData
from config.database import engine
from protocols.slab_002 import process_vision_payload
from protocols.slab_005 import persist_asset_allocation

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
    with engine.connect() as conn:
        # Insert a mock asset record in an "UNALLOCATED" state
        conn.execute(
            surplus_assets.insert().values(
                id=asset_id_str,
                status="UNALLOCATED",
                assigned_pipeline="NONE",
                updated_at="INIT"
            )
        )
        conn.commit()

# 2. Run the Core Trial Pipeline
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

    print("\n--- Trial Execution Completed Successfully ---")

if __name__ == "__main__":
    asyncio.run(execute_trial())
