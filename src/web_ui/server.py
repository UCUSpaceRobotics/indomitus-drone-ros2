import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from src.cv.camera import Camera

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Camera initialization...")
    app.state.shutdown_event = asyncio.Event()
    app.state.camera = Camera()
    try:
        yield
    finally:
        app.state.shutdown_event.set()
        print("Camera release")
        camera = getattr(app.state, "camera", None)
        if camera:
            camera.release()

app = FastAPI(title="Erso FPV - Ground Station", lifespan=lifespan)
templates = Jinja2Templates(directory="src/web_ui/templates")

async def frame_generator(request: Request):
    """Frame generator for the client."""
    try:
        while True:
            shutdown_event = getattr(request.app.state, "shutdown_event", None)
            if shutdown_event and shutdown_event.is_set():
                print("Shutdown requested, stopping stream.")
                break

            if await request.is_disconnected():
                print("Client disconnected, stopping stream.")
                break

            camera = getattr(request.app.state, "camera", None)
            if camera:
                frame_bytes = await asyncio.to_thread(camera.get_frame_bytes)
                if frame_bytes:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                    )
            else:
                await asyncio.sleep(0.1)

            await asyncio.sleep(0.01)
    except (asyncio.CancelledError, GeneratorExit):
        print("Stream cancelled, stopping generator.")
        raise


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page of the interface."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request}
    )

@app.get("/video_stream")
async def video_stream(request: Request):
    return StreamingResponse(
        frame_generator(request), 
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

if __name__ == "__main__":
    uvicorn.run("src.web_ui.server:app", host="0.0.0.0", port=8000, reload=True)