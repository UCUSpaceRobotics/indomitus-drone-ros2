#!/usr/bin/env python3
"""Real test: send one +1 m vertical command, log hold error, then land."""

from __future__ import annotations

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


TEST_NAME = "test_02_vertical_hold"


def parse_args():
    parser = base_parser(__doc__)
    add_real_flight_confirmation(parser)
    parser.add_argument(
        "--confirm-arm-only-passed",
        action="store_true",
        help="Required: test_01_arm_only.py passed for this setup.",
    )
    parser.add_argument("--climb-m", type=float, default=1.0)
    parser.add_argument("--hold-duration-s", type=float, default=8.0)
    parser.add_argument("--settle-s", type=float, default=3.0)
    parser.add_argument("--sample-rate-hz", type=float, default=20.0)
    parser.add_argument("--vertical-error-threshold-m", type=float, default=0.20)
    parser.add_argument("--no-land-at-end", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    require_real_flight_confirmation(args)
    if not args.confirm_arm_only_passed:
        raise SystemExit("Refusing to run: pass --confirm-arm-only-passed after test_01 passes.")
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
        command_position = {
            "x": start["pos_x_m"],
            "y": start["pos_y_m"],
            "z": start["pos_z_m"] - abs(args.climb_m),
        }
        logger.log_sample(start, command_position, event="vertical_command", message="one relative +Z-up command")
        runtime.client.send_position_target_local_ned(0.0, 0.0, -abs(args.climb_m))

        samples = sample_at_rate(
            runtime,
            logger,
            command_position,
            safety,
            duration_s=args.settle_s + args.hold_duration_s,
            rate_hz=args.sample_rate_hz,
            event="vertical_hold",
        )
        hold_sample_count = max(1, int(args.hold_duration_s * args.sample_rate_hz))
        hold_samples = samples[-hold_sample_count:]
        errors = [abs(sample["pos_z_m"] - command_position["z"]) for sample in hold_samples]
        max_error = max(errors) if errors else float("inf")
        avg_error = mean(errors)
        passed = max_error <= args.vertical_error_threshold_m

        final = runtime.tick()
        logger.log_sample(
            final,
            command_position,
            event="vertical_result",
            result="pass" if passed else "fail",
            message=f"max_z_error_m={max_error:.3f}; avg_z_error_m={avg_error:.3f}",
        )
        if not args.no_land_at_end:
            runtime.client.land()

        summary = {
            "result": "pass" if passed else "fail",
            "cmd_z_m": command_position["z"],
            "max_vertical_error_m": max_error,
            "avg_vertical_error_m": avg_error,
            "threshold_m": args.vertical_error_threshold_m,
            "requires_human_log_review_before_forward_test": True,
            "land_command_sent": not args.no_land_at_end,
            "log_path": str(logger.csv_path),
        }
        logger.write_summary(summary)
        if not passed:
            raise SystemExit(f"FAIL: vertical error {max_error:.3f} m > {args.vertical_error_threshold_m:.3f} m")
        print(f"PASS: vertical hold within threshold. Human log review still required. Log: {logger.csv_path}")


if __name__ == "__main__":
    main()
