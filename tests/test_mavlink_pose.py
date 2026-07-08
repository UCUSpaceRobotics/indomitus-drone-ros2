import importlib
import sys
import types
import unittest


def install_fake_pymavlink():
    mavlink = types.SimpleNamespace(
        MAVLINK_MSG_ID_LOCAL_POSITION_NED=32,
        MAVLINK_MSG_ID_ATTITUDE=30,
        MAVLINK_MSG_ID_SYS_STATUS=1,
        MAV_CMD_SET_MESSAGE_INTERVAL=511,
        MAV_CMD_COMPONENT_ARM_DISARM=400,
        MAV_CMD_NAV_TAKEOFF=22,
        MAV_CMD_NAV_LAND=21,
        MAV_MODE_FLAG_SAFETY_ARMED=128,
        MAV_MODE_FLAG_CUSTOM_MODE_ENABLED=1,
        MAV_RESULT_ACCEPTED=0,
        MAV_TYPE_GCS=6,
        MAV_AUTOPILOT_INVALID=8,
        MAV_FRAME_BODY_OFFSET_NED=9,
        MAV_FRAME_LOCAL_NED=1,
        MAV_FRAME_BODY_NED=8,
    )
    mavutil = types.SimpleNamespace(
        mavlink=mavlink,
        mavlink_connection=lambda *args, **kwargs: None,
        mode_string_v10=lambda msg: "GUIDED",
    )
    module = types.ModuleType("pymavlink")
    module.mavutil = mavutil
    sys.modules["pymavlink"] = module
    sys.modules["pymavlink.mavutil"] = mavutil


class FakeMav:
    def __init__(self):
        self.command_long_calls = []

    def command_long_send(self, *args):
        self.command_long_calls.append(args)


class FakeConnection:
    target_system = 1
    target_component = 1

    def __init__(self):
        self.mav = FakeMav()


class MavlinkPoseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_pymavlink()
        cls.module = importlib.import_module("src.comm.mavlink_client")

    def new_client(self):
        client = self.module.PixhawkClient.__new__(self.module.PixhawkClient)
        client.connection = FakeConnection()
        client.telemetry = {
            "pos_x_m": 1.0,
            "pos_y_m": 2.0,
            "pos_z_m": -1.0,
            "roll_rad": 0.1,
            "pitch_rad": 0.2,
            "yaw_rad": 0.3,
            "last_local_position_time": 10.0,
            "last_attitude_time": 10.1,
        }
        return client

    def test_pose_stream_request_sends_local_position_and_attitude_intervals(self):
        client = self.new_client()

        client.request_pose_stream(rate_hz=20)

        calls = client.connection.mav.command_long_calls
        self.assertEqual(2, len(calls))
        self.assertEqual(32, calls[0][4])
        self.assertEqual(30, calls[1][4])
        self.assertEqual(50000, calls[0][5])
        self.assertEqual(50000, calls[1][5])

    def test_get_pose_marks_fresh_and_stale(self):
        client = self.new_client()

        fresh = client.get_pose(max_age_s=0.5, now_s=10.3)
        stale = client.get_pose(max_age_s=0.5, now_s=11.0)

        self.assertTrue(fresh["fresh"])
        self.assertFalse(stale["fresh"])
        self.assertEqual(1.0, fresh["pos_x_m"])


if __name__ == "__main__":
    unittest.main()
