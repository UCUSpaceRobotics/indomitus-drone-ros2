import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from src.cv.camera import Camera

camera = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global camera
    print("Camera initialization...")
    camera = Camera()
    yield
    print("Camera release")
    if camera:
        camera.release()

app = FastAPI(title="Erso FPV - Ground Station", lifespan=lifespan)
templates = Jinja2Templates(directory="src/web_ui/templates")

async def frame_generator():
    """Asynchronous generator that yields MJPEG frames without blocking the server."""
    global camera
    while True:
        if camera:
            # CRITICAL FIX:
            # Run the heavy synchronous method capture_array in a separate
        
            frame_bytes = await asyncio.to_thread(camera.get_frame_bytes)
            
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # Minimal sleep to yield control back to the event loop, allowing other requests to be processed
        await asyncio.sleep(0.01)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page of the interface."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request}
    )

@app.get("/video_stream")
async def video_stream():
    """Endpoint for video streaming with cache protection."""
    return StreamingResponse(
        frame_generator(), 
        media_type="multipart/x-mixed-replace; boundary=frame",
        # Add headers to prevent caching of the video stream, ensuring clients always get the latest frames
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

if __name__ == "__main__":
    uvicorn.run("src.web_ui.server:app", host="0.0.0.0", port=8000, reload=True)