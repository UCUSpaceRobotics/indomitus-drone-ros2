#!/usr/bin/env python3
"""Real test: send one ARM or DISARM command and verify telemetry/ack."""

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
    require_real_flight_confirmation,
    safety_config_from_args,
    wait_for_preconditions,
    wait_until_armed,
)
from tests_real.flight_logger import FlightLogger


TEST_NAME = "test_01_arm_only"


def parse_args():
    parser = base_parser(__doc__)
    add_real_flight_confirmation(parser)
    parser.add_argument(
        "--confirm-mode-override-tested",
        action="store_true",
        help="Required: test_00_mode_override.py passed and log was reviewed.",
    )
    parser.add_argument(
        "--command",
        choices=("arm", "disarm"),
        default="arm",
        help="One command to send. Default: arm.",
    )
    parser.add_argument("--leave-armed", action="store_true", help="Do not send DISARM after verification.")
    return parser.parse_args()


def main():
    args = parse_args()
    require_real_flight_confirmation(args)
    if not args.confirm_mode_override_tested:
        raise SystemExit("Refusing to run: pass --confirm-mode-override-tested after test_00 passes.")
    safety = safety_config_from_args(args)
    runtime = connect_runtime(args)

    with FlightLogger(TEST_NAME, args.log_dir) as logger:
        telemetry = wait_for_preconditions(
            runtime,
            logger,
            safety,
            required_mode=args.required_mode,
            require_armed=False,
            timeout_s=args.precheck_timeout_s,
        )
        if args.command == "arm" and telemetry.get("armed"):
            logger.write_summary({"result": "fail", "reason": "vehicle already armed before ARM-only test"})
            raise SystemExit("Refusing ARM-only test: vehicle already armed.")
        if args.command == "disarm" and not telemetry.get("armed"):
            logger.write_summary({"result": "fail", "reason": "vehicle already disarmed before DISARM test"})
            raise SystemExit("Refusing DISARM test: vehicle already disarmed.")

        if args.command == "disarm":
            logger.log_sample(telemetry, event="disarm_command", message="sending one DISARM command")
            ack = runtime.client.arm(state=False)
            telemetry = wait_until_armed(runtime, logger, timeout_s=5.0, expected=False)
            passed = bool(ack and not telemetry.get("armed"))
        else:
            logger.log_sample(telemetry, event="arm_command", message="sending one ARM command")
            ack = runtime.client.arm(state=True)
            telemetry = wait_until_armed(runtime, logger, timeout_s=5.0, expected=True, safety=safety)
            passed = bool(ack and telemetry.get("armed"))

        if args.command == "arm" and not args.leave_armed:
            logger.log_sample(telemetry, event="cleanup_disarm", message="safety disarm after ARM-only test")
            runtime.client.arm(state=False)
            wait_until_armed(runtime, logger, timeout_s=5.0, expected=False)

        summary = {
            "result": "pass" if passed else "fail",
            "command": args.command,
            "command_ack": ack,
            "armed_telemetry": telemetry.get("armed"),
            "left_armed": args.command == "arm" and args.leave_armed,
            "log_path": str(logger.csv_path),
        }
        logger.write_summary(summary)
        if not passed:
            raise SystemExit(f"FAIL: {args.command.upper()} ack/telemetry did not confirm target armed state.")
        print(f"PASS: {args.command.upper()} command verified. Log: {logger.csv_path}")


if __name__ == "__main__":
    main()
