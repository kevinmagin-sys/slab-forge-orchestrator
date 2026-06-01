ls -R ingress && cat routers/cascade.py
cat routers/dispatcher.py
grep "def " routers/dispatcher.py
cat routers/dispatcher.py
import asyncio
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from config.settings import get_settings
from routers.cascade import get_all_routes
from protocols.scraper_network import ScraperNetworkProtocol

try:
    import cv2
except ImportError:
    cv2 = None

settings = get_settings()

class DispatchTarget(Enum):
    WEB_SCRAPE = "web_scrape"
    SOCKET = "socket"

class DispatcherError(Exception):
    pass

@dataclass
class AssetIdentificationJob:
    job_id: str
    serial_number: str
    target_type: DispatchTarget
    payload: Dict[str, Any] = field(default_factory=dict)
    target_endpoint: Optional[str] = None

class JobDispatcher:
    def __init__(self, max_workers: int = 5):
        self.semaphore = asyncio.Semaphore(max_workers)
        self.scraper = ScraperNetworkProtocol(timeout=10.0, max_retries=2)

    async def dispatch_batch(self, jobs: List[AssetIdentificationJob]) -> Dict[str, Dict[str, Any]]:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(self._dispatch_job(job)) for job in jobs]
        return {job.job_id: task.result() for job, task in zip(jobs, tasks)}

    async def _dispatch_job(self, job: AssetIdentificationJob) -> Dict[str, Any]:
        async with self.semaphore:
            if job.target_type == DispatchTarget.WEB_SCRAPE:
                return await self._route_to_web_scrape(job)
            elif job.target_type == DispatchTarget.SOCKET:
                return {"job_id": job.job_id, "status": "success", "result": "SOCKET_ACK"}
            return {"job_id": job.job_id, "status": "error", "message": "Unknown target"}

    async def _route_to_web_scrape(self, job: AssetIdentificationJob) -> Dict[str, Any]:
        try:
            url = job.payload.get("url", "")
            source_type = job.payload.get("source_type", "industrial")
            html_content = await self.scraper.fetch_raw_html(url)
            parsed_data = self.scraper.parse_industrial_specifications(html_content, source_type)
            return {"job_id": job.job_id, "status": "success", "result": parsed_data}
        except Exception as exc:
            return {"job_id": job.job_id, "status": "error", "message": str(exc)}

def create_default_dispatcher() -> JobDispatcher:
    return JobDispatcher(max_workers=settings.MAX_CONCURRENT_TASKS)
