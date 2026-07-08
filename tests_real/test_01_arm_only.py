#!/usr/bin/env python3
"""Real test: send one ARM or DISARM command and verify telemetry/ack."""

from __future__ import annotations

import sys
import time
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
    parser.add_argument(
        "--arm-mode",
        default="LOITER",
        help="Mode to set before ARM. Default mirrors main.py: LOITER.",
    )
    parser.add_argument("--mode-timeout-s", type=float, default=5.0)
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
        telemetry = wait_for_arm_only_preconditions(runtime, logger, safety, args.precheck_timeout_s)

        if args.command == "arm":
            logger.log_sample(telemetry, event="set_arm_mode", message=f"setting mode {args.arm_mode} before ARM")
            if not runtime.client.set_mode(args.arm_mode):
                logger.write_summary({"result": "fail", "reason": f"could not send mode {args.arm_mode}"})
                raise SystemExit(f"Could not send mode {args.arm_mode}.")
            telemetry = wait_for_mode(runtime, logger, args.arm_mode, args.mode_timeout_s)

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
            telemetry = wait_until_armed(runtime, logger, timeout_s=5.0, expected=True)
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


def wait_for_arm_only_preconditions(runtime, logger, safety, timeout_s):
    deadline_s = time.time() + timeout_s
    last_errors = []
    while time.time() < deadline_s:
        telemetry = runtime.tick()
        last_errors = arm_only_precondition_errors(telemetry, safety)
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


def arm_only_precondition_errors(telemetry, safety):
    errors = []
    if telemetry.get("heartbeat_age_s", 999.0) > safety.telemetry_timeout_s:
        errors.append("heartbeat stale or missing")
    if telemetry.get("battery_voltage_v", 0.0) < safety.min_battery_voltage_v:
        errors.append(f"battery below threshold: {telemetry.get('battery_voltage_v', 0.0):.2f} V")
    return errors


def wait_for_mode(runtime, logger, mode, timeout_s):
    deadline_s = time.time() + timeout_s
    last_mode = "UNKNOWN"
    while time.time() < deadline_s:
        telemetry = runtime.tick()
        last_mode = telemetry.get("mode", "UNKNOWN")
        logger.log_sample(telemetry, event="mode_wait", result="pass" if last_mode == mode else "wait")
        if last_mode == mode:
            return telemetry
        time.sleep(0.1)
    raise SystemExit(f"Timed out waiting for mode {mode}; last mode={last_mode}.")


if __name__ == "__main__":
    main()
