# Camera Calibration and ArUco Bench Recording (Raspberry Pi)

This guide is tailored to the downward-facing drone camera and the scripts in this repo. It covers capturing calibration images, computing the calibration file, and recording annotated ArUco detections using `scripts/bench_aruco.py`.

## 1) Prerequisites

- Run these steps on the Raspberry Pi that hosts the camera.
- Python dependencies (from requirements.txt):
  - `numpy`
  - `opencv-contrib-python-headless` (ArUco support)
- If you want on-screen preview windows, install non-headless OpenCV:
  - `opencv-python` (replace headless) so `cv2.imshow` works.

Example setup (Pi):

```bash
cd /workspace/indomitus-drone-ros2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you want GUI preview windows:

```bash
pip uninstall -y opencv-contrib-python-headless
pip install opencv-contrib-python
```

## 2) Capture Calibration Images

Use a printed chessboard with **known square size**. The script expects the **inner corner** count (not the number of squares).

Tips for good calibration images:
- Fill most of the frame with the board, but vary scale and distance.
- Tilt and rotate the board to cover different viewing angles.
- Avoid motion blur; keep the board still when capturing.
- Use even lighting; avoid glare and reflections.
- Capture at least 10-20 good images (minimum is 5).

Command (example):

```bash
source .venv/bin/activate
python3 scripts/capture_calibration_images.py \
  --output-dir media/calibration \
  --width 640 \
  --height 480 \
  --backend picamera2 \
  --device-index 0 \
  --prefix calibration
```

Controls:
- Press `Space` or `Enter` to save a frame.
- Press `q` or `Esc` to quit.

If you are using a USB camera, switch the backend:

```bash
python3 scripts/capture_calibration_images.py --backend opencv --device-index 0
```

## 3) Compute Calibration File

You must know:
- `--cols`: inner corners per row
- `--rows`: inner corners per column
- `--square-size-m`: square size in meters

Example for a 9x7 inner-corner board with 35 mm squares:

```bash
source .venv/bin/activate
python3 scripts/calibrate_camera.py \
  --image-dir media/calibration \
  --output camera_calibration.npz \
  --cols 9 \
  --rows 7 \
  --square-size-m 0.035
```

This produces `camera_calibration.npz` (used by `bench_aruco.py`).

Optional preview of detected corners:

```bash
python3 scripts/calibrate_camera.py \
  --image-dir media/calibration \
  --output camera_calibration.npz \
  --cols 9 \
  --rows 7 \
  --square-size-m 0.035 \
  --show
```

## 4) Bench ArUco Detection (Live Preview)

Run with calibration to enable pose estimation and distance labels.

```bash
source .venv/bin/activate
python3 scripts/bench_aruco.py \
  --calibration camera_calibration.npz \
  --width 640 \
  --height 480 \
  --backend picamera2 \
  --device-index 0
```

Headless mode (no GUI windows):

```bash
python3 scripts/bench_aruco.py \
  --calibration camera_calibration.npz \
  --no-display
```

## 5) Record Annotated Video with `bench_aruco.py`

The script records **annotated frames** (markers + distance labels) to MP4. It writes to RAM first (`/dev/shm`) and then moves the file to the final path.

Record for 60 seconds, save to repo root:

```bash
source .venv/bin/activate
python3 scripts/bench_aruco.py \
  --calibration camera_calibration.npz \
  --record \
  --duration 60 \
  --record-output /workspace/indomitus-drone-ros2/aruco_bench_60s.mp4 \
  --record-fps 30 \
  --backend picamera2 \
  --device-index 0 \
  --no-display
```

Use a different temp directory if `/dev/shm` is small:

```bash
python3 scripts/bench_aruco.py \
  --calibration camera_calibration.npz \
  --record \
  --record-temp-dir /tmp \
  --no-display
```

Stop recording early:
- If a preview window is open, press `q` or `Esc`.
- In headless mode, press `Ctrl+C` in the terminal.

The script always finalizes the file on exit and moves it from the temp path to the final output path.

## 6) Download the Video to Your Computer

Where to find the file on the Pi:
- If you used `--record-output`, the video is saved exactly at that path.
- Otherwise it is saved in the repo root as `aruco_bench_YYYYMMDD_HHMMSS.mp4`.

Example locations on the Pi:
- `/workspace/indomitus-drone-ros2/aruco_bench_60s.mp4`
- `/workspace/indomitus-drone-ros2/aruco_bench_YYYYMMDD_HHMMSS.mp4`

Download with `scp` from your computer (PowerShell):

```bash
scp pi@<PI_IP>:/workspace/indomitus-drone-ros2/aruco_bench_60s.mp4 C:\Users\<YOU>\Downloads\
```

Download a specific file name by replacing the remote path:

```bash
scp pi@<PI_IP>:/workspace/indomitus-drone-ros2/aruco_bench_YYYYMMDD_HHMMSS.mp4 C:\Users\<YOU>\Downloads\
```

## 7) Common Problems and How to Fix Them

- **No GUI window / OpenCV GUI error**
  - Cause: `opencv-contrib-python-headless` does not include GUI.
  - Fix: install `opencv-contrib-python` and remove headless.
  - Workaround: use `--no-display`.

- **No camera detected (picamera2)**
  - Cause: camera not enabled or not detected by libcamera.
  - Fix: enable camera interface, check `libcamera-hello --list-cameras`.
  - Workaround: try `--backend opencv` if using USB camera.

- **Chessboard corners not found**
  - Cause: wrong `--cols/--rows`, glare, low contrast, or blur.
  - Fix: verify inner-corner counts, improve lighting, reprint board, use sharper images.

- **High RMS reprojection error**
  - Cause: poor image variety or motion blur.
  - Fix: capture more images with varied angles and distances.

- **ArUco pose is missing**
  - Cause: no calibration provided or invalid calibration file.
  - Fix: pass `--calibration camera_calibration.npz` and verify the file.

- **Recording file is empty or missing**
  - Cause: not enough RAM in `/dev/shm` or script terminated before release.
  - Fix: use `--record-temp-dir /tmp`, avoid sudden power loss, let it exit cleanly.

- **Low FPS / dropped frames**
  - Cause: heavy CPU load or high resolution.
  - Fix: lower `--width/--height`, increase `--interval`, or reduce display overhead.

## 8) On-Site Recording Checklist

- Confirm camera is detected: `libcamera-hello --list-cameras`.
- Verify calibration file exists: `ls -l camera_calibration.npz`.
- Ensure enough free space or RAM temp: `df -h` and check `/dev/shm` or use `--record-temp-dir /tmp`.
- Decide recording duration and output path.
- Run a short 5-10s test recording to validate exposure and focus.
- Start the full recording command and wait for it to finish cleanly.

## 9) Quick Reference Commands

Capture images:

```bash
python3 scripts/capture_calibration_images.py --backend picamera2
```

Calibrate:

```bash
python3 scripts/calibrate_camera.py --cols 9 --rows 7 --square-size-m 0.035
```

Record annotated video:

```bash
python3 scripts/bench_aruco.py --calibration camera_calibration.npz --record --duration 60 --no-display
```
