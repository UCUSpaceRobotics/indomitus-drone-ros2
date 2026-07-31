#!/usr/bin/env python3
"""
Smoke Test Sender — Phase 2 UDP Bridge Verification
Sends MAVLink commands TO Simulink and verifies the decoder responds.
Run this AFTER smoke_test_receiver.py confirms heartbeats are flowing.
"""

import os
import time
import sys

os.environ["MAVLINK20"] = "1"
from pymavlink import mavutil

# Python SENDS to this address — Simulink's UDP Receive block listens here
CONNECTION = "udpout:127.0.0.1:14550"

def send_and_report(mav, description, send_fn):
    print(f"\n[SEND] {description}")
    send_fn(mav)
    time.sleep(0.3)  # Give Simulink one decode cycle

def main():
    print("=" * 60)
    print("SMOKE TEST — MAVLink UDP Bridge (Python → Simulink)")
    print("=" * 60)
    print(f"[SEND] Connecting to {CONNECTION}")
    print("[SEND] Simulink must already be RUNNING before this script\n")

    mav = mavutil.mavlink_connection(
        CONNECTION,
        source_system=255,
        source_component=0,
    )

    # Send initial heartbeat so Simulink knows our system ID
    print("[SEND] Sending initial GCS heartbeat...")
    mav.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_GCS,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
        0, 0, 0
    )
    time.sleep(0.5)

    # ── Test 1: SET_MODE (GUIDED) ──────────────────────────────
    def send_guided(m):
        m.mav.set_mode_send(
            1,   # target_system
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            4    # GUIDED mode custom_mode = 4 in ArduCopter
        )
    send_and_report(mav, "SET_MODE → GUIDED (msg_id=11, custom_mode=4)", send_guided)

    # ── Test 2: ARM ────────────────────────────────────────────
    def send_arm(m):
        m.mav.command_long_send(
            1, 1,  # target sys, comp
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,     # confirmation
            1,     # param1: 1=arm
            0, 0, 0, 0, 0, 0
        )
    send_and_report(mav, "COMMAND_LONG → ARM (msg_id=76, cmd=400, param1=1)", send_arm)

    # ── Test 3: TAKEOFF ────────────────────────────────────────
    def send_takeoff(m):
        m.mav.command_long_send(
            1, 1,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0, 0, 0, 0, 0, 0,
            1.4    # param7: altitude = 1.4m (your search_altitude_m)
        )
    send_and_report(mav, "COMMAND_LONG → TAKEOFF (msg_id=76, cmd=22, alt=1.4m)", send_takeoff)

    # ── Test 4: SET_POSITION_TARGET (absolute position) ────────
    def send_position(m):
        type_mask = (
            (1 << 3) | (1 << 4) | (1 << 5) |   # ignore velocity
            (1 << 6) | (1 << 7) | (1 << 8) |   # ignore accel
            (1 << 10) | (1 << 11)               # ignore yaw
        )
        m.mav.set_position_target_local_ned_send(
            0,    # time_boot_ms
            1, 1, # target sys, comp
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            type_mask,
            1.0, 0.5, -1.4,  # x, y, z (NED)
            0, 0, 0,         # vx, vy, vz
            0, 0, 0,         # afx, afy, afz
            0, 0             # yaw, yaw_rate
        )
    send_and_report(mav, "SET_POSITION_TARGET_LOCAL_NED (msg_id=84, x=1.0 y=0.5 z=-1.4)", send_position)

    # ── Test 5: VELOCITY command ───────────────────────────────
    def send_velocity(m):
        type_mask = (
            (1 << 0) | (1 << 1) | (1 << 2) |   # ignore position
            (1 << 6) | (1 << 7) | (1 << 8) |   # ignore accel
            (1 << 10) | (1 << 11)               # ignore yaw
        )
        m.mav.set_position_target_local_ned_send(
            0, 1, 1,
            mavutil.mavlink.MAV_FRAME_BODY_NED,
            type_mask,
            0, 0, 0,
            0.5, 0.0, 0.0,   # vx=0.5 forward
            0, 0, 0,
            0, 0
        )
    send_and_report(mav, "SET_POSITION_TARGET → VELOCITY (msg_id=84, vx=0.5)", send_velocity)

    # ── Test 6: LAND ───────────────────────────────────────────
    def send_land(m):
        m.mav.command_long_send(
            1, 1,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0,
            0, 0, 0, 0, 0, 0, 0
        )
    send_and_report(mav, "COMMAND_LONG → LAND (msg_id=76, cmd=21)", send_land)

    print("\n" + "=" * 60)
    print("[SEND] All 6 test commands sent.")
    print("[SEND] Now check MATLAB → open the 'cmd_action' Display block.")
    print("[SEND] Expected sequence of cmd_action values:")
    print("         SET_MODE  → cmd_action = 2")
    print("         ARM       → cmd_action = 1, cmd_armed = 1")
    print("         TAKEOFF   → cmd_action = 3, cmd_z ≈ -1.4")
    print("         POSITION  → cmd_action = 5, cmd_x=1.0 cmd_y=0.5")
    print("         VELOCITY  → cmd_action = 6, cmd_vx=0.5")
    print("         LAND      → cmd_action = 4")
    print("=" * 60)

if __name__ == "__main__":
    main()