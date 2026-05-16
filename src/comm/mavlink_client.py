import time
from pymavlink import mavutil

class PixhawkClient:
    """
    Low-level MAVLink communication client for ArduPilot (Pixhawk).
    Handles direct serial connection, telemetry parsing, and command dispatching.
    """

    def __init__(self, connection_string="/dev/ttyAMA0", baudrate=921600):
        """
        Initializes the serial connection to the Pixhawk.
        """
        print(f"[COMM] Initializing MAVLink connection on {connection_string} @ {baudrate}...")
        
        # We set source_system=255 and source_component=0 to identify this RPi as a GCS 
        # (Ground Control Station). This is crucial for the Pixhawk's failsafe logic.
        self.connection = mavutil.mavlink_connection(
            connection_string, 
            baud=baudrate,
            source_system=255, 
            source_component=0
        )
        
        # Internal state dictionary to hold the latest telemetry
        self.telemetry = {
            "connected": False,
            "armed": False,
            "mode": "UNKNOWN",
            "battery_voltage_v": 0.0,
            "battery_remaining_pct": 0,
            "pos_x_m": 0.0,  # Local North
            "pos_y_m": 0.0,  # Local East
            "pos_z_m": 0.0,  # Local Down (Negative is UP)
            "roll_rad": 0.0,
            "pitch_rad": 0.0,
            "yaw_rad": 0.0,
            "last_heartbeat_time": 0.0
        }

    def wait_for_heartbeat(self, timeout=10.0):
        """
        Blocks execution until the first heartbeat is received from the Pixhawk.
        This establishes the target_system and target_component IDs.
        """
        print("[COMM] Waiting for Pixhawk heartbeat...")
        msg = self.connection.wait_heartbeat(timeout=timeout)
        
        if msg:
            print(f"[COMM] Heartbeat received! Target System: {self.connection.target_system}, Component: {self.connection.target_component}")
            self.telemetry["connected"] = True
            self.telemetry["last_heartbeat_time"] = time.time()
            return True
        else:
            print("[COMM] ERROR: Timeout waiting for heartbeat.")
            return False

    def request_data_streams(self, rate_hz=10):
        """
        Requests the Pixhawk to stream specific data packets at a given frequency.
        """
        print(f"[COMM] Requesting telemetry streams at {rate_hz} Hz...")
        
        # Dictionary of Message IDs to request
        # 32: LOCAL_POSITION_NED, 30: ATTITUDE, 1: SYS_STATUS (Battery/Errors)
        messages_to_request = [
            mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED,
            mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE,
            mavutil.mavlink.MAVLINK_MSG_ID_SYS_STATUS
        ]

        for msg_id in messages_to_request:
            self.connection.mav.command_long_send(
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                0,       # Confirmation
                msg_id,  # Param 1: Message ID
                int(1e6 / rate_hz), # Param 2: Interval in microseconds
                0, 0, 0, 0, 0 # Params 3-7 (unused)
            )

    def send_gcs_heartbeat(self):
        """
        Sends a heartbeat FROM the Raspberry Pi TO the Pixhawk.
        Must be called at least 1Hz to prevent ArduPilot from triggering GCS Failsafe (RTL/LAND).
        """
        self.connection.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0, 0, 0
        )

    def get_telemetry_tick(self):
        """
        Non-blocking read of the MAVLink buffer. Parses incoming messages 
        and updates the internal telemetry dictionary.
        Returns the updated dictionary.
        """
        # Read all available messages in the buffer (non-blocking loop)
        while True:
            msg = self.connection.recv_match(blocking=False)
            if msg is None:
                break # Buffer is empty, exit loop
            
            msg_type = msg.get_type()

            if msg_type == "HEARTBEAT":
                self.telemetry["last_heartbeat_time"] = time.time()
                self.telemetry["armed"] = msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
                self.telemetry["mode"] = mavutil.mode_string_v10(msg)
                
            elif msg_type == "LOCAL_POSITION_NED":
                self.telemetry["pos_x_m"] = msg.x
                self.telemetry["pos_y_m"] = msg.y
                self.telemetry["pos_z_m"] = msg.z
                
            elif msg_type == "ATTITUDE":
                self.telemetry["roll_rad"] = msg.roll
                self.telemetry["pitch_rad"] = msg.pitch
                self.telemetry["yaw_rad"] = msg.yaw
                
            elif msg_type == "SYS_STATUS":
                self.telemetry["battery_voltage_v"] = msg.voltage_battery / 1000.0
                self.telemetry["battery_remaining_pct"] = msg.battery_remaining

        return self.telemetry

    # -------------------------------------------------------------------------
    # COMMAND METHODS (ACTIONS)
    # -------------------------------------------------------------------------

    def set_mode(self, mode_name="GUIDED"):
        """
        Changes the flight mode (e.g., 'GUIDED', 'RTL', 'LAND').
        """
        if mode_name not in self.connection.mode_mapping():
            print(f"[COMM] ERROR: Unknown flight mode '{mode_name}'")
            return False

        mode_id = self.connection.mode_mapping()[mode_name]
        
        self.connection.mav.set_mode_send(
            self.connection.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id
        )
        print(f"[COMM] Command sent: Change mode to {mode_name}")
        return True

    def arm(self, state=True, timeout=3.0):
        """
        Arms or disarms the motors and waits for confirmation from the Pixhawk.
        Captures and prints any Pre-Arm failure messages (STATUSTEXT).
        
        Parameters:
        state (bool): True to ARM, False to DISARM.
        timeout (float): Maximum time in seconds to wait for acknowledgment.
        
        Returns:
        bool: True if the command was accepted, False if rejected or timed out.
        """
        arm_val = 1 if state else 0
        action = "ARM" if state else "DISARM"
        print(f"[COMM] Sending {action} command...")

        # 1. Send the command
        self.connection.mav.command_long_send(
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,       # Confirmation
            arm_val, # Param 1: 1 to arm, 0 to disarm
            0, 0, 0, 0, 0, 0 # Params 2-7 (unused)
        )

        # 2. Wait for acknowledgment and catch status texts
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            # Read the next message in the buffer without blocking
            msg = self.connection.recv_match(blocking=False)
            
            if msg is None:
                time.sleep(0.01) # Tiny pause to prevent 100% CPU usage
                continue

            msg_type = msg.get_type()

            # Catch Pixhawk text messages (e.g., Pre-Arm errors)
            if msg_type == "STATUSTEXT":
                text = msg.text.decode('utf-8') if isinstance(msg.text, bytes) else msg.text
                print(f"[PIXHAWK MSG]: {text}")

            # Catch the Command Acknowledgment
            elif msg_type == "COMMAND_ACK":
                # Check if this ACK is specifically for our ARM_DISARM command
                if msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
                    if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                        print(f"[COMM] SUCCESS: Drone is now {action}ED.")
                        self.telemetry["armed"] = state # Update internal state
                        return True
                    else:
                        print(f"[COMM] ERROR: {action} command rejected! (MAV_RESULT code: {msg.result})")
                        return False

        # 3. Timeout handling
        print(f"[COMM] TIMEOUT: No acknowledgment received for {action} command after {timeout}s.")
        return False

    def takeoff(self, altitude_m):
        """
        Commands the drone to take off to a specified relative altitude.
        Drone MUST be armed and in GUIDED mode before sending this.
        """
        self.connection.mav.command_long_send(
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0, # Confirmation
            0, 0, 0, 0, 0, 0, 
            altitude_m # Param 7: Altitude in meters
        )
        print(f"[COMM] Command sent: TAKEOFF to {altitude_m}m")

    def send_position_target_local_ned(self, dx_m, dy_m, dz_m):
        """
        Moves the drone relative to its CURRENT position and heading.
        
        Parameters:
        dx_m: Move Forward (positive) or Backward (negative) in meters.
        dy_m: Move Right (positive) or Left (negative) in meters.
        dz_m: Move DOWN (positive) or UP (negative) in meters.
        """
        # Type mask: 0b0000_11_01_1111_1000 (0x0DF8)
        # We set bits to 1 to IGNORE them. We ignore Velocity, Acceleration, and Yaw.
        # We set bits to 0 to USE them. We use Position (x, y, z).
        type_mask = int(0b0000110111111000)

        self.connection.mav.set_position_target_local_ned_send(
            0, # time_boot_ms (not used)
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED, # Relative to current drone body
            type_mask,
            dx_m, dy_m, dz_m, # Position
            0, 0, 0,          # Velocity (Ignored by mask)
            0, 0, 0,          # Acceleration (Ignored by mask)
            0, 0              # Yaw, Yaw rate (Ignored by mask)
        )
        print(f"[COMM] Command sent: MOVE Local [dx:{dx_m}, dy:{dy_m}, dz:{dz_m}]")
    
    def send_velocity_target_body_ned(self, vx_m_s, vy_m_s, vz_m_s):
        """
        Commands the drone to move at a specific velocity relative to its own body.
        Perfect for visual servoing (tracking markers/objects).
        
        Parameters:
        vx_m_s: Forward (+) / Backward (-) speed in m/s.
        vy_m_s: Right (+) / Left (-) speed in m/s.
        vz_m_s: Down (+) / Up (-) speed in m/s.
        """
        # Type mask: 0b0000_11_01_1100_0111 (0x0DC7)
        # 1 means IGNORE, 0 means USE.
        # We ignore Position (bits 0,1,2), Acceleration (bits 6,7,8), and Yaw (bits 10,11).
        # We USE Velocity (bits 3,4,5).
        type_mask = int(0b0000110111000111)

        self.connection.mav.set_position_target_local_ned_send(
            0, # time_boot_ms (not used)
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_NED, # Velocity relative to drone's heading
            type_mask,
            0, 0, 0,                # Position (Ignored)
            vx_m_s, vy_m_s, vz_m_s, # Velocity in m/s (USED)
            0, 0, 0,                # Acceleration (Ignored)
            0, 0                    # Yaw, Yaw rate (Ignored)
        )
        print(f"[COMM] Command sent: VELOCITY [vx:{vx_m_s}, vy:{vy_m_s}, vz:{vz_m_s}] m/s")