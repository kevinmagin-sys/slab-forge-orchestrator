import os

app_py_path = 'ingress/app.py'
with open(app_py_path, 'r') as f:
    content = f.read()

# Add necessary imports if missing
if 'from typing import List' not in content:
    content = 'from typing import List\n' + content
if 'import os' not in content:
    content = 'import os\n' + content

new_route = """
@app.post("/upload-images")
async def upload_images(files: List[UploadFile] = File(...)):
    upload_dir = "./static/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    saved_paths = []
    for file in files:
        if not file.content_type.startswith("image/"):
            continue
        
        file_path = os.path.join(upload_dir, file.filename)
        with open(file_path, "wb") as buffer:
            # Note: file.file is a file-like object
            import shutil
            shutil.copyfileobj(file.file, buffer)
        saved_paths.append(file_path)
    
    return {"status": "success", "paths": saved_paths}
"""

if '@app.post("/upload-images")' not in content:
    content += new_route

with open(app_py_path, 'w') as f:
    f.write(content)

# Update index.html
html_path = 'static/index.html'
if os.path.exists(html_path):
    with open(html_path, 'r') as f:
        html_content = f.read()
    
    inputs_html = """
    <div id="upload-container" style="margin: 20px; padding: 20px; border: 1px solid #ccc;">
        <h3>Upload Images</h3>
        <div>
            <label>Camera Roll (Multiple):</label>
            <input type="file" id="camera-roll" multiple accept="image/*">
        </div>
        <div style="margin-top: 10px;">
            <label>Active Camera:</label>
            <input type="file" id="active-camera" accept="image/*" capture="environment">
        </div>
    </div>
    """
    
    if 'id="upload-container"' not in html_content:
        # Insert before </body>
        html_content = html_content.replace('</body>', inputs_html + '\n</body>')
    
    with open(html_path, 'w') as f:
        f.write(html_content)

print("Files updated successfully")
