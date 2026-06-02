import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
from routers.dispatcher import JobDispatcher, AssetIdentificationJob, DispatchTarget

app = FastAPI(title="Slab-Forge Mobile Gateway")

# Enable CORS so your mobile phone web browser can securely communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the dispatcher with the core ScraperNetworkProtocol integrated
dispatcher = JobDispatcher(max_workers=5)

class MobileJobRequest(BaseModel):
    url: str
    source_type: str = "industrial"

@app.post("/api/dispatch")
async def dispatch_mobile_job(payload: MobileJobRequest):
    if not payload.url:
        raise HTTPException(status_code=400, detail="Missing target URL")
        
    # Format the incoming mobile request into the core pipeline job architecture
    job = AssetIdentificationJob(
        target_type=DispatchTarget.WEB_SCRAPE,
        payload={"url": payload.url, "source_type": payload.source_type}
    )
    
    try:
        # Route directly through the network protocol
        result = await dispatcher._route_to_web_scrape(job)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)