from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
import uuid
import time
import logging
from typing import Optional, Dict, Any

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory stores
JOB_STORE: Dict[str, Dict[str, Any]] = {}
CACHE: Dict[str, Any] = {}

class ScrapeRequest(BaseModel):
    target: str
    bypass_cache: bool = False

async def background_worker_task(job_id: str, payload: ScrapeRequest):
    """Simulates a scraping task."""
    try:
        # Simulate work delay
        time.sleep(5) 
        result = {"url": payload.target, "content": "Sample scraped content"}
        
        # Update store and cache
        JOB_STORE[job_id]["status"] = "COMPLETED"
        JOB_STORE[job_id]["result"] = result
        CACHE[f"scrape:{payload.target}"] = result
    except Exception as e:
        logger.error(f"Error in job {job_id}: {e}")
        JOB_STORE[job_id]["status"] = "FAILED"
        JOB_STORE[job_id]["result"] = str(e)

@router.post("/scrape", status_code=status.HTTP_202_ACCEPTED)
async def handle_scrape_request(payload: ScrapeRequest, background_tasks: BackgroundTasks):
    target = payload.target
    if not target:
        raise HTTPException(status_code=400, detail="Target URL is required")

    # Cache Resolution Logic
    cache_key = f"scrape:{target}"
    cached = CACHE.get(cache_key)
    if cached and not payload.bypass_cache:
        return {"JobId": "CACHED", "Status": "COMPLETED", "Data": cached}

    # Job Registration
    job_id = str(uuid.uuid4())
    JOB_STORE[job_id] = {
        "status": "RUNNING",
        "timestamp": time.time(),
        "result": None
    }
    
    background_tasks.add_task(background_worker_task, job_id, payload)
    
    return {"JobId": job_id, "Status": "RUNNING"}

@router.get("/status/{job_id}", status_code=status.HTTP_200_OK)
async def poll_job_status(job_id: str):
    job_state = JOB_STORE.get(job_id)
    if not job_state:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Timeout Evaluation Loop
    if job_state["status"] == "RUNNING" and (time.time() - job_state["timestamp"] > 60):
        job_state["status"] = "TIMEOUT"
        return {"JobId": job_id, "Status": "TIMEOUT"}
    
    return {
        "JobId": job_id,
        "Status": job_state["status"],
        "Data": job_state["result"]
    }
import re
from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from pydantic import BaseModel
from typing import Any, List

class ScrapeRequest(BaseModel):
    target_url: str
    target_selectors: List[str]

def is_valid_url(url: str) -> bool:
    if not url or not url.strip():
        return False
    # Strictly match secure absolute URL protocol requirements
    return bool(re.match(r"^https?://", url.strip(), re.IGNORECASE))

@router.post("/scrape", status_code=status.HTTP_202_ACCEPTED)
async def handle_scrape_request(payload: ScrapeRequest, background_tasks: BackgroundTasks):
    target_url = payload.target_url.strip()
    
    # Mirroring VALIDATION_ERROR context
    if not is_valid_url(target_url):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A secure, absolute URL path is strictly required."
        )
        
    # (Existing task assignment and background worker triggers remain intact here)