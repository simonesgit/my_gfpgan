from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import uvicorn
from gfpgan_handler import GFPGANHandler
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
gfpgan_handler = GFPGANHandler()

@app.post("/restore")
async def restore_face(file: UploadFile = File(...)):
    temp_input = None
    temp_output = None
    try:
        # Create outputs directory if it doesn't exist
        os.makedirs("/app/outputs", exist_ok=True)
        
        # Log file details
        logger.info(f"Received file: {file.filename}")
        
        # Create unique filenames
        temp_input = f"/app/outputs/input_{file.filename}"
        temp_output = f"/app/outputs/output_{file.filename}"
        
        # Save uploaded file
        logger.info("Saving input file")
        content = await file.read()
        with open(temp_input, "wb") as buffer:
            buffer.write(content)
        
        # Process image
        logger.info("Processing image with GFPGAN")
        success = gfpgan_handler.process_image(temp_input, temp_output)
        
        if not success:
            logger.error("Processing failed")
            raise HTTPException(status_code=500, detail="Failed to process image")
        
        if not os.path.exists(temp_output):
            logger.error("Output file not found")
            raise HTTPException(status_code=500, detail="Output file not generated")
            
        logger.info("Processing successful, returning file")
        
        # Read the file into memory before cleanup
        with open(temp_output, 'rb') as f:
            content = f.read()
            
        # Cleanup files
        logger.info("Cleaning up temporary files")
        if os.path.exists(temp_input):
            os.remove(temp_input)
        if os.path.exists(temp_output):
            os.remove(temp_output)
            
        # Return the file content directly
        from fastapi.responses import Response
        return Response(
            content=content,
            media_type="image/jpeg",
            headers={
                "Content-Disposition": f'attachment; filename="restored_{file.filename}"'
            }
        )
        
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        # Cleanup on error
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