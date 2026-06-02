import sys
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import simulation worker
from ingress.training_feed import run_stream_simulation

# Ensure the repository root is in the sys path
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import your new receiver module
from ingress.receiver import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    # Wire simulation feed into the ASGI event loop
    simulation_task = asyncio.create_task(run_stream_simulation())
    try:
        yield
    finally:
        print("Shutting down...")
        simulation_task.cancel()

app = FastAPI(title="Log Ingress Service", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
async def root():
    return {"message": "Log Ingress Service is running"}
