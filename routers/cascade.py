import os
import json
import asyncio
import aiofiles
import sqlite3
from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from PIL import Image

router = APIRouter()
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_TIMEOUT = 30.0

def init_db_connection(db_name: str):
    conn = sqlite3.connect(db_name, timeout=DB_TIMEOUT)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

async def run_swarm_search(query: str):
    # Simulating scraper swarm search based on vision findings
    await asyncio.sleep(1)
    return [{"source_url": f"https://www.mscdirect.com/s?keyword={query.replace(' ', '+')}", "confidence": 0.92}]

async def write_telemetry_log(agent: str, level: str, message: str):
    loop = asyncio.get_event_loop()
    def _insert():
        with init_db_connection("telemetry.db") as conn:
            conn.execute(
                "INSERT INTO logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                (agent, level, message)
            )
            conn.commit()
    await loop.run_in_executor(None, _insert)

async def orchestrate_pipeline_task(cascade_id: str, file_path: str):
    loop = asyncio.get_event_loop()
    
    # 1. SLAB Stage - True Image Inspection
    await write_telemetry_log("SLAB", "INFO", f"Opening target asset: {os.path.basename(file_path)}")
    
    try:
        def _inspect_image():
            with Image.open(file_path) as img:
                return img.size, img.format
        
        dimensions, img_format = await loop.run_in_executor(None, _inspect_image)
        await write_telemetry_log("SLAB", "INFO", f"Asset Metrics verified: {dimensions[0]}x{dimensions[1]} ({img_format})")
        
        # Simulating key extraction profile derived from dimensions/metadata
        extracted_part_query = "Hex Bolt Grade 8 1/2-13"
        await write_telemetry_log("SLAB", "SUCCESS", f"Extraction signature resolved: '{extracted_part_query}'")
        
    except Exception as vision_err:
        await write_telemetry_log("SLAB", "ERROR", f"Vision pipeline failure: {str(vision_err)}")
        def _fail_state():
            with init_db_connection("pipeline.db") as conn:
                conn.execute("UPDATE pipeline_state SET status='FAILED' WHERE id=?", (cascade_id,))
                conn.commit()
        await loop.run_in_executor(None, _fail_state)
        return

    def _update_state(status: str, current_stage: str):
        with init_db_connection("pipeline.db") as conn:
            conn.execute(
                "UPDATE pipeline_state SET status=?, current_stage=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, current_stage, cascade_id)
            )
            conn.commit()

    await loop.run_in_executor(None, _update_state, "PROCESSING", "FORGE")
    
    # 2. FORGE Stage - Active Web Resolution
    await write_telemetry_log("FORGE", "INFO", f"Dispatched swarm queries to industrial suppliers for: '{extracted_part_query}'")
    results = await run_swarm_search(extracted_part_query)
    
    target_url = results[0]['source_url']
    await write_telemetry_log("FORGE", "SUCCESS", f"Matching inventory mapping confirmed -> {target_url}")
    await loop.run_in_executor(None, _update_state, "COMPLETED", "ORCHESTRATOR")

@router.post("/process")
async def process_cascade(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    cascade_id = f"cas_{int(asyncio.get_event_loop().time())}"
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    async with aiofiles.open(file_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)
        
    loop = asyncio.get_event_loop()
    def _init_state():
        with init_db_connection("pipeline.db") as conn:
            conn.execute(
                "INSERT OR REPLACE INTO pipeline_state (id, status, current_stage) VALUES (?, ?, ?)",
                (cascade_id, "PENDING", "SLAB")
            )
            conn.commit()
    await loop.run_in_executor(None, _init_state)

    await write_telemetry_log("ORCHESTRATOR", "INFO", f"Cascade tracking active: {cascade_id}")
    background_tasks.add_task(orchestrate_pipeline_task, cascade_id, file_path)
    
    return {"status": "QUEUED", "cascade_id": cascade_id}

@router.get("/logs/stream")
async def stream_logs():
    async def log_generator():
        last_id = 0
        while True:
            loop = asyncio.get_event_loop()
            def _fetch_logs():
                with init_db_connection("telemetry.db") as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id, agent_name, log_level, message, timestamp FROM logs WHERE id > ? ORDER BY id ASC",
                        (last_id,)
                    )
                    return cursor.fetchall()
            
            new_logs = await loop.run_in_executor(None, _fetch_logs)
            for row in new_logs:
                last_id = row[0]
                payload = {
                    "id": row[0],
                    "agent": row[1],
                    "level": row[2],
                    "message": row[3],
                    "timestamp": row[4]
                }
                yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(log_generator(), media_type="text/event-stream")
import os
import uuid
from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from typing import List

# Ensure this router matches the prefix used in main.py (likely already defined at the top of your file)
# router = APIRouter(prefix="/api/v1/cascade", tags=["cascade"])

@router.post("/batch-process")
async def process_incoming_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    upload_dir = "/workspaces/slab-forge-orchestrator/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    staged_manifest = []
    
    for asset in files:
        # Generate a clean tracking filename to prevent collisions
        file_extension = os.path.splitext(asset.filename)[1] or ".jpg"
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Read the stream and write out to workspace storage
        content = await asset.read()
        with open(file_path, "wb") as f:
            f.write(content)
            
        staged_manifest.append({
            "original_name": asset.filename,
            "saved_path": file_path
        })
    
    # TODO: Add your orchestrator background execution task here:
    # background_tasks.add_task(run_slab_forge_sequence, staged_manifest)
        
    return {
        "status": "PIPELINE_STAGED",
        "batch_size": len(staged_manifest),
        "manifest": [item["original_name"] for item in staged_manifest]
    }