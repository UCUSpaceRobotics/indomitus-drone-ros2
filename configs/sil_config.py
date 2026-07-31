# configs/sil_config.py
# Switch between hardware (UART) and SIL (UDP) mode here.

# For SIL testing against Simulink:
CONNECTION_STRING = "udpout:127.0.0.1:14550"
BAUDRATE = None  # Not used for UDP

# For real hardware (RPi 5 → Pixhawk 6C):
# CONNECTION_STRING = "/dev/ttyAMA0"
# BAUDRATE = 921600