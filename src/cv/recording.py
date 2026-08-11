"""Write timestamped OpenCV recordings through a temporary file.

Basic usage::

    import time

    from src.cv.recording import RecordingWriter, temporary_recording_path

    output_path = "recording.mp4"
    recorder = RecordingWriter(
        output_path,
        temporary_recording_path(output_path, "/dev/shm"),
        fps=30,
        frame_shape=first_frame.shape,
        started_at=time.time(),
    )
    recorder.write_until(frame, time.time())
    recorder.release()
"""

from datetime import datetime
import os
from pathlib import Path
import shutil

import cv2


def timestamped_recording_path(directory, prefix="recording", suffix=".mp4"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(directory) / f"{prefix}_{timestamp}{suffix}"


def temporary_recording_path(final_path, temp_dir):
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir / f".{Path(final_path).name}.{os.getpid()}.tmp.mp4"


class RecordingWriter:
    """Write frames at fixed FPS, then move completed video to its final path."""

    def __init__(self, path, temp_path, fps, frame_shape, started_at):
        self.path = Path(path)
        self.temp_path = Path(temp_path)
        self.fps = float(fps)
        self.started_at = float(started_at)
        self.frames_written = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.temp_path.parent.mkdir(parents=True, exist_ok=True)

        height, width = frame_shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(
            str(self.temp_path),
            fourcc,
            self.fps,
            (width, height),
        )
        if not self._writer.isOpened():
            raise RuntimeError(f"Could not open video writer: {self.temp_path}")

    def write_until(self, frame, recorded_at):
        target_frame_count = max(
            1,
            int(round((recorded_at - self.started_at) * self.fps)),
        )
        while self.frames_written < target_frame_count:
            self._writer.write(frame)
            self.frames_written += 1

    def release(self):
        self._writer.release()
        shutil.move(str(self.temp_path), str(self.path))
