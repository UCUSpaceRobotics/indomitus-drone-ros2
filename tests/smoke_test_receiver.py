#!/usr/bin/env python3
"""
Smoke Test Receiver — Phase 2 UDP Bridge Verification
Listens on udpin:127.0.0.1:14550 for MAVLink packets from Simulink.
Prints a clear PASS/FAIL verdict for each expected message type.
"""

import os
import time
import sys

os.environ["MAVLINK20"] = "1"
from pymavlink import mavutil

CONNECTION = "udpin:127.0.0.1:14550"
TIMEOUT_S  = 15.0   # How long to wait before declaring failure

def main():
    print("=" * 60)
    print("SMOKE TEST — MAVLink UDP Bridge (Simulink → Python)")
    print("=" * 60)
    print(f"[RECV] Binding to {CONNECTION} ...")
    print("[RECV] Waiting for Simulink to start sending packets...")
    print("[RECV] (You have 15 seconds before this times out)\n")

    mav = mavutil.mavlink_connection(
        CONNECTION,
        source_system=255,
        source_component=0,
    )

    # Tracking which message types we have received
    received = {
        "HEARTBEAT":          False,
        "LOCAL_POSITION_NED": False,
        "ATTITUDE":           False,
        "SYS_STATUS":         False,
    }

    heartbeat_count  = 0
    position_count   = 0
    start_time       = time.time()
    last_report_time = start_time

    print(f"{'MSG TYPE':<25} {'COUNT':>6}   DETAILS")
    print("-" * 60)

    while True:
        elapsed = time.time() - start_time

        # Timeout check
        if elapsed > TIMEOUT_S:
            print("\n[TIMEOUT] No packets received within 15 seconds.")
            break

        # All expected types received — declare success early
        if all(received.values()):
            print("\n[ALL MESSAGE TYPES CONFIRMED]\n")
            break

        msg = mav.recv_match(blocking=False)
        if msg is None:
            time.sleep(0.01)
            continue

        msg_type = msg.get_type()
        if msg_type == "BAD_DATA":
            print(f"[WARN] BAD_DATA received — CRC mismatch or framing error")
            continue

        if msg_type == "HEARTBEAT":
            heartbeat_count += 1
            received["HEARTBEAT"] = True
            armed_str = "ARMED" if (msg.base_mode & 128) else "DISARMED"
            print(f"{'HEARTBEAT':<25} {heartbeat_count:>6}   "
                  f"type={msg.type} autopilot={msg.autopilot} "
                  f"base_mode={msg.base_mode} [{armed_str}]")

        elif msg_type == "LOCAL_POSITION_NED":
            position_count += 1
            received["LOCAL_POSITION_NED"] = True
            if position_count <= 3 or position_count % 20 == 0:
                print(f"{'LOCAL_POSITION_NED':<25} {position_count:>6}   "
                      f"x={msg.x:.3f} y={msg.y:.3f} z={msg.z:.3f}")

        elif msg_type == "ATTITUDE":
            received["ATTITUDE"] = True
            print(f"{'ATTITUDE':<25} {'✓':>6}   "
                  f"roll={msg.roll:.3f} pitch={msg.pitch:.3f} yaw={msg.yaw:.3f}")

        elif msg_type == "SYS_STATUS":
            received["SYS_STATUS"] = True
            v = msg.voltage_battery / 1000.0
            print(f"{'SYS_STATUS':<25} {'✓':>6}   "
                  f"voltage={v:.2f}V remaining={msg.battery_remaining}%")

    # ── Final Verdict ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SMOKE TEST RESULTS")
    print("=" * 60)
    all_pass = True
    for msg_type, ok in received.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        if not ok:
            all_pass = False
        print(f"  {status}   {msg_type}")

    print("-" * 60)
    if all_pass:
        print("  ✅ OVERALL: BRIDGE IS WORKING — Proceed to Phase 3")
    else:
        print("  ❌ OVERALL: BRIDGE HAS ISSUES — See troubleshooting below")
    print("=" * 60)

if __name__ == "__main__":
    main()