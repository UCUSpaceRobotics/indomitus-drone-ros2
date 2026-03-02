import os
from picamera2 import Picamera2
import time

def take_photo():
    # Шлях, куди збережемо фото (на рівень вище від src, у папку captures)
    save_path = os.path.join(os.path.dirname(__file__), "..", "data", "captures", "test_photo.jpg")

    # Ініціалізуємо камеру
    picam2 = Picamera2()

    try:
        # Запускаємо камеру
        picam2.start()
        print("Камера запущена. Чекаємо 2 секунди для налаштування світла...")
        time.sleep(2)  # Даємо сенсору час налаштувати експозицію

        # Робимо знімок у максимальній якості
        picam2.capture_file(save_path)
        print(f"Успіх! Фото збережено за адресою: {save_path}")

    except Exception as e:
        print(f"Виникла помилка: {e}")

    finally:
        # Обов'язково звільняємо камеру, щоб не було помилки "Device busy" наступного разу
        picam2.stop()
        picam2.close()

if __name__ == "__main__":
    take_photo()