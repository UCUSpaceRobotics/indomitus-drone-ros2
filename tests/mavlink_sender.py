#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path

os.environ["MAVLINK20"] = "1"

from pymavlink import mavutil


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.comm.mavlink_client import PixhawkClient


TARGET_SYSTEM = 1
TARGET_COMPONENT = 1


def connect_client(connection_string):
    client = PixhawkClient(connection_string)
    client.send_gcs_heartbeat()
    print("[SENDER] Initial heartbeat sent")

    if not client.wait_for_heartbeat(timeout=2.0):
        print(
            "[SENDER] WARNING: No heartbeat received from receiver; "
            f"using target system={TARGET_SYSTEM}, component={TARGET_COMPONENT}"
        )
        client.connection.target_system = TARGET_SYSTEM
        client.connection.target_component = TARGET_COMPONENT

    return client


def send_set_mode(client, mode_name):
    if not client.set_mode(mode_name):
        print(f"[SENDER] Could not send mode {mode_name}; mode mapping is unavailable")


def read_ack_nonblocking(client):
    while True:
        msg = client.connection.recv_match(type="COMMAND_ACK", blocking=False)

        if msg is None:
            break

        print(
            f"[SENDER] Received ACK: command={msg.command}, "
            f"result={msg.result}"
        )


def print_menu():
    print()
    print("======== MAVLink Keyboard Sender ========")
    print("g  -> set mode GUIDED")
    print("l  -> send LAND command")
    print("a  -> arm")
    print("d  -> disarm")
    print("t  -> liftoff 2m")
    print("w  -> move forward 1m")
    print("s  -> move backward 1m")
    print("q  -> move left 1m")
    print("e  -> move right 1m")
    print("r  -> move up 1m")
    print("f  -> move down 1m")
    print("i  -> velocity forward 0.5 m/s")
    print("k  -> velocity backward 0.5 m/s")
    print("j  -> velocity left 0.5 m/s")
    print("o  -> velocity right 0.5 m/s")
    print("p  -> position target LOCAL_NED x=0 y=0 z=-1 once")
    print("h  -> hold LOCAL_NED x=0 y=0 z=-1 for 5s at 5Hz")
    print("x  -> exit")
    print("=========================================")
    print()


def main():
    connection_string = "udpout:127.0.0.1:14550"

    print(f"[SENDER] Connecting to {connection_string}")
    client = connect_client(connection_string)
    last_heartbeat_time = time.time()

    print_menu()

    while True:
        now = time.time()

        if now - last_heartbeat_time >= 1.0:
            client.send_gcs_heartbeat()
            last_heartbeat_time = now

        read_ack_nonblocking(client)

        key = input("Press command key: ").strip().lower()

        if key == "x":
            print("[SENDER] Exiting")
            break

        elif key == "g":
            send_set_mode(client, "GUIDED")

        elif key == "l":
            client.land()

        elif key == "a":
            client.arm(state=True)

        elif key == "d":
            client.arm(state=False)

        elif key == "t":
            client.liftoff(altitude_m=2.0)

        elif key == "w":
            client.send_position_target_local_ned(dx_m=1.0, dy_m=0.0, dz_m=0.0)

        elif key == "s":
            client.send_position_target_local_ned(dx_m=-1.0, dy_m=0.0, dz_m=0.0)

        elif key == "q":
            client.send_position_target_local_ned(dx_m=0.0, dy_m=-1.0, dz_m=0.0)

        elif key == "e":
            client.send_position_target_local_ned(dx_m=0.0, dy_m=1.0, dz_m=0.0)

        elif key == "r":
            client.send_position_target_local_ned(dx_m=0.0, dy_m=0.0, dz_m=-1.0)

        elif key == "f":
            client.send_position_target_local_ned(dx_m=0.0, dy_m=0.0, dz_m=1.0)

        elif key == "i":
            client.send_velocity_target_body_ned(vx_m_s=0.5, vy_m_s=0.0, vz_m_s=0.0)

        elif key == "k":
            client.send_velocity_target_body_ned(vx_m_s=-0.5, vy_m_s=0.0, vz_m_s=0.0)

        elif key == "j":
            client.send_velocity_target_body_ned(vx_m_s=0.0, vy_m_s=-0.5, vz_m_s=0.0)

        elif key == "o":
            client.send_velocity_target_body_ned(vx_m_s=0.0, vy_m_s=0.5, vz_m_s=0.0)

        elif key == "p":
            client.send_local_ned_position_target(x_m=0.0, y_m=0.0, z_m=-1.0)

        elif key == "h":
            sent_count = client.hold_local_ned_position(
                x_m=0.0,
                y_m=0.0,
                z_m=-1.0,
                rate_hz=5.0,
                duration_s=5.0,
            )
            print(f"[SENDER] Hold finished after {sent_count} packets")

        else:
            print(f"[SENDER] Unknown key: {key}")
            print_menu()

        time.sleep(0.05)


if __name__ == "__main__":
    main()
