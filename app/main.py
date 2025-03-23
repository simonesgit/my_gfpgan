from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response, JSONResponse
import uvicorn
from gfpgan_handler import GFPGANHandler
import os
import logging
import asyncio
from uuid import uuid4
from typing import Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
gfpgan_handler = GFPGANHandler()

# Store job status and file paths
jobs: Dict[str, Dict] = {}

# Add these imports at the top
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

# Add after app = FastAPI()
# Remove these lines
# app.mount("/static", StaticFiles(directory="static"), name="static")

# Keep only the necessary import
from fastapi.responses import HTMLResponse

# Add new endpoint for the web interface
@app.get("/", response_class=HTMLResponse)
async def web_interface():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>GFPGAN Face Restoration</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .container { text-align: center; }
            #uploadForm { margin: 20px 0; }
            #status { margin: 20px 0; }
            #result { margin: 20px 0; }
            .button { background: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            .button:disabled { background: #cccccc; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>GFPGAN Face Restoration</h1>
            <form id="uploadForm">
                <input type="file" id="imageFile" accept="image/*" required>
                <button type="submit" class="button">Upload and Process</button>
            </form>
            <div id="status"></div>
            <div id="result"></div>
        </div>
        
        <script>
            const form = document.getElementById('uploadForm');
            const status = document.getElementById('status');
            const result = document.getElementById('result');
            
            form.onsubmit = async (e) => {
                e.preventDefault();
                const formData = new FormData();
                formData.append('file', document.getElementById('imageFile').files[0]);
                
                // Reset UI
                form.querySelector('button').disabled = true;
                status.textContent = 'Uploading image...';
                result.innerHTML = '';
                
                try {
                    // Submit image
                    const submitResponse = await fetch('/submit', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (!submitResponse.ok) throw new Error('Upload failed');
                    
                    const jobData = await submitResponse.json();
                    let dots = '';
                    let attempts = 0;
                    const maxAttempts = 90; // 3 minutes maximum wait
                    
                    // Poll for status
                    while (attempts < maxAttempts) {
                        try {
                            const statusResponse = await fetch(jobData.status_url);
                            
                            if (statusResponse.headers.get('content-type')?.includes('image')) {
                                // Image is ready
                                const blob = await statusResponse.blob();
                                const imgUrl = URL.createObjectURL(blob);
                                result.innerHTML = `
                                    <h3>Restored Image:</h3>
                                    <div style="display: flex; justify-content: center; margin: 20px 0;">
                                        <div style="max-width: 45%; margin: 0 10px;">
                                            <h4>Original</h4>
                                            <img src="${URL.createObjectURL(document.getElementById('imageFile').files[0])}" 
                                                style="max-width: 100%; border: 1px solid #ccc;">
                                        </div>
                                        <div style="max-width: 45%; margin: 0 10px;">
                                            <h4>Restored</h4>
                                            <img src="${imgUrl}" style="max-width: 100%; border: 1px solid #ccc;">
                                        </div>
                                    </div>
                                    <a href="${imgUrl}" download="restored_image.jpg" class="button">Download Restored Image</a>
                                `;
                                status.textContent = '✅ Processing complete! You can download the restored image.';
                                break;
                            }
                            
                            const statusData = await statusResponse.json();
                            if (statusData.status === 'failed') {
                                throw new Error('Processing failed - please try again');
                            }
                            
                            // Update status with animated dots
                            dots = dots.length >= 3 ? '' : dots + '.';
                            status.textContent = `⏳ Processing image${dots} (${Math.round((attempts/maxAttempts) * 100)}%)`;
                            
                            // Wait before next poll
                            await new Promise(resolve => setTimeout(resolve, 2000));
                            attempts++;
                            
                        } catch (error) {
                            if (attempts >= maxAttempts) {
                                throw new Error('Processing timeout - please try again');
                            }
                            // Continue polling even if one request fails
                            await new Promise(resolve => setTimeout(resolve, 2000));
                            attempts++;
                        }
                    }
                    
                    if (attempts >= maxAttempts) {
                        throw new Error('Processing timeout - please try again');
                    }
                    
                } catch (error) {
                    status.textContent = `❌ Error: ${error.message}`;
                    result.innerHTML = '<button onclick="location.reload()" class="button">Try Again</button>';
                } finally {
                    form.querySelector('button').disabled = false;
                }
            };
        </script>
    </body>
    </html>
    """

# Add near the top with other imports
from datetime import datetime, timedelta
import glob

# Add before jobs dictionary
MAX_FILE_AGE_MINUTES = 10

# Add new function for cleanup
def cleanup_old_files():
    try:
        cutoff_time = datetime.now() - timedelta(minutes=MAX_FILE_AGE_MINUTES)
        output_files = glob.glob("/app/outputs/*")
        
        for file_path in output_files:
            file_time = datetime.fromtimestamp(os.path.getctime(file_path))
            if file_time < cutoff_time:
                os.remove(file_path)
                logger.info(f"Removed old file: {file_path}")
    except Exception as e:
        logger.error(f"Error during file cleanup: {str(e)}")

# Modify the submit endpoint to include cleanup
@app.post("/submit")
async def submit_image(file: UploadFile = File(...)):
    try:
        # Cleanup old files first
        cleanup_old_files()
        
        # Generate unique job ID
        job_id = str(uuid4())
        
        # Create outputs directory
        os.makedirs("/app/outputs", exist_ok=True)
        
        # Save input file
        input_path = f"/app/outputs/input_{job_id}_{file.filename}"
        output_path = f"/app/outputs/output_{job_id}_{file.filename}"
        
        content = await file.read()
        with open(input_path, "wb") as buffer:
            buffer.write(content)
        
        # Store job info
        jobs[job_id] = {
            "status": "processing",
            "input_path": input_path,
            "output_path": output_path,
            "original_filename": file.filename
        }
        
        # Start processing in background
        asyncio.create_task(process_image(job_id))
        
        return JSONResponse({
            "job_id": job_id,
            "status": "processing",
            "status_url": f"/status/{job_id}"
        })
        
    except Exception as e:
        logger.error(f"Error submitting job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_image(job_id: str):
    try:
        job = jobs[job_id]
        success = gfpgan_handler.process_image(job["input_path"], job["output_path"])
        
        if success and os.path.exists(job["output_path"]):
            jobs[job_id]["status"] = "completed"
        else:
            jobs[job_id]["status"] = "failed"
            
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {str(e)}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = jobs[job_id]
    
    if job["status"] == "failed":
        error = job.get("error", "Unknown error")
        # Cleanup failed job
        cleanup_job(job_id)
        raise HTTPException(status_code=500, detail=error)
        
    if job["status"] == "processing":
        return JSONResponse({
            "status": "processing",
            "job_id": job_id
        })
    
    # Job completed, return the image
    try:
        with open(job["output_path"], "rb") as f:
            content = f.read()
            
        # Cleanup completed job
        cleanup_job(job_id)
        
        return Response(
            content=content,
            media_type="image/jpeg",
            headers={
                "Content-Disposition": f'attachment; filename="restored_{job["original_filename"]}"'
            }
        )
    except Exception as e:
        logger.error(f"Error returning result for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def cleanup_job(job_id: str):
    job = jobs[job_id]
    # Remove files
    if os.path.exists(job["input_path"]):
        os.remove(job["input_path"])
    if os.path.exists(job["output_path"]):
        os.remove(job["output_path"])
    # Remove job from dictionary
    jobs.pop(job_id)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)