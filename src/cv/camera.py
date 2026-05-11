from picamera2 import Picamera2
import cv2

class Camera:
    def __init__(self, width=640, height=480):
        self.picam2 = Picamera2()
        
        # Set up a thread for the "main" stream with resolution 640x480
        config = self.picam2.create_video_configuration(
            main={"size": (width, height), "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()

    def get_frame_bytes(self):
        """Generator function to yield MJPEG frames."""
        try:
            
            frame = self.picam2.capture_array("main")
            
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            ret, encoded = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return encoded.tobytes() if ret else None
        except Exception as e:
            print(f"Error capturing frame: {e}")
            return None

    def release(self):
        self.picam2.stop()