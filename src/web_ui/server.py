import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import uvicorn

# Import Camera class from the cv module
from src.cv.camera import Camera

app = FastAPI(title="Drone Ground Station MVP")
templates = Jinja2Templates(directory="src/web_ui/templates")

# Initialize the camera on startup
camera = None

@app.on_event("startup")
async def startup_event():
    global camera
    camera = Camera()

@app.on_event("shutdown")
async def shutdown_event():
    global camera
    if camera:
        camera.release()

async def frame_generator():
    """Generator that yields frames for StreamingResponse."""
    global camera
    while True:
        frame_bytes = camera.get_frame_bytes()
        if frame_bytes:
            # Format bytes according to MJPEG standard
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        # Small pause to avoid blocking the event loop (approximately 30 FPS)
        await asyncio.sleep(0.03)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main interface page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/video_stream")
async def video_stream():
    """Endpoint that streams video."""
    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    # Start the server. 0.0.0.0 allows connections from any device on the Wi-Fi network
    uvicorn.run("src.web_ui.server:app", host="0.0.0.0", port=8000, reload=True)