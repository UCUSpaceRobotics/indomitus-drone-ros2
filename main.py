"""Main for drone autonomy."""

import time
import multiprocessing
import queue
import sys

from src.comm.mavlink_node import comm_process_loop, create_command

def main():
    print("🚀 [MAIN] Ініціалізація наземної станції...")
    
    # Створюємо черги для спілкування між процесами
    telemetry_queue = multiprocessing.Queue()
    command_queue = multiprocessing.Queue()

    # 1. Запуск фонового процесу MAVLink
    comm_process = multiprocessing.Process(
        target=comm_process_loop,
        args=(telemetry_queue, command_queue, "/dev/ttyAMA0", 921600),
        daemon=True
    )
    comm_process.start()

    print("⏳ [MAIN] Очікування підключення до Pixhawk (до 10 секунд)...")
    time.sleep(5) # Даємо час на запуск процесу та отримання перших Heartbeat

    try:
        # 2. Зміна режиму (змінюємо GUIDED на STABILIZE)
        print("\n>>> КРОК 1: Перехід у режим STABILIZE...")
        command_queue.put(create_command("set_mode", mode="STABILIZE"))
        time.sleep(2)

        # 3. Армінг (Запуск моторів)
        print("\n>>> КРОК 2: Запит на ARMING (Запуск моторів)...")
        command_queue.put(create_command("arm", state=True))
        time.sleep(4)
        
        # # 4. Зліт (Тестовий)
        # print("\n>>> КРОК 3: Команда TAKEOFF (Зліт на 2 метри)...")
        # command_queue.put(create_command("takeoff", altitude=2.0))

        # 5. Моніторинг телеметрії
        print("\n>>> КРОК 4: Моніторинг телеметрії (15 секунд)...")
        start_time = time.time()
        
        while (time.time() - start_time) < 15.0:
            try:
                # Дістаємо найсвіжіший словник телеметрії
                telem = telemetry_queue.get(timeout=0.1)
                
                # Z-координата в NED йде вниз, тому інвертуємо для зручності
                alt_m = -telem.get('pos_z_m', 0.0)
                mode = telem.get('mode', 'UNKNOWN')
                armed = "ТАК" if telem.get('armed') else "НІ"
                batt = telem.get('battery_voltage_v', 0.0)
                
                # Очищаємо рядок терміналу і друкуємо поверх нього (ефект панелі)
                sys.stdout.write(f"\r[ТЕЛЕМЕТРІЯ] Режим: {mode:^8} | Арм: {armed:^3} | Висота: {alt_m:>5.2f}м | Батарея: {batt:>5.1f}V ")
                sys.stdout.flush()
                
            except queue.Empty:
                pass
                
            time.sleep(0.2) # Оновлення 5 разів на секунду
            
        print() # Перенесення рядка після завершення моніторингу

        # 6. Посадка
        print("\n>>> КРОК 5: Команда LAND (Посадка)...")
        command_queue.put(create_command("set_mode", mode="LAND"))
        time.sleep(3)

    except KeyboardInterrupt:
        print("\n\n🛑 [MAIN] Екстрена зупинка (Ctrl+C)! Вимикаємо мотори...")
        command_queue.put(create_command("set_mode", mode="LAND"))
        command_queue.put(create_command("arm", state=False))
        time.sleep(1)

    finally:
        print("\n🔌 [MAIN] Завершення роботи. Вимкнення процесів...")
        comm_process.terminate()
        comm_process.join()
        print("✅ [MAIN] Програму успішно завершено.")

if __name__ == '__main__':
    main()