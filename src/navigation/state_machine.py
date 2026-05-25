import math
from enum import Enum

from src.comm.mavlink_node import create_command
from src.navigation.mission_config import MissionConfig


class MissionState(str, Enum):
    IDLE = "IDLE"
    TAKEOFF = "TAKEOFF"
    SEARCH = "SEARCH"
    CENTER_ON_LANDING_MARKER = "CENTER_ON_LANDING_MARKER"
    CAMERA_VERIFIED_DESCENT = "CAMERA_VERIFIED_DESCENT"
    LAND = "LAND"
    ABORT_LAND = "ABORT_LAND"


def local_radius_m(telemetry):
    return math.hypot(
        float(telemetry.get("pos_x_m", 0.0)),
        float(telemetry.get("pos_y_m", 0.0)),
    )


def generate_search_waypoints(radius_m=3.0, spacing_m=0.75):
    waypoints = [(0.0, 0.0)]
    step = 1
    x = 0.0
    y = 0.0
    directions = ((1, 0), (0, 1), (-1, 0), (0, -1))

    while True:
        added = False
        for direction_index, (dx, dy) in enumerate(directions):
            for _ in range(step):
                x += dx * spacing_m
                y += dy * spacing_m
                clamped = clamp_to_radius(x, y, radius_m)
                if clamped not in waypoints:
                    waypoints.append(clamped)
                    added = True
            if direction_index % 2 == 1:
                step += 1
        if not added or step * spacing_m > radius_m * 3.0:
            break
        if len(waypoints) > 80:
            break

    return waypoints


def clamp_to_radius(x_m, y_m, radius_m):
    distance = math.hypot(x_m, y_m)
    if distance <= radius_m or distance == 0.0:
        return (round(x_m, 6), round(y_m, 6))
    scale = radius_m / distance
    return (round(x_m * scale, 6), round(y_m * scale, 6))


def marker_body_offset_m(detection):
    if detection is None or not getattr(detection, "has_pose", False):
        return None
    tvec = detection.tvec
    return (float(tvec[1]), float(tvec[0]))


def offset_norm_m(offset):
    return math.hypot(offset[0], offset[1])


class CenteringStability:
    def __init__(self, tolerance_m, stable_time_s):
        self.tolerance_m = tolerance_m
        self.stable_time_s = stable_time_s
        self._started_at = None

    def update(self, offset_m, now_s):
        if offset_m is None or offset_norm_m(offset_m) > self.tolerance_m:
            self._started_at = None
            return False
        if self._started_at is None:
            self._started_at = now_s
            return False
        return now_s - self._started_at >= self.stable_time_s

    def reset(self):
        self._started_at = None


class AutonomousLandingMission:
    def __init__(self, config=None):
        self.config = config or MissionConfig()
        self.state = MissionState.IDLE
        self.search_waypoints = generate_search_waypoints(self.config.mission_radius_m)
        self._waypoint_index = 0
        self._centering = CenteringStability(
            self.config.center_tolerance_m,
            self.config.center_stable_time_s,
        )
        self._locked_xy = None
        self._target_z_m = -self.config.search_altitude_m
        self._last_marker_seen_s = None

    def start(self):
        self.state = MissionState.TAKEOFF
        return [
            create_command("set_mode", mode="GUIDED"),
            create_command("arm", state=True),
            create_command("takeoff", altitude=self.config.search_altitude_m),
        ]

    def update(self, telemetry, detections=None, now_s=None):
        now_s = now_s if now_s is not None else self._time()
        detections = detections or []

        if local_radius_m(telemetry) > self.config.hard_safety_radius_m:
            self.state = MissionState.ABORT_LAND
            return [create_command("land")]

        landing_detection = self._find_detection(detections, self.config.landing_marker_id)
        origin_detection = self._find_detection(detections, self.config.origin_marker_id)
        if origin_detection is not None:
            self._log_origin_pose_error(origin_detection, telemetry)

        if self.state == MissionState.IDLE:
            return []
        if self.state == MissionState.TAKEOFF:
            return self._update_takeoff(telemetry)
        if self.state == MissionState.SEARCH:
            return self._update_search(telemetry, landing_detection)
        if self.state == MissionState.CENTER_ON_LANDING_MARKER:
            return self._update_centering(telemetry, landing_detection, now_s)
        if self.state == MissionState.CAMERA_VERIFIED_DESCENT:
            return self._update_descent(telemetry, landing_detection, now_s)
        return []

    def _update_takeoff(self, telemetry):
        altitude_m = -float(telemetry.get("pos_z_m", 0.0))
        if altitude_m < self.config.search_altitude_m * 0.8:
            return []
        self.state = MissionState.SEARCH
        return [self._search_waypoint_command()]

    def _update_search(self, telemetry, landing_detection):
        if marker_body_offset_m(landing_detection) is not None:
            self.state = MissionState.CENTER_ON_LANDING_MARKER
            self._centering.reset()
            return [self._zero_body_velocity_command()]

        target_x, target_y = self.search_waypoints[self._waypoint_index]
        dx = target_x - float(telemetry.get("pos_x_m", 0.0))
        dy = target_y - float(telemetry.get("pos_y_m", 0.0))
        if math.hypot(dx, dy) <= self.config.waypoint_acceptance_m:
            self._waypoint_index = (self._waypoint_index + 1) % len(self.search_waypoints)
        return [self._search_waypoint_command()]

    def _update_centering(self, telemetry, landing_detection, now_s):
        offset = marker_body_offset_m(landing_detection)
        if offset is None:
            self._centering.reset()
            return [self._zero_body_velocity_command()]

        if self._centering.update(offset, now_s):
            self._locked_xy = (
                float(telemetry.get("pos_x_m", 0.0)),
                float(telemetry.get("pos_y_m", 0.0)),
            )
            self._target_z_m = float(telemetry.get("pos_z_m", -self.config.search_altitude_m))
            self._last_marker_seen_s = now_s
            self.state = MissionState.CAMERA_VERIFIED_DESCENT
            return [self._descent_hold_command()]

        forward_m_s = self._clamp(-offset[0] * self.config.center_gain)
        right_m_s = self._clamp(-offset[1] * self.config.center_gain)
        return [create_command("move_local_vel", vx=forward_m_s, vy=right_m_s, vz=0.0)]

    def _update_descent(self, telemetry, landing_detection, now_s):
        offset = marker_body_offset_m(landing_detection)
        if offset is None:
            if self._last_marker_seen_s is None:
                self._last_marker_seen_s = now_s
            if now_s - self._last_marker_seen_s > self.config.marker_loss_timeout_s:
                self.state = MissionState.CENTER_ON_LANDING_MARKER
                self._centering.reset()
            return [self._descent_hold_command()]

        self._last_marker_seen_s = now_s
        distance = offset_norm_m(offset)
        if distance > self.config.abort_tolerance_m:
            self.state = MissionState.ABORT_LAND
            return [create_command("land")]
        if distance > self.config.recenter_tolerance_m:
            self.state = MissionState.CENTER_ON_LANDING_MARKER
            self._centering.reset()
            return [self._zero_body_velocity_command()]

        self._target_z_m = min(
            self._target_z_m + self.config.descent_step_m,
            -self.config.land_altitude_m,
        )
        if -self._target_z_m <= self.config.land_altitude_m:
            self.state = MissionState.LAND
            return [create_command("land")]
        return [self._descent_hold_command()]

    def _search_waypoint_command(self):
        target_x, target_y = self.search_waypoints[self._waypoint_index]
        return create_command(
            "set_local_position",
            x=target_x,
            y=target_y,
            z=-self.config.search_altitude_m,
        )

    def _descent_hold_command(self):
        x_m, y_m = self._locked_xy or (0.0, 0.0)
        return create_command("set_local_position", x=x_m, y=y_m, z=self._target_z_m)

    def _zero_body_velocity_command(self):
        return create_command("move_local_vel", vx=0.0, vy=0.0, vz=0.0)

    def _clamp(self, value):
        limit = self.config.max_center_speed_m_s
        return max(-limit, min(limit, value))

    def _find_detection(self, detections, marker_id):
        for detection in detections:
            if getattr(detection, "marker_id", None) == marker_id:
                return detection
        return None

    def _log_origin_pose_error(self, detection, telemetry):
        offset = marker_body_offset_m(detection)
        if offset is None:
            return
        print(
            "[MISSION] Origin marker pose offset body_m="
            f"({offset[0]:.3f}, {offset[1]:.3f}) "
            "pixhawk_xy_m="
            f"({float(telemetry.get('pos_x_m', 0.0)):.3f}, "
            f"{float(telemetry.get('pos_y_m', 0.0)):.3f})"
        )

    def _time(self):
        import time

        return time.monotonic()
