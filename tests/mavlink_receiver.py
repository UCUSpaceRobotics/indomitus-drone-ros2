import os
import time

os.environ["MAVLINK20"] = "1"

from pymavlink import mavutil


def decode_command_ack_result(result):
    result_map = {
        mavutil.mavlink.MAV_RESULT_ACCEPTED: "ACCEPTED",
        mavutil.mavlink.MAV_RESULT_TEMPORARILY_REJECTED: "TEMPORARILY_REJECTED",
        mavutil.mavlink.MAV_RESULT_DENIED: "DENIED",
        mavutil.mavlink.MAV_RESULT_UNSUPPORTED: "UNSUPPORTED",
        mavutil.mavlink.MAV_RESULT_FAILED: "FAILED",
        mavutil.mavlink.MAV_RESULT_IN_PROGRESS: "IN_PROGRESS",
    }
    return result_map.get(result, f"UNKNOWN_RESULT_{result}")


def command_name(command_id):
    command_map = {
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM: "ARM/DISARM",
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF: "TAKEOFF",
        mavutil.mavlink.MAV_CMD_NAV_LAND: "LAND",
        mavutil.mavlink.MAV_CMD_DO_SET_MODE: "SET_MODE",
    }
    return command_map.get(command_id, f"COMMAND_{command_id}")


def main():
    connection_string = "udpin:127.0.0.1:14550"

    print(f"[RECEIVER] Listening on {connection_string}")
    mav = mavutil.mavlink_connection(
        connection_string,
        source_system=1,
        source_component=1,
    )

    print("[RECEIVER] Waiting for MAVLink messages...")

    last_heartbeat_sent = 0.0

    while True:
        now = time.time()

        # Optional heartbeat from receiver side
        if now - last_heartbeat_sent >= 1.0:
            mav.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_GCS,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                0,
                0,
                0,
            )
            last_heartbeat_sent = now

        msg = mav.recv_match(blocking=False)

        if msg is None:
            time.sleep(0.01)
            continue

        msg_type = msg.get_type()

        if msg_type == "BAD_DATA":
            continue

        print(f"\n[RECEIVER] Received MAVLink message: {msg_type}")

        if msg_type == "HEARTBEAT":
            print(
                f"  from system={msg.get_srcSystem()}, "
                f"component={msg.get_srcComponent()}"
            )

        elif msg_type == "COMMAND_LONG":
            print(f"  command: {command_name(msg.command)}")
            print(f"  command_id: {msg.command}")
            print(f"  target_system: {msg.target_system}")
            print(f"  target_component: {msg.target_component}")
            print(f"  confirmation: {msg.confirmation}")
            print(f"  params:")
            print(f"    param1: {msg.param1}")
            print(f"    param2: {msg.param2}")
            print(f"    param3: {msg.param3}")
            print(f"    param4: {msg.param4}")
            print(f"    param5: {msg.param5}")
            print(f"    param6: {msg.param6}")
            print(f"    param7: {msg.param7}")

            # Send fake ACK back to sender
            mav.mav.command_ack_send(
                msg.command,
                mavutil.mavlink.MAV_RESULT_ACCEPTED,
            )
            print(f"  ACK sent: {decode_command_ack_result(mavutil.mavlink.MAV_RESULT_ACCEPTED)}")

        elif msg_type == "SET_MODE":
            print("  command: SET_MODE")
            print(f"  target_system: {msg.target_system}")
            print(f"  base_mode: {msg.base_mode}")
            print(f"  custom_mode: {msg.custom_mode}")

        elif msg_type == "SET_POSITION_TARGET_LOCAL_NED":
            print("  command: SET_POSITION_TARGET_LOCAL_NED")
            print(f"  target_system: {msg.target_system}")
            print(f"  target_component: {msg.target_component}")
            print(f"  coordinate_frame: {msg.coordinate_frame}")
            print(f"  type_mask: {msg.type_mask}")
            print(f"  position: x={msg.x}, y={msg.y}, z={msg.z}")
            print(f"  velocity: vx={msg.vx}, vy={msg.vy}, vz={msg.vz}")
            print(f"  acceleration: afx={msg.afx}, afy={msg.afy}, afz={msg.afz}")
            print(f"  yaw: {msg.yaw}")
            print(f"  yaw_rate: {msg.yaw_rate}")

        elif msg_type == "STATUSTEXT":
            text = msg.text.decode("utf-8") if isinstance(msg.text, bytes) else msg.text
            print(f"  text: {text}")

        else:
            print(f"  raw: {msg}")


if __name__ == "__main__":
    main()