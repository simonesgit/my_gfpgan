from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response, StreamingResponse
import uvicorn
from gfpgan_handler import GFPGANHandler
import os
import logging
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
gfpgan_handler = GFPGANHandler()

async def process_with_heartbeat(temp_input, temp_output, gfpgan_handler):
    async def heartbeat():
        while True:
            yield b'\n'  # Send newline as heartbeat
            await asyncio.sleep(30)  # Send heartbeat every 30 seconds

    # Start heartbeat
    heartbeat_task = asyncio.create_task(heartbeat().__anext__())
    
    # Process image
    success = gfpgan_handler.process_image(temp_input, temp_output)
    
    # Cancel heartbeat
    heartbeat_task.cancel()
    
    return success

@app.post("/restore")
async def restore_face(file: UploadFile = File(...)):
    temp_input = None
    temp_output = None
    try:
        os.makedirs("/app/outputs", exist_ok=True)
        
        logger.info(f"Received file: {file.filename}")
        temp_input = f"/app/outputs/input_{file.filename}"
        temp_output = f"/app/outputs/output_{file.filename}"
        
        logger.info("Saving input file")
        content = await file.read()
        with open(temp_input, "wb") as buffer:
            buffer.write(content)
        
        logger.info("Processing image with GFPGAN")
        success = await process_with_heartbeat(temp_input, temp_output, gfpgan_handler)
        
        if not success:
            logger.error("Processing failed")
            raise HTTPException(status_code=500, detail="Failed to process image")
        
        if not os.path.exists(temp_output):
            logger.error("Output file not found")
            raise HTTPException(status_code=500, detail="Output file not generated")
            
        logger.info("Processing successful, returning file")
        
        with open(temp_output, 'rb') as f:
            content = f.read()
            
        logger.info("Cleaning up temporary files")
        if os.path.exists(temp_input):
            os.remove(temp_input)
        if os.path.exists(temp_output):
            os.remove(temp_output)
            
        return Response(
            content=content,
            media_type="image/jpeg",
            headers={
                "Content-Disposition": f'attachment; filename="restored_{file.filename}"'
            }
        )
        
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        if temp_input and os.path.exists(temp_input):
            os.remove(temp_input)
        if temp_output and os.path.exists(temp_output):
            os.remove(temp_output)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        timeout_keep_alive=300,
        timeout_graceful_shutdown=300
    )