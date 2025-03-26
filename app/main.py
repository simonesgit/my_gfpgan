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
                    // Submit image with short timeout
                    const submitResponse = await Promise.race([
                        fetch('/submit', {
                            method: 'POST',
                            body: formData
                        }),
                        new Promise((_, reject) => 
                            setTimeout(() => reject(new Error('Upload timeout')), 15000)
                        )
                    ]);
                    
                    if (!submitResponse.ok) throw new Error('Upload failed');
                    
                    // Add logging to debug response
                    const jobData = await submitResponse.json();
                    console.log('Submit response:', jobData);  // Debug log
                    
                    if (!jobData.status_url) {
                        throw new Error('Invalid server response');
                    }
                    status.textContent = jobData.message;
                    
                    // Remove this duplicate declaration
                    let attempts = 0;
                    const maxAttempts = 30; // 5 minutes maximum wait (10 seconds × 30 attempts)
                    
                    // Poll for status
                    async function checkStatus() {
                        const statusResponse = await fetch(jobData.status_url);
                        
                        if (statusResponse.status === 404) {
                            throw new Error('Job not found - please try again');
                        }
                        
                        const statusData = await statusResponse.json();
                        
                        if (statusData.status === 'failed') {
                            throw new Error(statusData.message || 'Processing failed');
                        }
                        
                        if (statusData.status === 'completed' && statusData.image_url) {
                            // Display images
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
                                        <img src="${statusData.image_url}" style="max-width: 100%; border: 1px solid #ccc;">
                                    </div>
                                </div>
                                <button onclick="window.open('${statusData.image_url}')" class="button">View Full Size</button>
                                <a href="${statusData.image_url}" download="restored_image.jpg" class="button" style="margin-left: 10px;">Save to Computer</a>
                            `;
                            status.textContent = '✅ Processing complete!';
                            return true;
                        } else {
                            status.textContent = statusData.message;
                            result.innerHTML = `
                                <button onclick="checkStatus()" class="button">Check Status</button>
                            `;
                            return false;
                        }
                    }
                    
                    // Keep this declaration
                    attempts = 0;  // Just assign, don't redeclare
                    // const maxAttempts = 30;  // Remove duplicate
                    
                    while (attempts < maxAttempts) {
                        try {
                            const isComplete = await checkStatus();
                            if (isComplete) break;
                            
                            await new Promise(resolve => setTimeout(resolve, 20000));
                            attempts++;
                        } catch (error) {
                            if (error.message === 'Failed to fetch') {
                                await new Promise(resolve => setTimeout(resolve, 20000));
                                attempts++;
                                continue;
                            }
                            throw error;
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

@app.post("/submit")
async def submit_image(file: UploadFile = File(...)):
    try:
        # Cleanup old files first
        cleanup_old_files()
        
        job_id = str(uuid4())
        os.makedirs("/app/outputs", exist_ok=True)
        
        input_path = f"/app/outputs/input_{job_id}_{file.filename}"
        output_path = f"/app/outputs/output_{job_id}_{file.filename}"
        
        content = await file.read()
        with open(input_path, "wb") as buffer:
            buffer.write(content)
        
        # Store job info with timestamp
        jobs[job_id] = {
            "status": "processing",
            "input_path": input_path,
            "output_path": output_path,
            "original_filename": file.filename,
            "start_time": datetime.now()
        }
        
        # Start processing in background
        asyncio.create_task(process_image(job_id))
        
        return JSONResponse({
            "job_id": job_id,
            "status": "processing",
            "status_url": f"/status/{job_id}",
            "message": "Image uploaded successfully. Please check status in 2-3 minutes."
        })
        
    except Exception as e:
        logger.error(f"Error submitting job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = jobs[job_id]
    
    if job["status"] == "failed":
        error = job.get("error", "Unknown error")
        cleanup_job(job_id)
        raise HTTPException(status_code=500, detail=error)
        
    if job["status"] == "processing":
        elapsed_time = datetime.now() - job["start_time"]
        elapsed_minutes = elapsed_time.total_seconds() / 60
        
        return JSONResponse({
            "status": "processing",
            "job_id": job_id,
            "message": f"Still processing (running for {elapsed_minutes:.1f} minutes)",
            "elapsed_minutes": round(elapsed_minutes, 1)
        })
    
    # Job completed
    if not os.path.exists(job["output_path"]):
        raise HTTPException(status_code=404, detail="Output file not found")
        
    image_url = f"/images/{job_id}/{os.path.basename(job['output_path'])}"
    return JSONResponse({
        "status": "completed",
        "image_url": image_url,
        "message": "Processing complete!"
    })

# Add new endpoint to serve images
@app.get("/images/{job_id}/{filename}")
async def get_image(job_id: str, filename: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = jobs[job_id]
    if not os.path.exists(job["output_path"]):
        raise HTTPException(status_code=404, detail="Image not found")
        
    with open(job["output_path"], "rb") as f:
        content = f.read()
    
    return Response(
        content=content,
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f'attachment; filename="restored_{job["original_filename"]}"',
            "Cache-Control": "no-cache"
        }
    )

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

def cleanup_job(job_id: str):
    if job_id in jobs:
        jobs.pop(job_id)  # Only remove from jobs dictionary, keep files for download

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)