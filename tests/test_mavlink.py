import time
import queue
import multiprocessing as mp


COMMAND_MAX_AGE_SEC = 0.5
TELEMETRY_PUBLISH_RATE_HZ = 10.0
GCS_HEARTBEAT_INTERVAL_SEC = 1.0


def create_command(action, **kwargs):
    """
    Same command format as your real comm node.
    """
    command = {
        "action": action,
        "timestamp": time.time(),
    }
    command.update(kwargs)
    return command


class FakePixhawkClient:
    """
    Fake Pixhawk client for testing the command pipeline without hardware.
    It prints every command that would normally be sent through MAVLink.
    """

    def __init__(self):
        self.telemetry = {
            "connected": True,
            "armed": False,
            "mode": "UNKNOWN",
            "battery_voltage_v": 12.1,
            "battery_remaining_pct": 95,
            "pos_x_m": 0.0,
            "pos_y_m": 0.0,
            "pos_z_m": 0.0,
            "roll_rad": 0.0,
            "pitch_rad": 0.0,
            "yaw_rad": 0.0,
            "last_heartbeat_time": time.time(),
        }

    def wait_for_heartbeat(self, timeout=15.0):
        print("[FAKE_PIXHAWK] Heartbeat received")
        return True

    def request_data_streams(self, rate_hz=10):
        print(f"[FAKE_PIXHAWK] Requesting fake telemetry streams at {rate_hz} Hz")

    def send_gcs_heartbeat(self):
        print("[FAKE_PIXHAWK] GCS heartbeat sent")

    def get_telemetry_tick(self):
        """
        Simulate changing telemetry.
        """
        self.telemetry["last_heartbeat_time"] = time.time()
        return self.telemetry

    def arm(self, state=True):
        self.telemetry["armed"] = state
        print(f"[FAKE_PIXHAWK] ARM command received: state={state}")
        return True

    def set_mode(self, mode_name="GUIDED"):
        self.telemetry["mode"] = mode_name
        print(f"[FAKE_PIXHAWK] SET_MODE command received: mode={mode_name}")
        return True

    def takeoff(self, altitude_m):
        print(f"[FAKE_PIXHAWK] TAKEOFF command received: altitude={altitude_m} m")

    def land(self):
        print("[FAKE_PIXHAWK] LAND command received")

    def send_position_target_local_ned(self, dx_m, dy_m, dz_m):
        print(
            "[FAKE_PIXHAWK] MOVE_LOCAL_POS command received: "
            f"dx={dx_m}, dy={dy_m}, dz={dz_m}"
        )

    def send_local_ned_position_target(self, x_m, y_m, z_m):
        print(
            "[FAKE_PIXHAWK] SET_LOCAL_POSITION command received: "
            f"x={x_m}, y={y_m}, z={z_m}"
        )

    def send_velocity_target_body_ned(self, vx_m_s, vy_m_s, vz_m_s):
        print(
            "[FAKE_PIXHAWK] MOVE_LOCAL_VEL command received: "
            f"vx={vx_m_s}, vy={vy_m_s}, vz={vz_m_s}"
        )


def comm_process_loop_test(telemetry_queue, command_queue, runtime_s=5.0):
    """
    Test version of your comm_process_loop.

    Instead of connecting to real Pixhawk hardware, it uses FakePixhawkClient.
    It receives commands from command_queue and prints what would be executed.
    """

    print("[COMM_NODE_TEST] Starting fake MAVLink communication process")

    client = FakePixhawkClient()

    if not client.wait_for_heartbeat(timeout=15.0):
        print("[COMM_NODE_TEST] Fake Pixhawk not responding")
        return

    client.request_data_streams(rate_hz=10)

    last_heartbeat_time = 0.0
    last_telemetry_pub_time = 0.0
    telemetry_interval_sec = 1.0 / TELEMETRY_PUBLISH_RATE_HZ

    start_time = time.time()

    print("[COMM_NODE_TEST] Entering test operation loop")

    while time.time() - start_time < runtime_s:
        current_time = time.time()

        # A. Fake GCS heartbeat
        if current_time - last_heartbeat_time >= GCS_HEARTBEAT_INTERVAL_SEC:
            client.send_gcs_heartbeat()
            last_heartbeat_time = current_time

        # B. Fake telemetry
        current_telemetry = client.get_telemetry_tick()

        if current_time - last_telemetry_pub_time >= telemetry_interval_sec:
            while not telemetry_queue.empty():
                try:
                    telemetry_queue.get_nowait()
                except queue.Empty:
                    break

            telemetry_queue.put_nowait(current_telemetry.copy())
            last_telemetry_pub_time = current_time

        # C. Receive and print commands
        while not command_queue.empty():
            try:
                cmd = command_queue.get_nowait()
            except queue.Empty:
                break

            cmd_timestamp = cmd.get("timestamp", 0.0)
            cmd_age = current_time - cmd_timestamp

            if cmd_age > COMMAND_MAX_AGE_SEC:
                print(
                    f"[COMM_NODE_TEST] WARNING: Dropped stale command "
                    f"'{cmd.get('action')}' age={cmd_age:.3f}s"
                )
                continue

            action = cmd.get("action")
            print(f"[COMM_NODE_TEST] Received command: {cmd}")

            if action == "arm":
                client.arm(state=cmd.get("state", True))

            elif action == "set_mode":
                client.set_mode(mode_name=cmd.get("mode", "GUIDED"))

            elif action == "takeoff":
                client.takeoff(altitude_m=cmd.get("altitude", 2.0))

            elif action == "land":
                client.land()

            elif action == "move_local_pos":
                client.send_position_target_local_ned(
                    dx_m=cmd.get("dx", 0.0),
                    dy_m=cmd.get("dy", 0.0),
                    dz_m=cmd.get("dz", 0.0),
                )

            elif action == "set_local_position":
                client.send_local_ned_position_target(
                    x_m=cmd.get("x", 0.0),
                    y_m=cmd.get("y", 0.0),
                    z_m=cmd.get("z", 0.0),
                )

            elif action == "move_local_vel":
                client.send_velocity_target_body_ned(
                    vx_m_s=cmd.get("vx", 0.0),
                    vy_m_s=cmd.get("vy", 0.0),
                    vz_m_s=cmd.get("vz", 0.0),
                )

            else:
                print(f"[COMM_NODE_TEST] ERROR: Unknown command action: {action}")

        time.sleep(0.005)

    print("[COMM_NODE_TEST] Test loop finished")


def command_sender(command_queue):
    """
    Simulates your navigation/state-machine side.
    Sends commands into the command queue.
    """

    test_commands = [
        create_command("set_mode", mode="GUIDED"),
        create_command("arm", state=True),
        create_command("takeoff", altitude=2.0),
        create_command("move_local_pos", dx=1.0, dy=0.0, dz=0.0),
        create_command("move_local_pos", dx=0.0, dy=1.0, dz=0.0),
        create_command("set_local_position", x=1.0, y=1.0, z=-1.4),
        create_command("move_local_vel", vx=0.5, vy=0.0, vz=0.0),
        create_command("land"),
        create_command("arm", state=False),
    ]

    for cmd in test_commands:
        print(f"[COMMAND_SENDER] Sending command: {cmd}")
        command_queue.put(cmd)
        time.sleep(0.2)


def telemetry_reader(telemetry_queue, runtime_s=5.0):
    """
    Reads telemetry published by the comm node.
    """

    start_time = time.time()

    while time.time() - start_time < runtime_s:
        try:
            telemetry = telemetry_queue.get(timeout=0.5)
            print(f"[TELEMETRY_READER] Latest telemetry: {telemetry}")
        except queue.Empty:
            pass


if __name__ == "__main__":
    telemetry_queue = mp.Queue()
    command_queue = mp.Queue()

    comm_process = mp.Process(
        target=comm_process_loop_test,
        args=(telemetry_queue, command_queue),
        kwargs={"runtime_s": 6.0},
    )

    telemetry_process = mp.Process(
        target=telemetry_reader,
        args=(telemetry_queue,),
        kwargs={"runtime_s": 6.0},
    )

    comm_process.start()
    telemetry_process.start()

    command_sender(command_queue)

    comm_process.join()
    telemetry_process.join()

    print("[MAIN] Pipeline test complete")