#!/bin/bash

# Wait for boot
sleep 5

FILENAME="downward_demo_$(date +'%Y-%m-%d_%H-%M-%S').mp4"
TEMP_PATH="/dev/shm/$FILENAME"
FINAL_PATH="/workspace/indomitus-drone-ros2/$FILENAME"

# ==========================================
# FILE TRANSFER FUNCTION
# ==========================================
# This function runs automatically when the timer ends OR if you stop the service.
save_video() {
    echo "Stopping recording and moving file from RAM to SD card..."
    
    # Check if the file exists in RAM, then move it to the workspace
    if [ -f "$TEMP_PATH" ]; then
        mv "$TEMP_PATH" "$FINAL_PATH"
        echo "Video successfully saved to $FINAL_PATH"
    fi
    exit 0
}

# Trap termination signals so we don't lose the video if stopped via SSH
trap save_video SIGINT SIGTERM

# ==========================================
# RECORD TO RAM
# ==========================================
# We run rpicam-vid in the background (using &) and then wait for it.
# This allows the trap above to listen for your stop commands.
rpicam-vid -t 120000 --width 1920 --height 1080 --framerate 30 --bitrate 4000000 --inline --codec libav -o "$TEMP_PATH" &

# Wait for the background recording process to finish naturally
wait $!

# If the 3 minutes complete naturally, trigger the save function
save_video