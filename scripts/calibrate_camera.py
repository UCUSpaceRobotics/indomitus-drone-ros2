#!/usr/bin/env python3
"""Compute camera calibration parameters from saved chessboard images."""

from pathlib import Path
import argparse
import sys

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


DEFAULT_IMAGE_DIR = "media/calibration"
DEFAULT_OUTPUT = "camera_calibration.npz"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Calibrate a camera from chessboard images."
    )
    parser.add_argument("--image-dir", default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--cols",
        type=int,
        required=True,
        help="Number of inner chessboard corners per row.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        required=True,
        help="Number of inner chessboard corners per column.",
    )
    parser.add_argument(
        "--square-size-m",
        type=float,
        required=True,
        help="Physical chessboard square size in meters.",
    )
    parser.add_argument("--show", action="store_true")
    return parser.parse_args()


def image_paths(image_dir):
    extensions = ("*.jpg", "*.jpeg", "*.png", "*.bmp")
    paths = []
    for extension in extensions:
        paths.extend(image_dir.glob(extension))
    return sorted(paths)


def build_object_points(cols, rows, square_size_m):
    points = np.zeros((rows * cols, 3), np.float32)
    points[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
    return points * square_size_m


def main():
    args = parse_args()
    image_dir = Path(args.image_dir)
    paths = image_paths(image_dir)
    if not paths:
        raise SystemExit(f"No calibration images found in: {image_dir}")

    pattern_size = (args.cols, args.rows)
    object_template = build_object_points(args.cols, args.rows, args.square_size_m)
    object_points = []
    image_points = []
    image_size = None

    print(f"[CALIBRATE] Reading {len(paths)} images from {image_dir}")

    for path in paths:
        image = cv2.imread(str(path))
        if image is None:
            print(f"[CALIBRATE] skipped unreadable image: {path}")
            continue

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        image_size = gray.shape[::-1]
        found, corners = cv2.findChessboardCorners(gray, pattern_size)

        if not found:
            print(f"[CALIBRATE] no chessboard corners: {path}")
            continue

        refined = cv2.cornerSubPix(
            gray,
            corners,
            (11, 11),
            (-1, -1),
            (
                cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                30,
                0.001,
            ),
        )
        object_points.append(object_template)
        image_points.append(refined)
        print(f"[CALIBRATE] accepted: {path}")

        if args.show:
            preview = image.copy()
            cv2.drawChessboardCorners(preview, pattern_size, refined, found)
            cv2.imshow("Calibration corners", preview)
            if cv2.waitKey(250) & 0xFF in (ord("q"), 27):
                break

    if args.show:
        cv2.destroyAllWindows()

    if len(object_points) < 5:
        raise SystemExit(
            "Need at least 5 valid chessboard images for calibration; "
            f"found {len(object_points)}."
        )

    rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        object_points,
        image_points,
        image_size,
        None,
        None,
    )

    output = Path(args.output)
    np.savez(
        output,
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
        image_size=np.array(image_size),
        rms=np.array(rms),
        rvecs=np.array(rvecs, dtype=object),
        tvecs=np.array(tvecs, dtype=object),
    )

    print(f"[CALIBRATE] valid images: {len(object_points)}")
    print(f"[CALIBRATE] RMS reprojection error: {rms:.6f}")
    print(f"[CALIBRATE] saved: {output}")


if __name__ == "__main__":
    main()
