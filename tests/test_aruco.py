import unittest

import cv2
import numpy as np

from src.cv.aruco import ArucoDetector, MISSION_MARKER_IDS
from src.cv.camera import CameraCalibration


class ArucoDetectorTest(unittest.TestCase):
    def test_detects_mission_marker_with_pose(self):
        frame = self._marker_frame(MISSION_MARKER_IDS["origin"])
        calibration = CameraCalibration(
            camera_matrix=np.array(
                [[500.0, 0.0, 160.0], [0.0, 500.0, 160.0], [0.0, 0.0, 1.0]]
            ),
            dist_coeffs=np.zeros((5, 1)),
        )

        detections = ArucoDetector(calibration=calibration).detect(frame)

        self.assertEqual(1, len(detections))
        self.assertEqual(MISSION_MARKER_IDS["origin"], detections[0].marker_id)
        self.assertTrue(detections[0].has_pose)

    def test_ignores_non_mission_marker_by_default(self):
        frame = self._marker_frame(42)

        detections = ArucoDetector().detect(frame)

        self.assertEqual([], detections)

    def test_detects_apriltag_36h11_marker(self):
        frame = self._marker_frame(13, cv2.aruco.DICT_APRILTAG_36h11)

        detections = ArucoDetector(
            marker_ids=[13],
            dictionary_id="apriltag_36h11",
        ).detect(frame)

        self.assertEqual(1, len(detections))
        self.assertEqual(13, detections[0].marker_id)

    def _marker_frame(self, marker_id, dictionary_id=cv2.aruco.DICT_ARUCO_ORIGINAL):
        aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_id)
        marker = cv2.aruco.generateImageMarker(aruco_dict, marker_id, 160)
        frame = np.full((320, 320), 255, dtype=np.uint8)
        frame[80:240, 80:240] = marker
        return frame


if __name__ == "__main__":
    unittest.main()
