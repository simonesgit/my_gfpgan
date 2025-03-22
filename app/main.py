from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import uvicorn
from gfpgan_handler import GFPGANHandler
import os

app = FastAPI()
gfpgan_handler = GFPGANHandler()

@app.post("/restore")
async def restore_face(file: UploadFile = File(...)):
    try:
        temp_input = f"temp_input_{file.filename}"
        temp_output = f"temp_output_{file.filename}"
        
        # Save uploaded file
        with open(temp_input, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Process image
        success = gfpgan_handler.process_image(temp_input, temp_output)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to process image")
        
        # Return processed image
        return FileResponse(temp_output, media_type="image/jpeg")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup
        if os.path.exists(temp_input):
            os.remove(temp_input)
        if os.path.exists(temp_output):
            os.remove(temp_output)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)