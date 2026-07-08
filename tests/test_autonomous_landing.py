import math
import unittest
from dataclasses import dataclass

from src.comm.mavlink_node import dispatch_command
from src.navigation.mission_config import MissionConfig
from src.navigation.state_machine import (
    AutonomousLandingMission,
    CenteringStability,
    MissionState,
    generate_search_waypoints,
)


@dataclass
class Detection:
    marker_id: int
    tvec: tuple[float, float, float]
    has_pose: bool = True


class FakeClient:
    def __init__(self):
        self.calls = []

    def arm(self, state=True):
        self.calls.append(("arm", state))

    def set_mode(self, mode_name="GUIDED"):
        self.calls.append(("set_mode", mode_name))

    def takeoff(self, altitude_m):
        self.calls.append(("takeoff", altitude_m))

    def land(self):
        self.calls.append(("land",))

    def send_position_target_local_ned(self, dx_m, dy_m, dz_m):
        self.calls.append(("move_local_pos", dx_m, dy_m, dz_m))

    def send_local_ned_position_target(self, x_m, y_m, z_m):
        self.calls.append(("set_local_position", x_m, y_m, z_m))

    def send_velocity_target_body_ned(self, vx_m_s, vy_m_s, vz_m_s):
        self.calls.append(("move_local_vel", vx_m_s, vy_m_s, vz_m_s))


class AutonomousLandingTest(unittest.TestCase):
    def test_start_emits_guided_arm_and_takeoff_commands(self):
        mission = AutonomousLandingMission()

        commands = mission.start()

        self.assertEqual(MissionState.TAKEOFF, mission.state)
        self.assertEqual(["set_mode", "arm", "takeoff"], [cmd["action"] for cmd in commands])
        self.assertEqual("GUIDED", commands[0]["mode"])
        self.assertTrue(commands[1]["state"])
        self.assertEqual(mission.config.search_altitude_m, commands[2]["altitude"])

    def test_search_waypoints_stay_inside_mission_radius(self):
        for x_m, y_m in generate_search_waypoints(radius_m=3.0):
            self.assertLessEqual(math.hypot(x_m, y_m), 3.000001)

    def test_hard_safety_radius_aborts_to_land(self):
        mission = AutonomousLandingMission()
        mission.state = MissionState.SEARCH

        commands = mission.update({"pos_x_m": 5.1, "pos_y_m": 0.0, "pos_z_m": -1.4})

        self.assertEqual(MissionState.ABORT_LAND, mission.state)
        self.assertEqual("land", commands[0]["action"])

    def test_centering_requires_tolerance_for_stable_time(self):
        stable = CenteringStability(tolerance_m=0.08, stable_time_s=0.7)

        self.assertFalse(stable.update((0.04, 0.02), now_s=10.0))
        self.assertFalse(stable.update((0.04, 0.02), now_s=10.6))
        self.assertTrue(stable.update((0.04, 0.02), now_s=10.8))
        self.assertFalse(stable.update((0.09, 0.0), now_s=10.9))

    def test_centering_locks_pixhawk_xy_before_descent(self):
        mission = AutonomousLandingMission()
        mission.state = MissionState.CENTER_ON_LANDING_MARKER
        telemetry = {"pos_x_m": 1.2, "pos_y_m": -0.4, "pos_z_m": -1.4}
        detection = Detection(marker_id=14, tvec=(0.01, 0.02, 1.4))

        mission.update(telemetry, [detection], now_s=0.0)
        commands = mission.update(telemetry, [detection], now_s=0.8)

        self.assertEqual(MissionState.CAMERA_VERIFIED_DESCENT, mission.state)
        self.assertEqual("set_local_position", commands[0]["action"])
        self.assertEqual(1.2, commands[0]["x"])
        self.assertEqual(-0.4, commands[0]["y"])

    def test_descent_recenters_above_recenter_tolerance(self):
        mission = AutonomousLandingMission()
        mission.state = MissionState.CAMERA_VERIFIED_DESCENT
        mission._locked_xy = (0.0, 0.0)
        mission._target_z_m = -1.0
        detection = Detection(marker_id=14, tvec=(0.0, 0.13, 1.0))

        commands = mission.update({"pos_x_m": 0.0, "pos_y_m": 0.0}, [detection], now_s=1.0)

        self.assertEqual(MissionState.CENTER_ON_LANDING_MARKER, mission.state)
        self.assertEqual("move_local_vel", commands[0]["action"])

    def test_descent_continues_with_locked_xy_when_marker_stays_centered(self):
        mission = AutonomousLandingMission()
        mission.state = MissionState.CAMERA_VERIFIED_DESCENT
        mission._locked_xy = (1.0, 2.0)
        mission._target_z_m = -1.0
        detection = Detection(marker_id=14, tvec=(0.01, 0.01, 1.0))

        commands = mission.update({"pos_x_m": 1.0, "pos_y_m": 2.0}, [detection], now_s=1.0)

        self.assertEqual(MissionState.CAMERA_VERIFIED_DESCENT, mission.state)
        self.assertEqual("set_local_position", commands[0]["action"])
        self.assertEqual(1.0, commands[0]["x"])
        self.assertEqual(2.0, commands[0]["y"])
        self.assertGreater(commands[0]["z"], -1.0)

    def test_descent_aborts_above_abort_tolerance(self):
        mission = AutonomousLandingMission()
        mission.state = MissionState.CAMERA_VERIFIED_DESCENT
        mission._locked_xy = (0.0, 0.0)
        detection = Detection(marker_id=14, tvec=(0.0, 0.26, 1.0))

        commands = mission.update({"pos_x_m": 0.0, "pos_y_m": 0.0}, [detection], now_s=1.0)

        self.assertEqual(MissionState.ABORT_LAND, mission.state)
        self.assertEqual("land", commands[0]["action"])

    def test_marker_loss_timeout_returns_to_centering(self):
        config = MissionConfig(marker_loss_timeout_s=1.0)
        mission = AutonomousLandingMission(config)
        mission.state = MissionState.CAMERA_VERIFIED_DESCENT
        mission._locked_xy = (0.0, 0.0)
        mission._target_z_m = -1.0
        mission._last_marker_seen_s = 1.0

        mission.update({"pos_x_m": 0.0, "pos_y_m": 0.0}, [], now_s=2.2)

        self.assertEqual(MissionState.CENTER_ON_LANDING_MARKER, mission.state)

    def test_command_dispatch_supports_landing_and_absolute_position(self):
        client = FakeClient()

        dispatch_command(client, {"action": "land"})
        dispatch_command(client, {"action": "set_local_position", "x": 1.0, "y": 2.0, "z": -1.0})

        self.assertEqual(("land",), client.calls[0])
        self.assertEqual(("set_local_position", 1.0, 2.0, -1.0), client.calls[1])


if __name__ == "__main__":
    unittest.main()
