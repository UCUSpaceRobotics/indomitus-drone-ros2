#!/usr/bin/env python3
"""Capture chessboard calibration images from a live camera feed."""

from pathlib import Path
import argparse
import sys
import time

import cv2


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.cv.camera import Camera


DEFAULT_OUTPUT_DIR = "media/calibration"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Show live camera frames and save snapshots for calibration."
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--backend", choices=("picamera2", "opencv"), default="picamera2")
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument("--prefix", default="calibration")
    return parser.parse_args()


def next_image_path(output_dir, prefix):
    existing = sorted(output_dir.glob(f"{prefix}_*.png"))
    if not existing:
        return output_dir / f"{prefix}_001.png"

    highest = 0
    for path in existing:
        suffix = path.stem.removeprefix(f"{prefix}_")
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return output_dir / f"{prefix}_{highest + 1:03d}.png"


def draw_status(frame, message):
    cv2.putText(
        frame,
        message,
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )
    return frame


def close_windows():
    try:
        cv2.destroyAllWindows()
    except cv2.error:
        pass


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    camera = Camera(
        width=args.width,
        height=args.height,
        backend=args.backend,
        device_index=args.device_index,
    )

    print(f"[CALIB_CAPTURE] Saving snapshots to: {output_dir}")
    print("[CALIB_CAPTURE] Press Space or Enter to save; press q or Esc to quit.")

    saved_count = 0
    last_saved_at = 0.0

    try:
        while True:
            frame = camera.get_frame()
            display = frame.copy()

            if time.time() - last_saved_at < 1.0:
                status = f"saved {saved_count} images"
            else:
                status = "Space/Enter: save  q/Esc: quit"
            draw_status(display, status)

            try:
                cv2.imshow("Camera calibration capture", display)
                key = cv2.waitKey(1) & 0xFF
            except cv2.error as exc:
                raise RuntimeError(
                    "OpenCV GUI is unavailable. Install opencv-contrib-python "
                    "instead of opencv-contrib-python-headless, or run this "
                    "script from a graphical desktop session."
                ) from exc

            if key in (ord("q"), 27):
                break
            if key in (ord(" "), 13):
                path = next_image_path(output_dir, args.prefix)
                if not cv2.imwrite(str(path), frame):
                    raise RuntimeError(f"Could not save image: {path}")
                saved_count += 1
                last_saved_at = time.time()
                print(f"[CALIB_CAPTURE] saved {path}")
    finally:
        camera.release()
        close_windows()


if __name__ == "__main__":
    main()
