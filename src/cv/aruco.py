"""Detect configured ArUco markers in OpenCV images.

Basic usage::

    import cv2

    from src.cv.aruco import ArucoDetector

    frame = cv2.imread("marker.jpg")
    detector = ArucoDetector(marker_ids={13, 14})
    detections = detector.detect(frame)

    for detection in detections:
        print(detection.marker_id, detection.center_px)

    annotated_frame = detector.draw_detections(frame, detections)

Pass camera calibration to ``ArucoDetector`` to populate each detection's
``rvec`` and ``tvec`` pose fields.
"""

from dataclasses import dataclass

import cv2
import numpy as np


MISSION_MARKER_IDS = {
    "origin": 13,
    "landing_target": 14,
    "real_origin": 101,
    "real_landing_target": 102,
}
DEFAULT_MARKER_SIZE_M = 0.15
ARUCO_DICTIONARIES = {
    "aruco_original": cv2.aruco.DICT_ARUCO_ORIGINAL,
    "apriltag_36h11": cv2.aruco.DICT_APRILTAG_36h11,
}


@dataclass(frozen=True)
class ArucoDetection:
    marker_id: int
    corners: np.ndarray
    center_px: tuple[float, float]
    marker_size_m: float = DEFAULT_MARKER_SIZE_M
    rvec: tuple[float, float, float] | None = None
    tvec: tuple[float, float, float] | None = None

    @property
    def has_pose(self):
        return self.rvec is not None and self.tvec is not None

    def distance_m(self):
        """Return straight-line camera-to-marker distance, or None without pose."""
        if self.tvec is None:
            return None
        return float(np.linalg.norm(self.tvec))


class ArucoDetector:
    def __init__(
        self,
        calibration=None,
        marker_size_m=DEFAULT_MARKER_SIZE_M,
        marker_ids=MISSION_MARKER_IDS,
        dictionary_id=None,
    ):
        if not hasattr(cv2, "aruco"):
            raise RuntimeError(
                "OpenCV ArUco module is unavailable. Install opencv-contrib-python-headless."
            )

        self.calibration = calibration
        self.marker_size_m = float(marker_size_m)
        self.marker_ids = self._normalize_marker_ids(marker_ids)
        self.dictionary_id = self._normalize_dictionary_id(dictionary_id)
        self.dictionary = cv2.aruco.getPredefinedDictionary(self.dictionary_id)
        self.parameters = self._create_detector_parameters()
        self.detector = self._create_detector()

    def _normalize_marker_ids(self, marker_ids):
        if marker_ids is None:
            return set()
        if isinstance(marker_ids, dict):
            return set(marker_ids.values())
        return set(marker_ids)

    def _normalize_dictionary_id(self, dictionary_id):
        if dictionary_id is None:
            return ARUCO_DICTIONARIES["aruco_original"]
        if isinstance(dictionary_id, str):
            try:
                return ARUCO_DICTIONARIES[dictionary_id]
            except KeyError as exc:
                supported = ", ".join(sorted(ARUCO_DICTIONARIES))
                raise ValueError(f"Unsupported ArUco dictionary '{dictionary_id}'. Supported: {supported}") from exc
        return dictionary_id

    def detect(self, frame):
        gray = self._to_grayscale(frame)
        corners, ids, _ = self._detect_markers(gray)

        if ids is None:
            return []

        detections = []
        for index, marker_id in enumerate(ids.flatten()):
            marker_id = int(marker_id)
            if self.marker_ids and marker_id not in self.marker_ids:
                continue

            marker_corners = np.asarray(corners[index], dtype=np.float32).reshape(4, 2)
            center = marker_corners.mean(axis=0)
            rvec, tvec = self._estimate_pose(marker_corners)
            detections.append(
                ArucoDetection(
                    marker_id=marker_id,
                    corners=marker_corners,
                    center_px=(float(center[0]), float(center[1])),
                    marker_size_m=self.marker_size_m,
                    rvec=rvec,
                    tvec=tvec,
                )
            )

        return detections

    def detect_one(self, frame, marker_id):
        for detection in self.detect(frame):
            if detection.marker_id == marker_id:
                return detection
        return None

    def draw_detections(self, frame, detections, draw_axes=True):
        output = frame.copy()
        if detections:
            corners = [detection.corners.reshape(1, 4, 2) for detection in detections]
            ids = np.array(
                [[detection.marker_id] for detection in detections],
                dtype=np.int32,
            )
            cv2.aruco.drawDetectedMarkers(output, corners, ids)

        if draw_axes and self.calibration is not None:
            for detection in detections:
                if detection.has_pose:
                    cv2.drawFrameAxes(
                        output,
                        self.calibration.camera_matrix,
                        self.calibration.dist_coeffs,
                        np.asarray(detection.rvec, dtype=np.float64),
                        np.asarray(detection.tvec, dtype=np.float64),
                        self.marker_size_m * 0.5,
                    )
        return output

    def _create_detector_parameters(self):
        if hasattr(cv2.aruco, "DetectorParameters"):
            return cv2.aruco.DetectorParameters()
        return cv2.aruco.DetectorParameters_create()

    def _create_detector(self):
        if hasattr(cv2.aruco, "ArucoDetector"):
            return cv2.aruco.ArucoDetector(self.dictionary, self.parameters)
        return None

    def _detect_markers(self, gray):
        if self.detector is not None:
            return self.detector.detectMarkers(gray)
        return cv2.aruco.detectMarkers(
            gray,
            self.dictionary,
            parameters=self.parameters,
        )

    def _estimate_pose(self, marker_corners):
        if self.calibration is None:
            return None, None

        camera_matrix = self.calibration.camera_matrix
        dist_coeffs = self.calibration.dist_coeffs
        corners = marker_corners.reshape(1, 4, 2)

        if hasattr(cv2.aruco, "estimatePoseSingleMarkers"):
            rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                corners,
                self.marker_size_m,
                camera_matrix,
                dist_coeffs,
            )
            return _as_tuple(rvecs[0][0]), _as_tuple(tvecs[0][0])

        half_size = self.marker_size_m / 2.0
        object_points = np.array(
            [
                [-half_size, half_size, 0.0],
                [half_size, half_size, 0.0],
                [half_size, -half_size, 0.0],
                [-half_size, -half_size, 0.0],
            ],
            dtype=np.float32,
        )
        success, rvec, tvec = cv2.solvePnP(
            object_points,
            marker_corners,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE,
        )
        if not success:
            return None, None
        return _as_tuple(rvec.flatten()), _as_tuple(tvec.flatten())

    def _to_grayscale(self, frame):
        if frame.ndim == 2:
            return frame
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def _as_tuple(vector):
    return tuple(float(value) for value in vector)
