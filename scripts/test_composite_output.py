#!/usr/bin/env python3
"""Smoke-test live camera output on the Raspberry Pi display stack."""

from pathlib import Path
import argparse
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.cv.camera import Camera
from src.cv.display import VideoDisplay, VideoDisplayConfig


def parse_args():
    parser = argparse.ArgumentParser(
        description="Show live camera frames on the active display output."
    )
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--backend", choices=("picamera2", "opencv"), default="picamera2")
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument(
        "--window-name",
        default="Composite output test",
        help="Window title used by the display sink.",
    )
    parser.add_argument(
        "--no-fullscreen",
        action="store_true",
        help="Disable fullscreen mode for the display sink.",
    )
    parser.add_argument(
        "--disabled",
        action="store_true",
        help="Run the loop without opening a display window.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    camera = Camera(
        width=args.width,
        height=args.height,
        backend=args.backend,
        device_index=args.device_index,
    )
    display = VideoDisplay(
        VideoDisplayConfig(
            window_name=args.window_name,
            fullscreen=not args.no_fullscreen,
            enabled=not args.disabled,
        )
    )

    print("[COMPOSITE_TEST] Press q or Esc to quit.")

    try:
        while True:
            frame = camera.get_frame()
            key = display.show(frame, wait_ms=1)
            if key in (ord("q"), 27):
                break
    finally:
        camera.release()
        display.close()


if __name__ == "__main__":
    main()