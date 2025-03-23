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
        return FileResponse(
            temp_output, 
            media_type="image/jpeg",
            filename=f"restored_{file.filename}"
        )
        
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup
        logger.info("Cleaning up temporary files")
        if temp_input and os.path.exists(temp_input):
            os.remove(temp_input)
        if temp_output and os.path.exists(temp_output):
            os.remove(temp_output)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, timeout_keep_alive=300)