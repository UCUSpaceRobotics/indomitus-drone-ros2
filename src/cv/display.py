from dataclasses import dataclass

import cv2


@dataclass(frozen=True)
class VideoDisplayConfig:
    window_name: str = "Drone video"
    fullscreen: bool = True
    enabled: bool = True


class VideoDisplay:
    def __init__(self, config=None):
        self.config = config or VideoDisplayConfig()
        self._window_ready = False

    @property
    def enabled(self):
        return bool(self.config.enabled)

    def show(self, frame, wait_ms=1):
        if not self.enabled:
            return -1

        self._ensure_window()
        try:
            cv2.imshow(self.config.window_name, frame)
            return cv2.waitKey(wait_ms) & 0xFF
        except cv2.error as exc:
            raise RuntimeError(
                "OpenCV GUI output is unavailable. Install a GUI-enabled OpenCV build "
                "and run inside the Raspberry Pi display session that feeds composite output."
            ) from exc

    def close(self):
        if not self._window_ready:
            return

        try:
            cv2.destroyWindow(self.config.window_name)
        except cv2.error:
            pass
        finally:
            self._window_ready = False

    def _ensure_window(self):
        if self._window_ready:
            return

        try:
            cv2.namedWindow(self.config.window_name, cv2.WINDOW_NORMAL)
            if self.config.fullscreen:
                cv2.setWindowProperty(
                    self.config.window_name,
                    cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_FULLSCREEN,
                )
        except cv2.error as exc:
            raise RuntimeError(
                "OpenCV GUI output is unavailable. Install a GUI-enabled OpenCV build "
                "instead of a headless package."
            ) from exc

        self._window_ready = True