#!/usr/bin/env python3
"""Annotate an MP4 with ArUco detections."""

from __future__ import annotations

from pathlib import Path
import argparse
import sys

import cv2

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.cv.aruco import ARUCO_DICTIONARIES, ArucoDetector


def parse_args():
    parser = argparse.ArgumentParser(
        description="Detect ArUco/AprilTag markers in an MP4 and save an annotated video."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input MP4 path (relative to repo root or absolute).",
    )
    parser.add_argument(
        "--output",
        help="Output MP4 path. Defaults to <input>_aruco.mp4 in the same folder.",
    )
    parser.add_argument(
        "--dictionary",
        choices=tuple(sorted(ARUCO_DICTIONARIES)),
        default="apriltag_36h11",
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
        help="Detect every marker in the dictionary instead of filtering by ID.",
    )
    parser.add_argument(
        "--output-fps",
        type=float,
        default=0.0,
        help="Optional override for output FPS. Use 0 to keep input FPS.",
    )
    return parser.parse_args()


def resolve_input_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_aruco{input_path.suffix}")


def selected_marker_ids(args):
    if args.all_markers:
        return None
    if args.marker_id:
        return args.marker_id
    return [13, 14]


def draw_marker_frame(frame, detection):
    corners = detection.corners
    if corners is None or len(corners) != 4:
        return
    points = corners.reshape((-1, 1, 2)).astype(int)
    cv2.polylines(frame, [points], isClosed=True, color=(0, 255, 0), thickness=2)


def annotate_frame(frame, detections):
    annotated = frame.copy()
    for detection in detections:
        draw_marker_frame(annotated, detection)
    return annotated


def tune_detector_parameters(parameters):
    if hasattr(parameters, "adaptiveThreshWinSizeMin"):
        parameters.adaptiveThreshWinSizeMin = 3
    if hasattr(parameters, "adaptiveThreshWinSizeMax"):
        parameters.adaptiveThreshWinSizeMax = 73
    if hasattr(parameters, "adaptiveThreshWinSizeStep"):
        parameters.adaptiveThreshWinSizeStep = 4
    if hasattr(parameters, "adaptiveThreshConstant"):
        parameters.adaptiveThreshConstant = 9
    if hasattr(parameters, "minMarkerPerimeterRate"):
        parameters.minMarkerPerimeterRate = 0.01
    if hasattr(parameters, "maxMarkerPerimeterRate"):
        parameters.maxMarkerPerimeterRate = 4.0
    if hasattr(parameters, "minCornerDistanceRate"):
        parameters.minCornerDistanceRate = 0.02
    if hasattr(parameters, "minDistanceToBorder"):
        parameters.minDistanceToBorder = 0
    if hasattr(parameters, "minOtsuStdDev"):
        parameters.minOtsuStdDev = 3.0
    if hasattr(parameters, "errorCorrectionRate"):
        parameters.errorCorrectionRate = 0.9
    if hasattr(parameters, "cornerRefinementMethod") and hasattr(cv2.aruco, "CORNER_REFINE_SUBPIX"):
        parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    if hasattr(parameters, "cornerRefinementWinSize"):
        parameters.cornerRefinementWinSize = 7
    if hasattr(parameters, "cornerRefinementMaxIterations"):
        parameters.cornerRefinementMaxIterations = 50
    if hasattr(parameters, "cornerRefinementMinAccuracy"):
        parameters.cornerRefinementMinAccuracy = 0.01
    if hasattr(parameters, "detectInvertedMarker"):
        parameters.detectInvertedMarker = True
    if hasattr(parameters, "useAruco3Detection"):
        parameters.useAruco3Detection = True


def main():
    args = parse_args()
    input_path = resolve_input_path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    output_path = resolve_input_path(args.output) if args.output else default_output_path(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    marker_ids = selected_marker_ids(args)
    detector = ArucoDetector(
        calibration=None,
        marker_ids=marker_ids,
        dictionary_id=args.dictionary,
    )
    tune_detector_parameters(detector.parameters)

    capture = cv2.VideoCapture(str(input_path))
    if not capture.isOpened():
        raise SystemExit(f"Could not open video: {input_path}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 30.0
    if args.output_fps and args.output_fps > 0:
        fps = float(args.output_fps)

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise SystemExit(f"Could not open video writer: {output_path}")

    frame_index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frame_index += 1
            detections = detector.detect(frame)
            annotated = annotate_frame(frame, detections)
            writer.write(annotated)
            if frame_index % 120 == 0:
                print(f"[ARUCO_VIDEO] processed {frame_index} frames")
    finally:
        capture.release()
        writer.release()

    print(f"[ARUCO_VIDEO] Saved annotated video to {output_path}")


if __name__ == "__main__":
    main()
