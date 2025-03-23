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
app.mount("/static", StaticFiles(directory="static"), name="static")

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
                
                // Disable form during processing
                form.querySelector('button').disabled = true;
                status.textContent = 'Uploading image...';
                
                try {
                    // Submit image
                    const submitResponse = await fetch('/submit', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (!submitResponse.ok) throw new Error('Upload failed');
                    
                    const jobData = await submitResponse.json();
                    status.textContent = 'Processing image...';
                    
                    // Poll for status
                    while (true) {
                        const statusResponse = await fetch(jobData.status_url);
                        
                        if (statusResponse.headers.get('content-type')?.includes('image')) {
                            // Image is ready
                            const blob = await statusResponse.blob();
                            const imgUrl = URL.createObjectURL(blob);
                            result.innerHTML = `
                                <h3>Restored Image:</h3>
                                <img src="${imgUrl}" style="max-width: 100%">
                                <br>
                                <a href="${imgUrl}" download="restored_image.jpg" class="button">Download</a>
                            `;
                            status.textContent = 'Processing complete!';
                            break;
                        }
                        
                        const statusData = await statusResponse.json();
                        if (statusData.status === 'failed') {
                            throw new Error('Processing failed');
                        }
                        
                        // Wait before next poll
                        await new Promise(resolve => setTimeout(resolve, 2000));
                    }
                } catch (error) {
                    status.textContent = `Error: ${error.message}`;
                } finally {
                    form.querySelector('button').disabled = false;
                }
            };
        </script>
    </body>
    </html>
    """

@app.post("/submit")
async def submit_image(file: UploadFile = File(...)):
    try:
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