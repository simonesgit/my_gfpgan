from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import uvicorn
from gfpgan_handler import GFPGANHandler
import os

app = FastAPI()
gfpgan_handler = GFPGANHandler()

@app.post("/restore")
async def restore_face(file: UploadFile = File(...)):
    temp_input = f"temp_input_{file.filename}"
    temp_output = f"temp_output_{file.filename}"
    
    # Save uploaded file
    with open(temp_input, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Process image
    gfpgan_handler.process_image(temp_input, temp_output)
    
    # Return processed image
    response = FileResponse(temp_output)
    
    # Cleanup
    os.remove(temp_input)
    os.remove(temp_output)
    
    return response

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)