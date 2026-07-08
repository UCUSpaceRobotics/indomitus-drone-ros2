# Camera Calibration Guide

This guide describes how to capture chessboard calibration frames, compute
`camera_calibration.npz`, and verify the result with AprilTag/ArUco pose
estimation.

## 1. Prepare The Environment

From the repository root:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Raspberry Pi, Picamera2 is normally installed from apt, not pip:

```bash
sudo apt install python3-picamera2
```

The capture script uses an OpenCV display window. Run it from a graphical
desktop session, not a headless SSH-only terminal. If OpenCV GUI support is
missing, install a GUI-capable OpenCV package for capture.

If you want the Raspberry Pi OpenCV window to appear on your laptop, connect
with X11 forwarding:

```bash
ssh -AX <username>@<ip>
```

This requires an X server running on the laptop. On Linux this usually works
from a normal graphical session. On macOS or Windows, install and start an X
server first.

## 2. Capture Calibration Frames

Use the same resolution you plan to use for marker detection. For the current
bench pipeline:

```bash
python3 scripts/capture_calibration_images.py \
    --output-dir media/calibration \
    --width 1920 \
    --height 1080 \
    --backend picamera2 \
    --device-index 0 \
    --prefix calibration
```

Controls:

- Press `Space` or `Enter` to save a frame.
- Press `q` or `Esc` to quit.
- Frames are saved under `media/calibration`.

## 3. What Frames To Capture

Use a flat chessboard calibration target with known square size. The
`--cols` and `--rows` values used later are the number of inner corners, not
the number of printed squares.

Capture at least 25 to 40 sharp images. More is useful if the board covers
different parts of the image. Avoid blurry frames, glare, partial occlusion,
and frames where the chessboard is almost edge-on.

Cover the full image:

- Board centered in the image.
- Board near the top.
- Board near the bottom.
- Board near the left edge.
- Board near the right edge.
- Board near each corner: top-left, top-right, bottom-left, bottom-right.

For each position, repeat with board tilt:

- Board parallel to the camera.
- Tilted upward by about 15 to 30 degrees.
- Tilted downward by about 15 to 30 degrees.
- Tilted left by about 15 to 30 degrees.
- Tilted right by about 15 to 30 degrees.

Vary distance:

- Close: board fills most of the frame but all inner corners are visible.
- Medium: board fills roughly half the frame.
- Far: board fills roughly one quarter to one third of the frame.

Vary rotation in the image plane:

- Normal horizontal/vertical orientation.
- Rotated clockwise about 20 to 45 degrees.
- Rotated counter-clockwise about 20 to 45 degrees.

Good calibration sets usually include:

- Corners and edges of the image, not only the middle.
- Several board angles, not only front-facing shots.
- Several distances, not only one depth.
- Sharp images with even lighting.
- The full chessboard visible in every saved frame.

## 4. Run Calibration

Measure one printed square on the chessboard in meters. У Пана Олександра дошка з розміром клітинки `35mm`, то вводиш `0.035`. Перевір провсяк, може помиляюсь

Then run calibration. Replace `--cols`, `--rows`, and `--square-size-m` with
your board values:

```bash
python3 scripts/calibrate_camera.py \
    --image-dir media/calibration \
    --output camera_calibration.npz \
    --cols 8 \
    --rows 6 \
    --square-size-m 0.035
```

Optional visual check while calibrating:

```bash
python3 scripts/calibrate_camera.py \
    --image-dir media/calibration \
    --output camera_calibration.npz \
    --cols 9 \
    --rows 6 \
    --square-size-m 0.035 \
    --show
```

The script prints accepted images, skipped images, the RMS reprojection error,
and saves `camera_calibration.npz`.

Lower RMS is better, but do not judge calibration from RMS alone. A low RMS
from many nearly identical center-only frames can still produce poor marker
pose estimates near the image edges. If RMS is high or marker pose looks
unstable, remove blurry/bad frames and capture more images with better edge,
corner, tilt, and distance coverage.

## 5. Verify With Marker Pose Recording

After calibration, run the ArUco/AprilTag benchmark with the calibration file.
This command records annotated video to RAM first, then saves the completed MP4
to the repository directory:

```bash
python3 scripts/bench_aruco.py \
    --calibration camera_calibration.npz \
    --width 1920 \
    --height 1080 \
    --backend picamera2 \
    --dictionary apriltag_36h11 \
    --marker-id 13 \
    --marker-id 14 \
    --duration 120 \
    --interval 0.0 \
    --record \
    --record-output aruco_bench_$(date +'%Y-%m-%d_%H-%M-%S').mp4 \
    --record-temp-dir /dev/shm \
    --record-fps 20
```

Command explanation:

- `--calibration camera_calibration.npz` loads the calibration computed above.
- `--width 1920 --height 1080` uses the same resolution as calibration capture.
- `--backend picamera2` uses the Raspberry Pi camera pipeline.
- `--dictionary apriltag_36h11` selects the marker family.
- `--marker-id 13 --marker-id 14` limits detection to the mission test markers.
- `--duration 120` records for 120 seconds.
- `--interval 0.0` processes frames without intentional sleep.
- `--record` enables MP4 recording.
- `--record-output ...mp4` names the final video using a timestamp.
- `--record-temp-dir /dev/shm` writes the active recording to RAM first.
- `--record-fps 20` sets the output video FPS metadata.

Watch the logs while moving the marker through the image. The script prints
marker center and estimated translation vector. The video should show stable
marker outlines and pose axes when the marker is visible.

## 6. Practical Quality Checks

After calibration, test a marker at known distances such as 0.5 m, 1.0 m, and
1.5 m. The estimated `z` distance should be reasonably close. Small errors are
normal; large or direction-dependent errors usually mean one of these problems:

- Wrong chessboard `--cols` or `--rows`.
- Wrong `--square-size-m`.
- Calibration images captured at a different resolution than detection.
- Too many center-only calibration frames.
- Not enough tilted or edge/corner frames.
- Blurry images or rolling-shutter motion during capture.
- Board not flat.

When in doubt, recapture a balanced set of sharp images and recalibrate.
