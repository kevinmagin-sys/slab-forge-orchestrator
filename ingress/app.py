from routers import dispatcher
import os
from typing import List
from fastapi import FastAPI, UploadFile, File
from routers import dispatcher
from routers import dispatcher

app.include_router(dispatcher.router)
app = FastAPI()
app.include_router(dispatcher.router)
app.include_router(dispatcher.router)

@app.post("/upload-images")
async def upload_images(files: List[UploadFile] = File(...)):
    upload_dir = "./static/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    saved_paths = []
    for file in files:
        if not file.content_type.startswith("image/"):
            continue
        
        file_path = os.path.join(upload_dir, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        saved_paths.append(f"/static/uploads/{file.filename}")
    
    return {"paths": saved_paths}
