"""
Arducam camera acquisition.
"""

from typing import Optional

import cv2
import numpy as np


class ArducamCamera:
    """
    OpenCV-based interface for an Arducam camera.

    Responsible only for:
    - opening/closing the camera
    - configuring acquisition resolution
    - capturing frames
    """

    def __init__(
        self,
        camera_index: int,
        width: Optional[int] = None,
        height: Optional[int] = None,
        backend: Optional[int] = cv2.CAP_DSHOW,
    ):
        if not isinstance(camera_index, int):
            raise TypeError(
                "camera_index must be an integer."
            )

        if width is not None and width <= 0:
            raise ValueError(
                "width must be greater than zero."
            )

        if height is not None and height <= 0:
            raise ValueError(
                "height must be greater than zero."
            )

        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.backend = backend

        self._capture: Optional[
            cv2.VideoCapture
        ] = None

    @property
    def is_open(self) -> bool:
        return (
            self._capture is not None
            and self._capture.isOpened()
        )

    @property
    def resolution(self) -> tuple[int, int]:
        """
        Return the actual current camera resolution
        as (width, height).
        """

        if not self.is_open:
            raise RuntimeError(
                "Camera is not open."
            )

        width = int(
            self._capture.get(
                cv2.CAP_PROP_FRAME_WIDTH
            )
        )

        height = int(
            self._capture.get(
                cv2.CAP_PROP_FRAME_HEIGHT
            )
        )

        return width, height

    def open(self) -> None:
        if self.is_open:
            return

        if self.backend is None:
            capture = cv2.VideoCapture(
                self.camera_index
            )
        else:
            capture = cv2.VideoCapture(
                self.camera_index,
                self.backend,
            )

        if not capture.isOpened():
            capture.release()

            raise RuntimeError(
                "Could not open Arducam camera "
                f"at index {self.camera_index}."
            )

        if self.width is not None:
            capture.set(
                cv2.CAP_PROP_FRAME_WIDTH,
                self.width,
            )

        if self.height is not None:
            capture.set(
                cv2.CAP_PROP_FRAME_HEIGHT,
                self.height,
            )

        self._capture = capture

    def capture(self) -> np.ndarray:
        if not self.is_open:
            raise RuntimeError(
                "Camera is not open."
            )

        success, frame = self._capture.read()

        if not success or frame is None:
            raise RuntimeError(
                "Failed to capture frame "
                "from Arducam camera."
            )

        return frame

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None