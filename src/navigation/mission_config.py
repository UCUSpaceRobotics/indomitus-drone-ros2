from dataclasses import dataclass


@dataclass(frozen=True)
class MissionConfig:
    mission_radius_m: float = 3.0
    hard_safety_radius_m: float = 5.0
    marker_size_m: float = 0.15
    origin_marker_id: int = 13
    landing_marker_id: int = 14
    search_altitude_m: float = 1.4
    search_speed_m_s: float = 0.4
    descent_step_m: float = 0.15
    land_altitude_m: float = 0.25
    pose_timeout_s: float = 0.5
    marker_loss_timeout_s: float = 1.5
    center_tolerance_m: float = 0.08
    recenter_tolerance_m: float = 0.12
    abort_tolerance_m: float = 0.25
    center_stable_time_s: float = 0.7
    center_gain: float = 0.6
    max_center_speed_m_s: float = 0.25
    waypoint_acceptance_m: float = 0.25


DEV_CONFIG = MissionConfig(origin_marker_id=13, landing_marker_id=14)
REAL_CONFIG = MissionConfig(origin_marker_id=101, landing_marker_id=102)
