import cv2

class Camera:
    def __init__(self, camera_id=0, width=640, height=480):
        self.cap = cv2.VideoCapture(camera_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
        if not self.cap.isOpened():
            raise RuntimeError("Couldn't open camera")

    def get_frame_bytes(self):
        """Captures a frame, encodes it as JPEG, and returns the bytes."""
        success, frame = self.cap.read()
        if not success:
            return None
        
        # Encode the frame as .jpg with 80% quality
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return buffer.tobytes() if ret else None

    def release(self):
        self.cap.release()