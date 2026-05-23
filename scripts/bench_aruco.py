#!/usr/bin/env python3
"""Bench-test mission ArUco detection with an image file or Pi camera."""

from pathlib import Path
import argparse
import sys
import time

import cv2


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.cv.aruco import ARUCO_DICTIONARIES, ArucoDetector, MISSION_MARKER_IDS
from src.cv.camera import CameraCalibration


def parse_args():
    parser = argparse.ArgumentParser(
        description="Detect ArUco or AprilTag markers from an image or camera."
    )
    parser.add_argument(
        "--calibration",
        help="Optional camera calibration file (.npz, .yml, or .xml).",
    )
    parser.add_argument(
        "--image",
        help="Optional image path. If omitted, the script uses the selected camera backend.",
    )
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--backend", choices=("picamera2", "opencv"), default="picamera2")
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument(
        "--dictionary",
        choices=tuple(sorted(ARUCO_DICTIONARIES)),
        default="aruco_original",
    )
    parser.add_argument(
        "--marker-id",
        action="append",
        type=int,
        help="Marker ID to detect. Repeat to allow multiple IDs. Defaults to mission IDs.",
    )
    parser.add_argument(
        "--all-markers",
        action="store_true",
        help="Detect every marker in the selected dictionary instead of filtering by ID.",
    )
    parser.add_argument("--duration", type=float, default=0.0)
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--no-display", action="store_true")
    return parser.parse_args()


def show_frame(window_name, frame, wait_ms):
    try:
        cv2.imshow(window_name, frame)
        key = cv2.waitKey(wait_ms) & 0xFF
        return True, key in (ord("q"), 27)
    except cv2.error:
        print(
            "[ARUCO_BENCH] OpenCV GUI is unavailable. "
            "Install opencv-python instead of opencv-python-headless to use --display."
        )
        return False, False


def close_windows():
    try:
        cv2.destroyAllWindows()
    except cv2.error:
        pass


def format_detection(detection):
    pose = "pose=unavailable"
    if detection.has_pose:
        x_m, y_m, z_m = detection.tvec
        pose = f"tvec=({x_m:+.3f}, {y_m:+.3f}, {z_m:+.3f}) m"

    x_px, y_px = detection.center_px
    return f"id={detection.marker_id} center=({x_px:.1f}, {y_px:.1f}) px {pose}"


def selected_marker_ids(args):
    if args.all_markers:
        return None
    if args.marker_id:
        return args.marker_id
    return MISSION_MARKER_IDS


def main():
    args = parse_args()
    marker_ids = selected_marker_ids(args)
    calibration = (
        CameraCalibration.from_file(args.calibration)
        if args.calibration
        else None
    )

    if args.image:
        detector = ArucoDetector(
            calibration=calibration,
            marker_ids=marker_ids,
            dictionary_id=args.dictionary,
        )
        frame = cv2.imread(args.image)
        if frame is None:
            raise SystemExit(f"Could not read image: {args.image}")

        detections = detector.detect(frame)
        if detections:
            print("[ARUCO_BENCH] " + " | ".join(map(format_detection, detections)))
        else:
            print("[ARUCO_BENCH] no mission markers detected")

        if not args.no_display:
            display_available, _ = show_frame(
                "ArUco detection",
                detector.draw_detections(frame, detections),
                0,
            )
            if display_available:
                close_windows()
        return

    from src.cv.camera import Camera

    camera = Camera(
        width=args.width,
        height=args.height,
        calibration=calibration,
        backend=args.backend,
        device_index=args.device_index,
    )
    detector = ArucoDetector(
        calibration=camera.calibration,
        marker_ids=marker_ids,
        dictionary_id=args.dictionary,
    )
    started_at = time.time()

    print(
        f"[ARUCO_BENCH] Looking for markers with dictionary {args.dictionary}. "
        "Press Ctrl+C to stop."
    )
    if calibration is None:
        print("[ARUCO_BENCH] No calibration supplied; reporting 2D centers only.")

    display_available = not args.no_display

    try:
        while True:
            frame = camera.get_frame()
            detections = detector.detect(frame)

            if detections:
                print("[ARUCO_BENCH] " + " | ".join(map(format_detection, detections)))
            else:
                print("[ARUCO_BENCH] no mission markers detected")

            if display_available:
                display_available, should_quit = show_frame(
                    "ArUco detection",
                    detector.draw_detections(frame, detections),
                    1,
                )
                if should_quit:
                    break

            if args.duration > 0 and time.time() - started_at >= args.duration:
                break

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[ARUCO_BENCH] stopped by operator")
    finally:
        camera.release()
        if display_available:
            close_windows()


if __name__ == "__main__":
    main()
