import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from src.cv.camera import Camera

# Camera global variable to be initialized in lifespan
camera = None

# Lifespan function to manage camera lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    global camera
    print("Camera Initialization...")
    camera = Camera()
    yield  # Тут сервер працює і приймає запити
    print("🛑 Camera Shutdown...")
    if camera:
        camera.release()

# Передаємо lifespan у наш додаток
app = FastAPI(title="Erso FPV - Ground Station", lifespan=lifespan)
templates = Jinja2Templates(directory="src/web_ui/templates")

async def frame_generator():
    """Генератор, який безперервно віддає кадри клієнту."""
    global camera
    while True:
        if camera:
            frame_bytes = camera.get_frame_bytes()
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        # Пауза для розвантаження процесора (~30 FPS)
        await asyncio.sleep(0.03)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Головна сторінка."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request}
    )

@app.get("/video_stream")
async def video_stream():
    """Ендпоінт трансляції MJPEG."""
    return StreamingResponse(
        frame_generator(), 
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

if __name__ == "__main__":
    uvicorn.run("src.web_ui.server:app", host="0.0.0.0", port=8000, reload=True)