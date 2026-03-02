import cv2
from picamera2 import Picamera2
import time
import os

def detect_face():
    # Шлях для збереження результату
    save_path = os.path.join(os.path.dirname(__file__), "..", "data", "captures", "face_detected2.jpg")

    # 1. Завантажуємо вбудовану в OpenCV нейромережу для пошуку облич (Haar Cascade)
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)

    # 2. Ініціалізуємо камеру
    picam2 = Picamera2()
    picam2.start()

    print("Камера запущена. Подивись в об'єктив! Знімок через 2 секунди...")
    time.sleep(2) # Час на автофокус та освітлення

    try:
        # 3. Робимо знімок напряму в пам'ять (у форматі масиву для OpenCV)
        image = picam2.capture_array()

        # Picamera2 віддає колір у форматі RGB, а OpenCV любить BGR. Конвертуємо:
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        # Для пошуку облич алгоритмам легше працювати з чорно-білим зображенням
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

        # 4. Шукаємо обличчя
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )

        print(f"Знайдено облич: {len(faces)}")

        # 5. Малюємо зелений квадрат (0, 255, 0) навколо кожного знайденого обличчя
        for (x, y, w, h) in faces:
            cv2.rectangle(image_bgr, (x, y), (x+w, y+h), (0, 255, 0), 3)

        # 6. Зберігаємо результат
        cv2.imwrite(save_path, image_bgr)
        print(f"Готово! Відкрий {save_path} у VS Code, щоб побачити результат.")

    finally:
        # Завжди вимикаємо камеру
        picam2.stop()
        picam2.close()

if __name__ == "__main__":
    detect_face()