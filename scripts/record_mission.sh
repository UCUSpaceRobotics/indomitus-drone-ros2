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

# Ensure the target directory exists
mkdir -p "$SAVE_DIR"

log "=== Mission recording started ==="
log "Output : $OUTPUT"
log "Duration: ${DURATION}s  |  ${WIDTH}x${HEIGHT} @ ${FPS}fps"

# Wait a few seconds for the OS and camera stack to fully settle after boot
sleep 5

# Start recording
# --timeout  : recording duration in milliseconds
# --codec h264: hardware-accelerated H.264 encoding
# --width/--height/--framerate: resolution & FPS
# --autofocus-mode continuous: keeps the IMX708 autofocus active
# --hdr      : enable HDR mode available on IMX708
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
    # Optional: wrap in a proper MP4 container so it plays everywhere.
    # Requires: sudo apt install -y ffmpeg
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
        log "Install with:  sudo apt install -y ffmpeg"
    fi
else
    log "ERROR: libcamera-vid exited with code $EXIT_CODE"
fi

log "Syncing filesystem …"
sync

log "Powering off Raspberry Pi."
/sbin/poweroff