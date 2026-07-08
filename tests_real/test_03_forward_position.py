#!/usr/bin/env python3
"""Real test: send one +1 m up/+1 m body-forward command and measure drift."""

from __future__ import annotations

import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests_real.common import (
    add_real_flight_confirmation,
    base_parser,
    connect_runtime,
    mean,
    sample_at_rate,
    safety_config_from_args,
    require_real_flight_confirmation,
    wait_for_preconditions,
)
from tests_real.flight_logger import FlightLogger


TEST_NAME = "test_03_forward_position"


def parse_args():
    parser = base_parser(__doc__)
    add_real_flight_confirmation(parser)
    parser.add_argument(
        "--confirm-vertical-log-reviewed",
        action="store_true",
        help="Required: vertical hold log reviewed by human and accepted.",
    )
    parser.add_argument("--forward-m", type=float, default=1.0)
    parser.add_argument("--climb-m", type=float, default=1.0)
    parser.add_argument("--hold-duration-s", type=float, default=8.0)
    parser.add_argument("--settle-s", type=float, default=4.0)
    parser.add_argument("--sample-rate-hz", type=float, default=20.0)
    parser.add_argument("--position-error-threshold-m", type=float, default=0.30)
    parser.add_argument("--lateral-drift-threshold-m", type=float, default=0.20)
    parser.add_argument("--vertical-error-threshold-m", type=float, default=0.20)
    parser.add_argument("--no-land-at-end", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    require_real_flight_confirmation(args)
    if not args.confirm_vertical_log_reviewed:
        raise SystemExit("Refusing to run: pass --confirm-vertical-log-reviewed after human log review.")
    safety = safety_config_from_args(args)
    runtime = connect_runtime(args)

    with FlightLogger(TEST_NAME, args.log_dir) as logger:
        start = wait_for_preconditions(
            runtime,
            logger,
            safety,
            required_mode=args.required_mode,
            require_armed=True,
            timeout_s=args.precheck_timeout_s,
        )
        yaw = start["yaw_rad"]
        north_step = math.cos(yaw) * abs(args.forward_m)
        east_step = math.sin(yaw) * abs(args.forward_m)
        command_position = {
            "x": start["pos_x_m"] + north_step,
            "y": start["pos_y_m"] + east_step,
            "z": start["pos_z_m"] - abs(args.climb_m),
        }
        logger.log_sample(
            start,
            command_position,
            event="forward_command",
            message=f"start_yaw_rad={yaw:.3f}; one body-offset forward/up command",
        )
        runtime.client.send_position_target_local_ned(abs(args.forward_m), 0.0, -abs(args.climb_m))

        samples = sample_at_rate(
            runtime,
            logger,
            command_position,
            safety,
            duration_s=args.settle_s + args.hold_duration_s,
            rate_hz=args.sample_rate_hz,
            event="forward_hold",
        )
        hold_sample_count = max(1, int(args.hold_duration_s * args.sample_rate_hz))
        hold_samples = samples[-hold_sample_count:]

        position_errors = [_position_error(sample, command_position) for sample in hold_samples]
        lateral_drifts = [_lateral_drift(sample, start, yaw) for sample in hold_samples]
        vertical_errors = [abs(sample["pos_z_m"] - command_position["z"]) for sample in hold_samples]

        max_position_error = max(position_errors) if position_errors else float("inf")
        max_lateral_drift = max(lateral_drifts) if lateral_drifts else float("inf")
        max_vertical_error = max(vertical_errors) if vertical_errors else float("inf")
        passed = (
            max_position_error <= args.position_error_threshold_m
            and max_lateral_drift <= args.lateral_drift_threshold_m
            and max_vertical_error <= args.vertical_error_threshold_m
        )

        final = runtime.tick()
        logger.log_sample(
            final,
            command_position,
            event="forward_result",
            result="pass" if passed else "fail",
            message=(
                f"max_position_error_m={max_position_error:.3f}; "
                f"max_lateral_drift_m={max_lateral_drift:.3f}; "
                f"max_vertical_error_m={max_vertical_error:.3f}"
            ),
        )
        if not args.no_land_at_end:
            runtime.client.land()

        summary = {
            "result": "pass" if passed else "fail",
            "start_yaw_rad": yaw,
            "cmd_x_m": command_position["x"],
            "cmd_y_m": command_position["y"],
            "cmd_z_m": command_position["z"],
            "max_position_error_m": max_position_error,
            "avg_position_error_m": mean(position_errors),
            "max_lateral_drift_m": max_lateral_drift,
            "avg_lateral_drift_m": mean(lateral_drifts),
            "max_vertical_error_m": max_vertical_error,
            "avg_vertical_error_m": mean(vertical_errors),
            "land_command_sent": not args.no_land_at_end,
            "log_path": str(logger.csv_path),
        }
        logger.write_summary(summary)
        if not passed:
            raise SystemExit("FAIL: forward position/vertical/lateral threshold exceeded")
        print(f"PASS: forward position test within thresholds. Log: {logger.csv_path}")


def _position_error(sample, command_position):
    dx = sample["pos_x_m"] - command_position["x"]
    dy = sample["pos_y_m"] - command_position["y"]
    dz = sample["pos_z_m"] - command_position["z"]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _lateral_drift(sample, start, yaw):
    dx = sample["pos_x_m"] - start["pos_x_m"]
    dy = sample["pos_y_m"] - start["pos_y_m"]
    return abs(-math.sin(yaw) * dx + math.cos(yaw) * dy)


if __name__ == "__main__":
    main()
