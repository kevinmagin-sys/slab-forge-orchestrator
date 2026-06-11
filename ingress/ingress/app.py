import os
from fastapi import FastAPI, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

app = FastAPI()

# Calculate absolute path to the root static directory
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
static_dir = os.path.join(base_dir, "static")

# Mount static files safely for asset image rendering
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def read_root():
    return {"status": "online", "engine": "Slab-Forge-Orchestrator"}

# TARGET ROUTE FOR MULTI-ASSET EXTRACTION
@app.post("/api/extract")
async def extract_industrial_assets(files: list[UploadFile] = File(...)):
    extracted_manifest = []
    
    for file in files:
        contents = await file.read()
        print(f"[INGRESS] Received Asset: {file.filename} | Size: {len(contents)} bytes")
        
        # Placeholder dictionary structure aligning with your logViewer.js match schema
        extracted_manifest.append({
            "item": file.filename.upper().split('.')[0],
            "source_url": "https://www.industrial-surplus-catalog.com",
            "image_url": f"/static/uploads/{file.filename}",
            "verified": True,
            "confidence": 0.95
        })
        
    print(f"[INGRESS] Complete. Processed {len(files)} assets.")
    return {
        "status": "success",
        "processed_assets": len(files),
        "matches": extracted_manifest
    }

@app.get("/api/logs")
async def get_telemetry_logs():
    # Fallback route ensuring logViewer.js fetchLogs() always receives a valid data schema
    return {
        "status": "success",
        "processed_assets": 0,
        "matches": []
    }