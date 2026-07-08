"""Shared CSV logging for real MAVLink flight tests."""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime
from pathlib import Path


FIELDNAMES = [
    "timestamp_s",
    "timestamp_iso",
    "test_name",
    "event",
    "result",
    "message",
    "cmd_x_m",
    "cmd_y_m",
    "cmd_z_m",
    "pos_x_m",
    "pos_y_m",
    "pos_z_m",
    "roll_rad",
    "pitch_rad",
    "yaw_rad",
    "mode",
    "armed",
    "battery_voltage_v",
    "battery_remaining_pct",
    "ekf_flags",
    "ekf_healthy",
    "rc_rssi",
    "rc_link_live",
    "local_age_s",
    "attitude_age_s",
    "heartbeat_age_s",
    "ekf_age_s",
    "rc_age_s",
]


class FlightLogger:
    def __init__(self, test_name, output_dir="logs/real_tests"):
        self.test_name = test_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_path = self.output_dir / f"{test_name}_{timestamp}.csv"
        self.summary_path = self.output_dir / f"{test_name}_{timestamp}.summary.json"
        self._file = self.csv_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=FIELDNAMES)
        self._writer.writeheader()
        self._file.flush()

    def log_sample(
        self,
        telemetry,
        command_position=None,
        event="sample",
        result="",
        message="",
        now_s=None,
    ):
        now_s = time.time() if now_s is None else now_s
        command_position = command_position or {}
        row = {
            "timestamp_s": f"{now_s:.3f}",
            "timestamp_iso": datetime.fromtimestamp(now_s).isoformat(timespec="milliseconds"),
            "test_name": self.test_name,
            "event": event,
            "result": result,
            "message": message,
            "cmd_x_m": _fmt(command_position.get("x")),
            "cmd_y_m": _fmt(command_position.get("y")),
            "cmd_z_m": _fmt(command_position.get("z")),
            "pos_x_m": _fmt(telemetry.get("pos_x_m")),
            "pos_y_m": _fmt(telemetry.get("pos_y_m")),
            "pos_z_m": _fmt(telemetry.get("pos_z_m")),
            "roll_rad": _fmt(telemetry.get("roll_rad")),
            "pitch_rad": _fmt(telemetry.get("pitch_rad")),
            "yaw_rad": _fmt(telemetry.get("yaw_rad")),
            "mode": telemetry.get("mode", "UNKNOWN"),
            "armed": telemetry.get("armed", ""),
            "battery_voltage_v": _fmt(telemetry.get("battery_voltage_v")),
            "battery_remaining_pct": telemetry.get("battery_remaining_pct", ""),
            "ekf_flags": telemetry.get("ekf_flags", ""),
            "ekf_healthy": telemetry.get("ekf_healthy", ""),
            "rc_rssi": telemetry.get("rc_rssi", ""),
            "rc_link_live": telemetry.get("rc_link_live", ""),
            "local_age_s": _fmt(telemetry.get("local_age_s")),
            "attitude_age_s": _fmt(telemetry.get("attitude_age_s")),
            "heartbeat_age_s": _fmt(telemetry.get("heartbeat_age_s")),
            "ekf_age_s": _fmt(telemetry.get("ekf_age_s")),
            "rc_age_s": _fmt(telemetry.get("rc_age_s")),
        }
        self._writer.writerow(row)
        self._file.flush()

    def write_summary(self, summary):
        payload = dict(summary)
        payload.setdefault("test_name", self.test_name)
        payload.setdefault("csv_path", str(self.csv_path))
        payload.setdefault("written_at", datetime.now().isoformat(timespec="seconds"))
        self.summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def close(self):
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def _fmt(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return value
