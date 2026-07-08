"""Shared safety gates and helpers for isolated real-drone tests."""

from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_CONNECTION = "/dev/ttyAMA0"
DEFAULT_BAUD = 921600
DEFAULT_REQUIRED_MODE = "GUIDED"


@dataclass(frozen=True)
class SafetyConfig:
    min_battery_voltage_v: float = 11.0
    max_hdop: float = 2.0
    telemetry_timeout_s: float = 1.0
    max_tilt_rad: float = 0.35
    max_position_deviation_m: float = 2.0


class FlightTestRuntime:
    def __init__(self, client):
        self.client = client
        self._last_gcs_heartbeat_s = 0.0

    def tick(self):
        now_s = time.time()
        if now_s - self._last_gcs_heartbeat_s >= 1.0:
            self.client.send_gcs_heartbeat()
            self._last_gcs_heartbeat_s = now_s
        telemetry = self.client.get_telemetry_tick().copy()
        return annotate_telemetry_ages(telemetry, now_s)


def add_connection_args(parser):
    parser.add_argument("--connection", default=DEFAULT_CONNECTION)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--required-mode", default=DEFAULT_REQUIRED_MODE)
    parser.add_argument("--precheck-timeout-s", type=float, default=20.0)
    parser.add_argument("--min-battery-voltage", type=float, default=SafetyConfig.min_battery_voltage_v)
    parser.add_argument("--max-hdop", type=float, default=SafetyConfig.max_hdop)
    parser.add_argument("--telemetry-timeout-s", type=float, default=SafetyConfig.telemetry_timeout_s)
    parser.add_argument("--max-tilt-deg", type=float, default=20.0)
    parser.add_argument("--max-position-deviation-m", type=float, default=SafetyConfig.max_position_deviation_m)
    parser.add_argument("--log-dir", default="logs/real_tests")


def safety_config_from_args(args):
    return SafetyConfig(
        min_battery_voltage_v=args.min_battery_voltage,
        max_hdop=args.max_hdop,
        telemetry_timeout_s=args.telemetry_timeout_s,
        max_tilt_rad=math.radians(args.max_tilt_deg),
        max_position_deviation_m=args.max_position_deviation_m,
    )


def add_real_flight_confirmation(parser):
    parser.add_argument(
        "--confirm-real-flight",
        action="store_true",
        help="Required for any script that may affect a real vehicle.",
    )


def require_real_flight_confirmation(args):
    if not args.confirm_real_flight:
        raise SystemExit("Refusing to run: pass --confirm-real-flight after operator safety checks.")


def require_propless_confirmation(args):
    if args.confirm_propless != "PROPS_OFF":
        raise SystemExit("Refusing to run: pass --confirm-propless PROPS_OFF for bench test.")


def connect_runtime(args):
    from src.comm.mavlink_client import PixhawkClient

    client = PixhawkClient(args.connection, args.baud)
    if not client.wait_for_heartbeat(timeout=15.0):
        raise SystemExit("No Pixhawk heartbeat received.")
    client.request_data_streams(rate_hz=20)
    runtime = FlightTestRuntime(client)
    for _ in range(20):
        runtime.tick()
        time.sleep(0.05)
    return runtime


def annotate_telemetry_ages(telemetry, now_s):
    telemetry["local_age_s"] = _age(now_s, telemetry.get("last_local_position_time"))
    telemetry["attitude_age_s"] = _age(now_s, telemetry.get("last_attitude_time"))
    telemetry["heartbeat_age_s"] = _age(now_s, telemetry.get("last_heartbeat_time"))
    telemetry["gps_age_s"] = _age(now_s, telemetry.get("last_gps_time"))
    telemetry["ekf_age_s"] = _age(now_s, telemetry.get("last_ekf_time"))
    telemetry["rc_age_s"] = _age(now_s, telemetry.get("last_rc_channels_time"))
    return telemetry


def wait_for_preconditions(runtime, logger, safety, required_mode, require_armed, timeout_s):
    deadline_s = time.time() + timeout_s
    last_errors = []
    while time.time() < deadline_s:
        telemetry = runtime.tick()
        last_errors = precondition_errors(telemetry, safety, required_mode, require_armed)
        logger.log_sample(
            telemetry,
            event="precheck",
            result="pass" if not last_errors else "wait",
            message="; ".join(last_errors),
        )
        if not last_errors:
            return telemetry
        time.sleep(0.1)
    raise SystemExit("Preconditions failed: " + "; ".join(last_errors))


def precondition_errors(telemetry, safety, required_mode, require_armed):
    errors = []
    if telemetry.get("heartbeat_age_s", 999.0) > safety.telemetry_timeout_s:
        errors.append("heartbeat stale or missing")
    if telemetry.get("local_age_s", 999.0) > safety.telemetry_timeout_s:
        errors.append("local position stale or missing")
    if telemetry.get("attitude_age_s", 999.0) > safety.telemetry_timeout_s:
        errors.append("attitude stale or missing")
    if telemetry.get("gps_age_s", 999.0) > safety.telemetry_timeout_s:
        errors.append("GPS telemetry stale or missing")
    if telemetry.get("gps_fix_type", 0) < 3:
        errors.append(f"GPS fix < 3D: {telemetry.get('gps_fix_type', 0)}")
    hdop = telemetry.get("hdop")
    if hdop is None or hdop > safety.max_hdop:
        errors.append(f"HDOP too high/unknown: {hdop}")
    if telemetry.get("ekf_age_s", 999.0) > safety.telemetry_timeout_s:
        errors.append("EKF telemetry stale or missing")
    if not telemetry.get("ekf_healthy", False):
        errors.append(f"EKF unhealthy flags={telemetry.get('ekf_flags')}")
    if telemetry.get("rc_age_s", 999.0) > safety.telemetry_timeout_s:
        errors.append("RC telemetry stale or missing")
    if not telemetry.get("rc_link_live", False):
        errors.append("RC link not live")
    if telemetry.get("battery_voltage_v", 0.0) < safety.min_battery_voltage_v:
        errors.append(f"battery below threshold: {telemetry.get('battery_voltage_v', 0.0):.2f} V")
    if telemetry.get("mode") != required_mode:
        errors.append(f"mode is {telemetry.get('mode')}, expected {required_mode}")
    if require_armed and not telemetry.get("armed", False):
        errors.append("vehicle not armed")
    return errors


def abort_reason(telemetry, safety, command_position=None, max_position_deviation_m=None):
    if telemetry.get("heartbeat_age_s", 999.0) > safety.telemetry_timeout_s:
        return "missing heartbeat"
    if telemetry.get("local_age_s", 999.0) > safety.telemetry_timeout_s:
        return "stale local position"
    if telemetry.get("attitude_age_s", 999.0) > safety.telemetry_timeout_s:
        return "stale attitude"
    if abs(telemetry.get("roll_rad", 0.0)) > safety.max_tilt_rad:
        return f"roll tilt too high: {telemetry.get('roll_rad'):.3f} rad"
    if abs(telemetry.get("pitch_rad", 0.0)) > safety.max_tilt_rad:
        return f"pitch tilt too high: {telemetry.get('pitch_rad'):.3f} rad"
    if command_position:
        limit = max_position_deviation_m or safety.max_position_deviation_m
        distance = position_error_m(telemetry, command_position)
        if distance > limit:
            return f"position deviation {distance:.3f} m > {limit:.3f} m"
    return ""


def abort_to_land(runtime, logger, telemetry, command_position, reason):
    logger.log_sample(telemetry, command_position, event="abort", result="fail", message=reason)
    runtime.client.land()
    logger.write_summary({"result": "fail", "reason": reason})
    raise SystemExit(f"ABORT: {reason}; LAND command sent")


def wait_until_armed(runtime, logger, command_position=None, timeout_s=5.0, expected=True, safety=None):
    deadline_s = time.time() + timeout_s
    while time.time() < deadline_s:
        telemetry = runtime.tick()
        logger.log_sample(telemetry, command_position, event="armed_wait")
        if safety is not None and expected:
            reason = abort_reason(telemetry, safety, command_position)
            if reason:
                logger.log_sample(telemetry, command_position, event="abort", result="fail", message=reason)
                if telemetry.get("armed"):
                    runtime.client.arm(state=False)
                raise SystemExit(f"ABORT: {reason}; DISARM command sent if vehicle was armed")
        if telemetry.get("armed") is expected:
            return telemetry
        time.sleep(0.1)
    state = "armed" if expected else "disarmed"
    raise SystemExit(f"Timed out waiting for vehicle to become {state}.")


def sample_at_rate(runtime, logger, command_position, safety, duration_s, rate_hz, event="monitor"):
    interval_s = 1.0 / rate_hz
    end_s = time.time() + duration_s
    samples = []
    while time.time() < end_s:
        telemetry = runtime.tick()
        reason = abort_reason(telemetry, safety, command_position)
        logger.log_sample(telemetry, command_position, event=event, result="abort" if reason else "")
        if reason:
            abort_to_land(runtime, logger, telemetry, command_position, reason)
        samples.append(telemetry)
        time.sleep(interval_s)
    return samples


def position_error_m(telemetry, command_position):
    dx = telemetry.get("pos_x_m", 0.0) - command_position.get("x", 0.0)
    dy = telemetry.get("pos_y_m", 0.0) - command_position.get("y", 0.0)
    dz = telemetry.get("pos_z_m", 0.0) - command_position.get("z", 0.0)
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def mean(values):
    return sum(values) / len(values) if values else float("nan")


def _age(now_s, timestamp_s):
    if not timestamp_s:
        return 999.0
    return max(0.0, now_s - timestamp_s)


def base_parser(description):
    parser = argparse.ArgumentParser(description=description)
    add_connection_args(parser)
    return parser
