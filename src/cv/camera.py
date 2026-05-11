from threading import Lock

import cv2
from picamera2 import Picamera2

class Camera:
    def __init__(self, width=640, height=480, jpeg_quality=80):
        self._lock = Lock()
        self._jpeg_quality = int(jpeg_quality)
        self.picam2 = Picamera2()

        config = self.picam2.create_video_configuration(
            main={"size": (width, height), "format": "BGR888"}
        )
        self.picam2.configure(config)
        self.picam2.start()

    def get_frame_bytes(self):
        try:
            with self._lock:
                frame_rgb = self.picam2.capture_array("main")

            frame_bgr = frame_rgb[:, :, ::-1]
            ret, encoded = cv2.imencode(
                ".jpg",
                frame_bgr,
                [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality],
            )
            return encoded.tobytes() if ret else None
        except Exception as e:
            print(f"Error capturing frame: {e}")
            return None

    def release(self):
        self.picam2.stop()