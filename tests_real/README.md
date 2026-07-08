# Real MAVLink Test Guide

Use these scripts for isolated Raspberry Pi -> Pixhawk MAVLink tests. Run one test at a time from repo root. Do not use `main.py` for these 1 m tests; it still contains chained ARM -> TAKEOFF 2 m -> LAND reference behavior.

## Safety Rules
- Keep RC transmitter on and manual takeover ready before every run.
- Run `test_00_mode_override.py` propless before any ARM-only or flight test.
- Use props off for `test_00_mode_override.py`; use real-flight confirmation flags only when physically ready.
- Do not advance to next test unless current test passes and logs are reviewed.
- Automatic aborts are defense in depth; RC manual takeover remains primary safety path.

## Setup
- Activate venv: `source .venv/bin/activate`.
- Default Pixhawk link is `/dev/ttyAMA0` at `921600` baud.
- Override link if needed with `--connection <device-or-uri> --baud <baud>`.
- Logs are written to `logs/real_tests/` as CSV plus summary JSON.

## Test Order
- `test_00_mode_override.py`: propless bench check that RC mode switch overrides GUIDED setpoints.
- `test_01_arm_only.py`: send one ARM command, verify ack/telemetry, disarm by default.
- `test_02_vertical_hold.py`: send one +1 m climb command, measure vertical hold error, land by default.
- `test_03_forward_position.py`: send one +1 m forward/+1 m up command, measure position and drift, land by default.

## Common Preconditions
- Heartbeat received from Pixhawk.
- Mode equals required mode, default `GUIDED`.
- 3D GPS fix: `gps_fix_type >= 3`.
- HDOP at or below `--max-hdop`, default `2.0`.
- EKF status healthy.
- RC link live.
- Battery voltage at or above `--min-battery-voltage`, default `11.0` V.
- Local position and attitude telemetry fresh.

## Common Abort Conditions
- Missing/stale heartbeat.
- Stale local position or attitude telemetry.
- Roll or pitch above `--max-tilt-deg`, default `20` degrees.
- Position deviation above `--max-position-deviation-m`, default `2.0` m, for position tests.
- Vertical/forward tests send `LAND` on abort; arming wait sends `DISARM` if needed.

## Logs
Each run creates:

```text
logs/real_tests/<test_name>_<timestamp>.csv
logs/real_tests/<test_name>_<timestamp>.summary.json
```

Important CSV columns:
- `timestamp_s`, `timestamp_iso`, `event`, `result`, `message`.
- `cmd_x_m`, `cmd_y_m`, `cmd_z_m`: commanded full NED position.
- `pos_x_m`, `pos_y_m`, `pos_z_m`: actual full NED position.
- `roll_rad`, `pitch_rad`, `yaw_rad`: full attitude.
- `mode`, `armed`, `battery_voltage_v`, `battery_remaining_pct`.
- `gps_fix_type`, `satellites_visible`, `hdop`.
- `ekf_flags`, `ekf_healthy`, `rc_rssi`, `rc_link_live`.
- `local_age_s`, `attitude_age_s`, `heartbeat_age_s`, `gps_age_s`, `ekf_age_s`, `rc_age_s`.

Example CSV shape:

```csv
timestamp_s,event,result,message,cmd_x_m,cmd_y_m,cmd_z_m,pos_x_m,pos_y_m,pos_z_m,mode,armed
1720000000.100,precheck,pass,,0.000000,0.000000,-1.000000,0.020000,-0.010000,-0.980000,GUIDED,True
1720000001.100,vertical_result,pass,max_z_error_m=0.120; avg_z_error_m=0.060,0.000000,0.000000,-1.000000,0.010000,0.000000,-1.050000,GUIDED,True
```

Record final CSV/JSON path, pass/fail result, and anomalies in `FLIGHT_LOG.md` after each run.

## Test 00: Mode Override
Purpose: prove RC mode switch stops GUIDED setpoint control before relying on it in air.

Physical setup:
- Props off.
- Battery connected only if safe for arming/spin without props.
- RC transmitter on; mode switch can move from `GUIDED` to `LOITER` or `STABILIZE`.

Command:

```bash
.venv/bin/python tests_real/test_00_mode_override.py --confirm-propless PROPS_OFF
```

Operator action:
- Wait for terminal message: `Streaming SET_POSITION_TARGET_LOCAL_NED now. Flip RC mode switch out of GUIDED.`
- Flip RC mode switch from `GUIDED` to `LOITER` or `STABILIZE`.

Expected real-life behavior:
- Vehicle arms on bench with props off.
- Pi keeps sending small `SET_POSITION_TARGET_LOCAL_NED` body-offset commands.
- Pixhawk reported mode changes away from `GUIDED` when RC switch is flipped.

Expected terminal:
- Pixhawk heartbeat received.
- Prechecks pass.
- Streaming prompt appears.
- `PASS: mode override observed. Log: ...`

Expected log:
- Repeated `event=stream_setpoint` rows.
- At least one `event=mode_override_detected`, `result=pass` row.
- `mode` changes from `GUIDED` to RC-selected mode.
- `armed` state is recorded each sample.

Pass criteria:
- Script observes `mode != GUIDED` while setpoint streaming continues.
- CSV shows mode transition and no stale telemetry/unsafe tilt abort.

Fail response:
- Do not run ARM-only or flight tests.
- Fix RC mode mapping/failsafe behavior, then rerun this test propless.

## Test 01: ARM-Only
Purpose: verify Raspberry Pi can send one ARM command and Pixhawk telemetry confirms armed state.

Physical setup:
- Run only after Test 00 passed and log was reviewed.
- RC transmitter on and manual takeover ready.
- Vehicle in required mode, default `GUIDED`.

Command:

```bash
.venv/bin/python tests_real/test_01_arm_only.py --confirm-real-flight --confirm-mode-override-tested
```

Expected real-life behavior:
- Pi sends one ARM command.
- Vehicle arms.
- Script disarms by default after verification.

Expected terminal:
- Prechecks pass.
- ARM command sent.
- Armed telemetry confirmed.
- `PASS: ARM command verified. Log: ...`

Expected log:
- `event=arm_command` row.
- `event=armed_wait` rows until `armed=True`.
- Cleanup rows showing `armed=False` unless `--leave-armed` was used.

Pass criteria:
- ARM command accepted by Pixhawk.
- Telemetry confirms `armed=True` before timeout.
- Cleanup disarm completes unless intentionally skipped.

Fail response:
- Keep props/vehicle safe, inspect pre-arm STATUSTEXT and CSV.
- Do not run vertical test until ARM-only passes.

## Test 02: Vertical Hold
Purpose: command one +1 m climb, hold horizontal position, measure vertical error.

Physical setup:
- Run only after Test 01 passed.
- Vehicle already armed, stable, and in `GUIDED`.
- RC manual takeover ready.

Command:

```bash
.venv/bin/python tests_real/test_02_vertical_hold.py --confirm-real-flight --confirm-arm-only-passed
```

Expected real-life behavior:
- Pi sends one relative body-offset command: `dx=0`, `dy=0`, `dz=-1`.
- Vehicle climbs about 1 m because NED `z` down means negative is up.
- Vehicle holds near starting `x/y`.
- Script sends `LAND` by default after measurement.

Expected terminal:
- Prechecks pass.
- Vertical command sent once.
- Result reports max/average vertical error.
- `PASS: vertical hold within threshold...` only if threshold is met.

Expected log:
- `cmd_x_m`, `cmd_y_m`, `cmd_z_m` show full target NED position.
- `pos_z_m` approaches `cmd_z_m` during hold.
- `pos_x_m` and `pos_y_m` show horizontal drift.
- `roll_rad`, `pitch_rad`, `yaw_rad` logged every sample.
- Summary JSON includes `requires_human_log_review_before_forward_test=true`.

Default pass criteria:
- Max vertical error during hold window <= `--vertical-error-threshold-m`, default `0.20` m.
- Human reviews CSV/summary before Test 03.

Fail or abort response:
- Script sends `LAND` unless `--no-land-at-end` was used.
- Do not run forward test.
- Review vertical error, horizontal drift, EKF, HDOP, battery, and telemetry age columns.

## Test 03: Forward Position
Purpose: command one +1 m body-forward and +1 m up move, then measure position, vertical error, and lateral drift.

Physical setup:
- Run only after Test 02 passed and human log review accepted.
- Vehicle already armed, stable, and in `GUIDED`.
- RC manual takeover ready.

Command:

```bash
.venv/bin/python tests_real/test_03_forward_position.py --confirm-real-flight --confirm-vertical-log-reviewed
```

Expected real-life behavior:
- Pi reads starting yaw.
- Pi sends one body-offset command: `dx=1`, `dy=0`, `dz=-1`.
- Expected NED target is computed from starting yaw because body forward depends on heading.
- Vehicle moves about 1 m forward relative to its nose and 1 m up.
- Script sends `LAND` by default after measurement.

Expected terminal:
- Prechecks pass.
- Forward/up command sent once.
- Result reports max position error, lateral drift, and vertical error.
- `PASS: forward position test within thresholds. Log: ...` only if all thresholds are met.

Expected log:
- `message` on `event=forward_command` includes `start_yaw_rad`.
- `cmd_x_m`, `cmd_y_m`, `cmd_z_m` contain full expected local-NED target.
- `pos_x_m`, `pos_y_m`, `pos_z_m` show actual full position.
- Lateral drift can be reviewed from `pos_x_m/pos_y_m` and summary JSON.

Default pass criteria:
- Max full position error <= `--position-error-threshold-m`, default `0.30` m.
- Max lateral drift <= `--lateral-drift-threshold-m`, default `0.20` m.
- Max vertical error <= `--vertical-error-threshold-m`, default `0.20` m.

Fail or abort response:
- Script sends `LAND` unless `--no-land-at-end` was used.
- Review yaw, lateral drift, EKF/GPS/HDOP, and position logs before retry.

## Operator Checklist
Before each test:
- Correct props state for the test.
- RC transmitter on, mode switch verified, manual takeover ready.
- Battery voltage above configured threshold.
- Pixhawk parameters snapshotted before any parameter change.
- Repo command is launched from root with `.venv` active.

After each test:
- Save CSV and summary JSON path.
- Record run in `FLIGHT_LOG.md`.
- Note firmware version, parameter snapshot name, result, and anomalies.
- Stop sequence immediately if pass criteria are not met.
