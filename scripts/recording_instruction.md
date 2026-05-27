# Drone Mission Camera Recording — Setup Guide

**Platform:** Raspberry Pi 5 + Arducam IMX708 12MP HDR (CSI)
**Purpose:** Auto-record downward camera footage on boot, save to repo, power off.
**Repo path:** `/workspace/indomitus-drone-ros2`

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [File Placement](#2-file-placement)
3. [Script Content](#3-script-content)
4. [Service File Content](#4-service-file-content)
5. [Installation Commands](#5-installation-commands)
6. [Verifying the Setup](#6-verifying-the-setup)
7. [Disabling / Removing the Service](#7-disabling--removing-the-service)
8. [Changing Recording Parameters](#8-changing-recording-parameters)
9. [Troubleshooting & Known Challenges](#9-troubleshooting--known-challenges)

---

## 1. Prerequisites

Before deploying the scripts, make sure the following are in place on the Raspberry Pi.

### 1.1 Operating System

Use **Raspberry Pi OS (64-bit, Bookworm or later)**. The 64-bit variant is required for full IMX708 HDR support and best `libcamera` performance.

```bash
# Verify OS version
cat /etc/os-release

# Verify architecture (must be aarch64)
uname -m
```

### 1.2 Camera Stack

The IMX708 is supported natively by `libcamera` on modern Raspberry Pi OS. Confirm the camera is detected:

```bash
# List detected cameras
libcamera-hello --list-cameras
```

Expected output includes a line mentioning `imx708`. If nothing is listed, see [§9.1](#91-camera-not-detected).

### 1.3 Camera Interface Enabled

```bash
# Open the raspi-config tool
sudo raspi-config
```

Navigate to: **Interface Options → Camera → Enable**, then reboot.

Alternatively, check `/boot/firmware/config.txt` and ensure this line exists:

```
camera_auto_detect=1
```

### 1.4 Install ffmpeg

ffmpeg is used to wrap the raw H.264 stream into a playable `.mp4` container.

```bash
sudo apt update && sudo apt install -y ffmpeg

# Verify
ffmpeg -version | head -1
```

### 1.5 Ensure the Scripts Folder Exists

```bash
mkdir -p /workspace/indomitus-drone-ros2/scripts
```

---

## 2. File Placement

| File | Destination on Raspberry Pi |
|------|-----------------------------|
| `record_mission.sh` | `/workspace/indomitus-drone-ros2/scripts/record_mission.sh` |
| `drone-record.service` | `/etc/systemd/system/drone-record.service` |

Video recordings and the log file will be saved to:

```
/workspace/indomitus-drone-ros2/mission_YYYYMMDD_HHMMSS.mp4
/workspace/indomitus-drone-ros2/record_mission.log
```

---

## 3. Script Content

Create the recording script at the path below. You can paste this directly or `scp` it from your development machine.

**File:** `/workspace/indomitus-drone-ros2/scripts/record_mission.sh`

```bash
#!/bin/bash
# =============================================================
#  record_mission.sh
#  Auto-records from Arducam IMX708 (CSI) for a fixed duration,
#  saves the video to the project repo, then powers off the Pi.
# =============================================================

# ---------- configuration ------------------------------------
SAVE_DIR="/workspace/indomitus-drone-ros2"
DURATION=60          # seconds to record
WIDTH=1920
HEIGHT=1080
FPS=30
# -------------------------------------------------------------

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT="${SAVE_DIR}/mission_${TIMESTAMP}.h264"
LOG_FILE="${SAVE_DIR}/record_mission.log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

mkdir -p "$SAVE_DIR"

log "=== Mission recording started ==="
log "Output : $OUTPUT"
log "Duration: ${DURATION}s  |  ${WIDTH}x${HEIGHT} @ ${FPS}fps"

# Wait for the OS and camera stack to fully settle after boot
sleep 5

# Start recording
libcamera-vid \
    --timeout $(( DURATION * 1000 )) \
    --codec h264 \
    --width  $WIDTH \
    --height $HEIGHT \
    --framerate $FPS \
    --autofocus-mode continuous \
    --hdr \
    --output "$OUTPUT" \
    >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log "Recording finished successfully → $OUTPUT"
    MP4_OUTPUT="${OUTPUT%.h264}.mp4"
    if command -v ffmpeg &>/dev/null; then
        log "Converting to MP4 …"
        ffmpeg -y -framerate $FPS -i "$OUTPUT" \
               -c:v copy "$MP4_OUTPUT" >> "$LOG_FILE" 2>&1 \
        && rm "$OUTPUT" \
        && log "Saved as MP4 → $MP4_OUTPUT" \
        || log "ffmpeg conversion failed – raw H.264 kept at $OUTPUT"
    else
        log "ffmpeg not found – keeping raw H.264 file."
    fi
else
    log "ERROR: libcamera-vid exited with code $EXIT_CODE"
fi

log "Syncing filesystem …"
sync

log "Powering off Raspberry Pi."
/sbin/poweroff
```

Make it executable:

```bash
chmod +x /workspace/indomitus-drone-ros2/scripts/record_mission.sh
```

---

## 4. Service File Content

Create the systemd unit file exactly as shown below.

**File:** `/etc/systemd/system/drone-record.service`

```ini
[Unit]
Description=Indomitus Drone – Mission Camera Recording
After=multi-user.target local-fs.target

[Service]
Type=oneshot
User=root

ExecStart=/workspace/indomitus-drone-ros2/scripts/record_mission.sh

# Must be at least DURATION + ~60 s for ffmpeg conversion headroom
TimeoutStartSec=180

StandardOutput=journal
StandardError=journal

RemainAfterExit=no

[Install]
WantedBy=multi-user.target
```

> **Note on `TimeoutStartSec`:** If you increase `DURATION` beyond 60 s, raise this value too.
> Rule of thumb: `TimeoutStartSec = DURATION + 60`.

---

## 5. Installation Commands

Run these commands on the Raspberry Pi in order. You must be `root` or use `sudo`.

```bash
# 1. Copy the script into the repo's scripts folder
#    (skip if you created it there directly)
cp /path/to/record_mission.sh /workspace/indomitus-drone-ros2/scripts/record_mission.sh

# 2. Make it executable
chmod +x /workspace/indomitus-drone-ros2/scripts/record_mission.sh

# 3. Copy the service file into systemd
cp /path/to/drone-record.service /etc/systemd/system/drone-record.service

# 4. Reload systemd so it picks up the new unit
sudo systemctl daemon-reload

# 5. Enable the service to run on every boot
sudo systemctl enable drone-record.service

# 6. (Optional) Run it once right now without rebooting to verify
sudo systemctl start drone-record.service
```

To watch live output while the service runs:

```bash
journalctl -fu drone-record.service
```

---

## 6. Verifying the Setup

### 6.1 Check the service is enabled

```bash
sudo systemctl is-enabled drone-record.service
# Expected output: enabled
```

### 6.2 Check service status after a boot

```bash
sudo systemctl status drone-record.service
```

A healthy run shows `inactive (dead)` with exit code `0` — this is correct because `Type=oneshot` services finish and exit.

### 6.3 Read the log file

```bash
cat /workspace/indomitus-drone-ros2/record_mission.log
```

A successful run looks like:

```
[2025-01-15 10:32:01] === Mission recording started ===
[2025-01-15 10:32:01] Output : /workspace/indomitus-drone-ros2/mission_20250115_103201.h264
[2025-01-15 10:32:01] Duration: 60s  |  1920x1080 @ 30fps
[2025-01-15 10:33:07] Recording finished successfully → ...mission_20250115_103201.h264
[2025-01-15 10:33:09] Converting to MP4 …
[2025-01-15 10:33:11] Saved as MP4 → ...mission_20250115_103201.mp4
[2025-01-15 10:33:11] Syncing filesystem …
[2025-01-15 10:33:11] Powering off Raspberry Pi.
```

### 6.4 Check the journal (more detail)

```bash
journalctl -u drone-record.service --no-pager
```

---

## 7. Disabling / Removing the Service

### 7.1 Temporarily disable (survives until re-enabled)

The service will not start on the next boot, but the files remain intact.

```bash
sudo systemctl disable drone-record.service
```

### 7.2 Stop a currently running instance

```bash
sudo systemctl stop drone-record.service
```

> **Warning:** Stopping mid-recording will leave an incomplete `.h264` file.
> The Pi will **not** power off if the service is stopped this way.

### 7.3 Prevent the poweroff during testing

Comment out the last line of `record_mission.sh` so the Pi stays on after recording:

```bash
# /sbin/poweroff    ← add a # at the start of this line
```

Then restart the service manually for tests. Re-enable poweroff before a real flight.

### 7.4 Fully remove the service

```bash
sudo systemctl stop drone-record.service
sudo systemctl disable drone-record.service
sudo rm /etc/systemd/system/drone-record.service
sudo systemctl daemon-reload
sudo systemctl reset-failed
```

The script itself at `/workspace/indomitus-drone-ros2/scripts/record_mission.sh` is not deleted by the above — remove it manually if needed:

```bash
rm /workspace/indomitus-drone-ros2/scripts/record_mission.sh
```

---

## 8. Changing Recording Parameters

All core parameters live at the top of `record_mission.sh`:

```bash
SAVE_DIR="/workspace/indomitus-drone-ros2"   # where to save recordings
DURATION=60          # recording length in seconds
WIDTH=1920           # frame width
HEIGHT=1080          # frame height
FPS=30               # frames per second
```

After editing the script, **also update `TimeoutStartSec`** in the service file if you change `DURATION`:

```bash
# Example: 3-minute flight
# In record_mission.sh:  DURATION=180
# In drone-record.service:  TimeoutStartSec=260   (180 + 80)

sudo systemctl daemon-reload   # always reload after editing the .service file
```

### Common resolution presets

| Use case | WIDTH | HEIGHT | FPS | ~Bitrate |
|----------|-------|--------|-----|---------|
| Max quality | 4608 | 2592 | 14 | ~25 Mbps |
| Full HD (default) | 1920 | 1080 | 30 | ~10 Mbps |
| HD for longer flights | 1280 | 720 | 30 | ~5 Mbps |
| Low storage test | 1280 | 720 | 15 | ~2.5 Mbps |

> At 1080p 30fps, 60 seconds ≈ **~75 MB** on the SD card.

---

## 9. Troubleshooting & Known Challenges

### 9.1 Camera Not Detected

**Symptom:** `libcamera-hello --list-cameras` returns `No cameras available`.

**Causes and fixes:**

- **CSI cable not seated properly** — power off completely, reseat both ends of the flat cable (connector on Pi and on camera). The locking tab must click.
- **Camera interface disabled** — run `sudo raspi-config → Interface Options → Camera → Enable` and reboot.
- **Wrong config.txt entry** — open `/boot/firmware/config.txt` (note: on older OS it was `/boot/config.txt`) and confirm `camera_auto_detect=1` is present and **not** commented out.
- **Outdated OS** — IMX708 support was added in late 2022. Run `sudo apt full-upgrade` and reboot.

```bash
# Quick diagnostic
vcgencmd get_camera          # should show: supported=1 detected=1
dmesg | grep -i imx708       # should show the driver loading
```

---

### 9.2 `libcamera-vid` Exits Immediately with Error

**Symptom:** Log shows `ERROR: libcamera-vid exited with code 1` seconds after starting.

**Causes and fixes:**

- **Another process holds the camera** — only one process can use the CSI camera at a time. Check for other services using it:
  ```bash
  sudo fuser /dev/video0
  ```
- **HDR flag not supported on your libcamera version** — remove `--hdr` from the `libcamera-vid` call in the script if you see errors about unknown options:
  ```bash
  libcamera-vid --help | grep hdr   # if nothing printed, --hdr is unsupported
  ```
- **Autofocus not supported** — if the camera mount has no autofocus motor wired, change `--autofocus-mode continuous` to `--autofocus-mode manual`.

---

### 9.3 Recorded File is Unplayable / Corrupted

**Symptom:** `.h264` or `.mp4` file exists but media players fail to open it.

**Causes and fixes:**

- **Power cut during recording** — the raw H.264 stream has no container index; if recording is interrupted the file is still usually playable with VLC. The `.mp4` container written by ffmpeg requires a complete stream. Always let the script finish.
- **SD card full** — check free space before flights:
  ```bash
  df -h /workspace
  ```
  Clean up old recordings regularly.
- **ffmpeg muxing error** — check `record_mission.log` for ffmpeg output. The raw `.h264` is kept if ffmpeg fails, and VLC can play it directly.

---

### 9.4 Service Does Not Start on Boot

**Symptom:** After reboot, no recording happens and no log file is created.

**Checks:**

```bash
# Is the service enabled?
sudo systemctl is-enabled drone-record.service

# Did it fail silently?
sudo systemctl status drone-record.service
journalctl -u drone-record.service -b   # -b = current boot only
```

**Common causes:**

- `daemon-reload` was not run after placing the service file — run it again:
  ```bash
  sudo systemctl daemon-reload && sudo systemctl enable drone-record.service
  ```
- Script path is wrong — confirm the script exists at the exact path in `ExecStart`:
  ```bash
  ls -la /workspace/indomitus-drone-ros2/scripts/record_mission.sh
  ```
- Script is not executable:
  ```bash
  chmod +x /workspace/indomitus-drone-ros2/scripts/record_mission.sh
  ```

---

### 9.5 Pi Powers Off Before Recording Starts

**Symptom:** The Pi boots and shuts down in under 10 seconds with no video file.

**Cause:** The script likely hit an early error (missing directory, permission denied) and jumped to `poweroff`.

**Fix:** Temporarily disable poweroff (see §7.3), then run the script manually to see the error:

```bash
sudo /workspace/indomitus-drone-ros2/scripts/record_mission.sh
```

---

### 9.6 `TimeoutStartSec` Kills the Service Early

**Symptom:** Recording stops before `DURATION` seconds. Journal shows `Timeout`.

**Fix:** The service file's `TimeoutStartSec` must be larger than `DURATION` plus ffmpeg time. Update it and reload:

```bash
sudo nano /etc/systemd/system/drone-record.service
# Change: TimeoutStartSec=<DURATION + 60>

sudo systemctl daemon-reload
```

---

### 9.7 SD Card Performance / Write Speed Issues

The IMX708 at 1080p 30fps writes roughly **10 Mbps** continuously. Slow or aging SD cards can cause dropped frames or corrupt files.

**Recommendations:**

- Use a **Class 10 / U3 / A2** rated SD card (e.g. Samsung PRO Endurance, SanDisk Extreme).
- Avoid cheap no-brand cards — they degrade quickly under constant write load.
- Check write speed before trusting a card:
  ```bash
  dd if=/dev/zero of=/workspace/speedtest bs=1M count=200 oflag=direct
  # Expect at least 20 MB/s for reliable 1080p recording
  rm /workspace/speedtest
  ```

---

### 9.8 5V BEC / Power Supply Issues

The Raspberry Pi 5 requires a **stable 5V @ 5A** supply. Voltage dips during motor spin-up can cause unexpected reboots mid-recording.

**Checks:**

```bash
# Check for undervoltage events in current boot log
dmesg | grep -i "voltage\|throttl"

# Or via vcgencmd
vcgencmd get_throttled
# 0x0 means no issues; any other value indicates throttling or undervoltage
```

**Fixes:**

- Add a **capacitor** (470–1000µF, 6.3V) across the BEC output to smooth transient dips.
- Route BEC power directly to the Pi's GPIO 5V pins (pins 2/4 + GND), not via USB-C, to avoid the USB power negotiation overhead.
- Make sure Dupont connectors are fully seated and the wire gauge is sufficient for 5A (at least 22 AWG).

---

### 9.9 `workspace` Filesystem Not Mounted at Boot Time

**Symptom:** Service starts but log says `mkdir: cannot create directory … Permission denied` or `No such file or directory` for `/workspace`.

**Cause:** If `/workspace` is on a separate partition or USB drive, it may not be mounted when the service starts.

**Fix:** Add a mount dependency to the service file:

```ini
[Unit]
After=multi-user.target local-fs.target
RequiresMountsFor=/workspace
```

Then reload:

```bash
sudo systemctl daemon-reload
```

---

### 9.10 HDR Mode Causes Lower Frame Rate

**Symptom:** Video is recorded at fewer FPS than configured, or `libcamera-vid` warns about frame rate.

**Cause:** The IMX708's HDR mode merges two exposures and limits the sensor to approximately **15 fps** at full resolution.

**Fix:** Either disable HDR for smooth 30fps:

```bash
# In record_mission.sh, remove the --hdr flag
```

Or keep HDR and lower FPS to match the sensor limit:

```bash
FPS=15
# and remove --hdr from libcamera-vid call
```

---

## Quick Reference Card

```
ENABLE SERVICE          sudo systemctl enable drone-record.service
DISABLE SERVICE         sudo systemctl disable drone-record.service
CHECK STATUS            sudo systemctl status drone-record.service
VIEW LIVE LOGS          journalctl -fu drone-record.service
VIEW BOOT LOGS          journalctl -u drone-record.service -b
READ SCRIPT LOG         cat /workspace/indomitus-drone-ros2/record_mission.log
MANUAL TEST RUN         sudo systemctl start drone-record.service
RUN SCRIPT DIRECTLY     sudo /workspace/indomitus-drone-ros2/scripts/record_mission.sh
CHECK CAMERA            libcamera-hello --list-cameras
CHECK FREE SPACE        df -h /workspace
CHECK UNDERVOLTAGE      vcgencmd get_throttled
```