from threading import Lock

import cv2
import numpy as np

try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None


class CameraCalibration:
    def __init__(self, camera_matrix, dist_coeffs):
        self.camera_matrix = np.asarray(camera_matrix, dtype=np.float64)
        self.dist_coeffs = np.asarray(dist_coeffs, dtype=np.float64)

    @classmethod
    def from_file(cls, path):
        if path.endswith(".npz"):
            data = np.load(path)
            camera_matrix = data.get("camera_matrix")
            if camera_matrix is None:
                camera_matrix = data.get("mtx")
            dist_coeffs = data.get("dist_coeffs")
            if dist_coeffs is None:
                dist_coeffs = data.get("dist")
            if camera_matrix is None or dist_coeffs is None:
                raise ValueError(
                    "Calibration .npz must contain camera_matrix/dist_coeffs or mtx/dist"
                )
            return cls(camera_matrix, dist_coeffs)

        storage = cv2.FileStorage(path, cv2.FILE_STORAGE_READ)
        if not storage.isOpened():
            raise ValueError(f"Could not open calibration file: {path}")
        try:
            camera_matrix = storage.getNode("camera_matrix").mat()
            if camera_matrix is None:
                camera_matrix = storage.getNode("mtx").mat()
            dist_coeffs = storage.getNode("dist_coeffs").mat()
            if dist_coeffs is None:
                dist_coeffs = storage.getNode("dist").mat()
        finally:
            storage.release()

        if camera_matrix is None or dist_coeffs is None:
            raise ValueError(
                "Calibration file must contain camera_matrix/dist_coeffs or mtx/dist"
            )
        return cls(camera_matrix, dist_coeffs)


class Camera:
    def __init__(
        self,
        width=640,
        height=480,
        jpeg_quality=80,
        calibration=None,
        backend="picamera2",
        device_index=0,
    ):
        self._lock = Lock()
        self._jpeg_quality = int(jpeg_quality)
        self._backend = backend
        self._capture = None
        self.calibration = calibration

        if backend == "picamera2":
            if Picamera2 is None:
                raise RuntimeError("picamera2 is unavailable; use backend='opencv'.")
            self._capture = Picamera2()
            config = self._capture.create_video_configuration(
                main={"size": (width, height), "format": "RGB888"}
            )
            self._capture.configure(config)
            self._capture.start()
        elif backend == "opencv":
            self._capture = cv2.VideoCapture(device_index)
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            if not self._capture.isOpened():
                raise RuntimeError(f"Could not open OpenCV camera index {device_index}.")
        else:
            raise ValueError("Camera backend must be 'picamera2' or 'opencv'.")

    def get_frame(self):
        with self._lock:
            if self._backend == "picamera2":
                frame_rgb = self._capture.capture_array("main")
                return cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

            ok, frame = self._capture.read()
            if not ok:
                raise RuntimeError("Could not read frame from OpenCV camera.")
            return frame

    def get_frame_bytes(self):
        try:
            frame_bgr = self.get_frame()
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
        if self._capture is None:
            return
        if self._backend == "picamera2":
            self._capture.stop()
        else:
            self._capture.release()
