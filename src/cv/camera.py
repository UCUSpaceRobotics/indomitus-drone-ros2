from picamera2 import Picamera2
import cv2

class Camera:
    def __init__(self, width=640, height=480):
        self.picam2 = Picamera2()
        
        # Налаштовуємо конфігурацію: потік "main" з роздільною здатністю 640x480
        config = self.picam2.create_video_configuration(
            main={"size": (width, height), "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()

    def get_frame_bytes(self):
        """Захоплює поточний кадр як масив та кодує в JPEG."""
        try:
            # Беремо готовий масив пікселів напряму з потоку "main"
            frame = self.picam2.capture_array("main")
            
            # Picamera2 віддає RGB, а OpenCV працює з BGR
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Кодуємо в байти JPEG
            ret, encoded = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return encoded.tobytes() if ret else None
        except Exception as e:
            # Тепер, якщо щось піде не так, ми одразу побачимо це в терміналі
            print(f"❌ Помилка обробки кадру: {e}")
            return None

    def release(self):
        self.picam2.stop()