#!/usr/bin/env python3
"""Stream camera frames in a browser and save calibration snapshots."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import socket
import sys
import threading
import time

import cv2


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.cv.camera import Camera


DEFAULT_OUTPUT_DIR = "media/calibration"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Stream camera frames and save calibration snapshots in a browser."
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--backend", choices=("picamera2", "opencv"), default="picamera2")
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument("--prefix", default="calibration")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    return parser.parse_args()


def next_image_path(output_dir, prefix):
    existing = sorted(output_dir.glob(f"{prefix}_*.png"))
    if not existing:
        return output_dir / f"{prefix}_001.png"

    highest = 0
    for path in existing:
        suffix = path.stem.removeprefix(f"{prefix}_")
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return output_dir / f"{prefix}_{highest + 1:03d}.png"


class CaptureState:
    def __init__(self, camera, output_dir, prefix):
        self.camera = camera
        self.output_dir = output_dir
        self.prefix = prefix
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.latest_frame = None
        self.latest_jpeg = None
        self.saved_count = 0
        self.last_error = None

    def capture_loop(self):
        while not self.stop_event.is_set():
            try:
                frame = self.camera.get_frame()
                ok, encoded = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80]
                )
                if not ok:
                    raise RuntimeError("Could not encode camera frame as JPEG.")
                with self.lock:
                    self.latest_frame = frame
                    self.latest_jpeg = encoded.tobytes()
                    self.last_error = None
            except Exception as exc:
                with self.lock:
                    self.latest_frame = None
                    self.latest_jpeg = None
                    self.last_error = str(exc)
                time.sleep(0.1)

    def save_snapshot(self):
        with self.lock:
            if self.latest_frame is None:
                raise RuntimeError(self.last_error or "No camera frame is available yet.")
            frame = self.latest_frame.copy()
            path = next_image_path(self.output_dir, self.prefix)
            if not cv2.imwrite(str(path), frame):
                raise RuntimeError(f"Could not save image: {path}")
            self.saved_count += 1
            return path, self.saved_count


def page_html(width, height):
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Camera calibration capture</title>
  <style>
    body {{ background:#121212; color:#eee; font-family:monospace; text-align:center; margin:0; padding:20px; }}
    h2 {{ color:#00e676; }}
    .stream {{ display:inline-block; max-width:100%; border:2px solid #333; border-radius:8px; overflow:hidden; background:#000; }}
    img {{ display:block; width:{width}px; height:{height}px; max-width:100%; object-fit:contain; }}
    button {{ margin-top:16px; padding:12px 24px; border:0; border-radius:6px; background:#00e676; color:#111; font:700 16px monospace; cursor:pointer; }}
    button:disabled {{ opacity:.5; cursor:wait; }}
    #status {{ min-height:1.5em; color:#aaa; }}
  </style>
</head>
<body>
  <h2>Camera calibration capture</h2>
  <div class="stream"><img src="/stream.mjpg" alt="Live camera stream"></div><br>
  <button id="capture" type="button">Save calibration image</button>
  <p id="status">Waiting for capture</p>
  <script>
    const button = document.getElementById('capture');
    const status = document.getElementById('status');
    button.addEventListener('click', async () => {{
      button.disabled = true;
      try {{
        const response = await fetch('/capture', {{ method: 'POST' }});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Capture failed');
        status.textContent = `Saved ${{result.path}} (${{result.saved_count}} this run)`;
      }} catch (error) {{
        status.textContent = `Error: ${{error.message}}`;
      }} finally {{
        button.disabled = false;
      }}
    }});
  </script>
</body>
</html>"""


def make_handler(state, width, height):
    class StreamingHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                body = page_html(width, height).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if self.path != "/stream.mjpg":
                self.send_error(404)
                return

            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private, no-store")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while not state.stop_event.is_set():
                    with state.lock:
                        frame = state.latest_jpeg
                    if frame is not None:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                        self.wfile.write(frame)
                        self.wfile.write(b"\r\n")
                    time.sleep(0.04)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self):
            if self.path != "/capture":
                self.send_error(404)
                return

            try:
                path, saved_count = state.save_snapshot()
                print(f"[CALIB_CAPTURE] saved {path}")
                payload = {"path": str(path), "saved_count": saved_count}
                status = 200
            except RuntimeError as exc:
                payload = {"error": str(exc)}
                status = 503

            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    return StreamingHandler


def browser_url(host, port):
    if host not in ("0.0.0.0", "::"):
        return f"http://{host}:{port}"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            address = probe.getsockname()[0]
    except OSError:
        try:
            address = socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            address = "127.0.0.1"
    return f"http://{address}:{port}"


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    camera = Camera(
        width=args.width,
        height=args.height,
        backend=args.backend,
        device_index=args.device_index,
    )
    state = CaptureState(camera, output_dir, args.prefix)
    capture_thread = threading.Thread(target=state.capture_loop, daemon=True)
    server = None
    try:
        server = ThreadingHTTPServer(
            (args.host, args.port), make_handler(state, args.width, args.height)
        )
        server.daemon_threads = False

        print(f"[CALIB_CAPTURE] Saving snapshots to: {output_dir}")
        print(f"[CALIB_CAPTURE] Open {browser_url(args.host, args.port)}")
        print("[CALIB_CAPTURE] Press Ctrl+C to stop.")
        capture_thread.start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    finally:
        state.stop_event.set()
        if server is not None:
            server.server_close()
        if capture_thread.is_alive():
            capture_thread.join(timeout=2.0)
        camera.release()


if __name__ == "__main__":
    main()
