#!/usr/bin/env python3
"""Bench/propless test: RC mode switch overrides GUIDED setpoint streaming."""

from __future__ import annotations

import time
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests_real.common import (
    abort_reason,
    base_parser,
    connect_runtime,
    require_propless_confirmation,
    safety_config_from_args,
    wait_for_preconditions,
    wait_until_armed,
)
from tests_real.flight_logger import FlightLogger


TEST_NAME = "test_00_mode_override"


def parse_args():
    parser = base_parser(__doc__)
    parser.add_argument("--confirm-propless", help="Must be exactly PROPS_OFF.")
    parser.add_argument("--stream-duration-s", type=float, default=20.0)
    parser.add_argument("--stream-rate-hz", type=float, default=5.0)
    parser.add_argument("--dx", type=float, default=0.1, help="Body-offset x target sent repeatedly.")
    parser.add_argument("--dy", type=float, default=0.0, help="Body-offset y target sent repeatedly.")
    parser.add_argument("--dz", type=float, default=0.0, help="Body-offset z target sent repeatedly.")
    parser.add_argument("--no-disarm-at-end", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    require_propless_confirmation(args)
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
        logger.log_sample(telemetry, event="precheck_complete", result="pass")

        if not runtime.client.arm(state=True):
            logger.write_summary({"result": "fail", "reason": "arm command rejected or timed out"})
            raise SystemExit("ARM command rejected or timed out.")
        telemetry = wait_until_armed(runtime, logger, timeout_s=5.0, expected=True, safety=safety)

        print("Streaming SET_POSITION_TARGET_LOCAL_NED now. Flip RC mode switch out of GUIDED.")
        start_s = time.time()
        end_s = start_s + args.stream_duration_s
        interval_s = 1.0 / args.stream_rate_hz
        observed_guided = telemetry.get("mode") == args.required_mode
        observed_override = False

        try:
            while time.time() < end_s:
                runtime.client.send_position_target_local_ned(args.dx, args.dy, args.dz)
                telemetry = runtime.tick()
                mode = telemetry.get("mode")
                if mode == args.required_mode:
                    observed_guided = True
                if observed_guided and mode != args.required_mode:
                    observed_override = True
                    event = "mode_override_detected"
                    result = "pass"
                    message = f"mode changed to {mode} while streaming commands"
                else:
                    event = "stream_setpoint"
                    result = ""
                    message = ""

                reason = abort_reason(telemetry, safety)
                logger.log_sample(telemetry, event=event, result=result, message=message)
                if reason:
                    logger.write_summary({"result": "fail", "reason": reason})
                    raise SystemExit(f"ABORT: {reason}")
                time.sleep(interval_s)
        finally:
            if not args.no_disarm_at_end:
                runtime.client.arm(state=False)

        summary = {
            "result": "pass" if observed_override else "fail",
            "observed_guided": observed_guided,
            "observed_override": observed_override,
            "log_path": str(logger.csv_path),
        }
        logger.write_summary(summary)
        if not observed_override:
            raise SystemExit("FAIL: did not observe RC mode override away from GUIDED.")
        print(f"PASS: mode override observed. Log: {logger.csv_path}")


if __name__ == "__main__":
    main()
