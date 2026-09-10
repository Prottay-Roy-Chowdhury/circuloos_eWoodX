"""
Angetube webcam acquisition and hardware control.
"""

from typing import Optional

import cv2
import numpy as np


try:
    import duvc_ctl as duvc

    HAS_DUVC = True

except ImportError:

    duvc = None
    HAS_DUVC = False


class AngetubeCamera:
    """
    OpenCV-based interface for the Angetube webcam.

    Responsible for:

    - opening / closing the camera
    - configuring stream resolution
    - configuring FPS and FOURCC
    - applying supported camera properties
    - optional duvc_ctl hardware control
    - applying digital center zoom
    - capturing frames
    """

    def __init__(
        self,
        camera_index: int,
        width: Optional[int] = None,
        height: Optional[int] = None,
        fps: Optional[int] = None,
        fourcc: Optional[str] = "MJPG",
        backend: Optional[int] = cv2.CAP_DSHOW,
        focus_mode: Optional[str] = None,
        focus_value: Optional[int] = None,
        exposure_mode: Optional[str] = None,
        exposure_value: Optional[int] = None,
        brightness: Optional[int] = None,
        contrast: Optional[int] = None,
        saturation: Optional[int] = None,
        sharpness: Optional[int] = None,
        gain: Optional[int] = None,
        backlight_compensation: Optional[int] = None,
        white_balance_mode: Optional[str] = None,
        white_balance_temperature: Optional[int] = None,
        digital_zoom: float = 1.0,
        warmup_frames: int = 5,
    ) -> None:

        if not isinstance(
            camera_index,
            int,
        ):
            raise TypeError(
                "camera_index must be an integer."
            )

        if (
            width is not None
            and width <= 0
        ):
            raise ValueError(
                "width must be greater than zero."
            )

        if (
            height is not None
            and height <= 0
        ):
            raise ValueError(
                "height must be greater than zero."
            )

        if (
            fps is not None
            and fps <= 0
        ):
            raise ValueError(
                "fps must be greater than zero."
            )

        if (
            fourcc is not None
            and len(fourcc) != 4
        ):
            raise ValueError(
                "fourcc must contain exactly 4 characters."
            )

        if digital_zoom < 1.0:
            raise ValueError(
                "digital_zoom must be >= 1.0."
            )

        if warmup_frames < 0:
            raise ValueError(
                "warmup_frames cannot be negative."
            )

        self.camera_index = (
            camera_index
        )

        self.width = (
            width
        )

        self.height = (
            height
        )

        self.fps = (
            fps
        )

        self.fourcc = (
            fourcc
        )

        self.backend = (
            backend
        )

        self.focus_mode = (
            focus_mode
        )

        self.focus_value = (
            focus_value
        )

        self.exposure_mode = (
            exposure_mode
        )

        self.exposure_value = (
            exposure_value
        )

        self.brightness = (
            brightness
        )

        self.contrast = (
            contrast
        )

        self.saturation = (
            saturation
        )

        self.sharpness = (
            sharpness
        )

        self.gain = (
            gain
        )

        self.backlight_compensation = (
            backlight_compensation
        )

        self.white_balance_mode = (
            white_balance_mode
        )

        self.white_balance_temperature = (
            white_balance_temperature
        )

        self.digital_zoom = float(
            digital_zoom
        )

        self.warmup_frames = int(
            warmup_frames
        )

        self._capture: Optional[
            cv2.VideoCapture
        ] = None

        self._controller = None

    # -----------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------

    @property
    def is_open(
        self,
    ) -> bool:

        return (
            self._capture is not None
            and self._capture.isOpened()
        )

    @property
    def resolution(
        self,
    ) -> tuple[int, int]:
        """
        Return current actual stream resolution
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

        return (
            width,
            height,
        )

    # -----------------------------------------------------------------
    # Open / close
    # -----------------------------------------------------------------

    def open(
        self,
    ) -> None:

        if self.is_open:
            return

        self._open_controller()

        if self.backend is None:

            capture = (
                cv2.VideoCapture(
                    self.camera_index
                )
            )

        else:

            capture = (
                cv2.VideoCapture(
                    self.camera_index,
                    self.backend,
                )
            )

        if not capture.isOpened():

            capture.release()

            self._close_controller()

            raise RuntimeError(
                "Could not open Angetube webcam "
                f"at index {self.camera_index}."
            )

        self._capture = (
            capture
        )

        self._configure_stream()

        self._apply_opencv_properties()

        self._warm_up()

    def close(
        self,
    ) -> None:

        if self._capture is not None:

            self._capture.release()

            self._capture = None

        self._close_controller()

    # -----------------------------------------------------------------
    # Capture
    # -----------------------------------------------------------------

    def capture(
        self,
    ) -> np.ndarray:

        if not self.is_open:

            raise RuntimeError(
                "Camera is not open."
            )

        success, frame = (
            self._capture.read()
        )

        if (
            not success
            or frame is None
        ):

            raise RuntimeError(
                "Failed to capture frame "
                "from Angetube webcam."
            )

        frame = (
            self._apply_digital_zoom(
                frame
            )
        )

        return frame

    # -----------------------------------------------------------------
    # Stream configuration
    # -----------------------------------------------------------------

    def _configure_stream(
        self,
    ) -> None:

        if not self.is_open:
            return

        if self.fourcc is not None:

            codec = (
                cv2.VideoWriter_fourcc(
                    *self.fourcc
                )
            )

            self._capture.set(
                cv2.CAP_PROP_FOURCC,
                codec,
            )

        if self.width is not None:

            self._capture.set(
                cv2.CAP_PROP_FRAME_WIDTH,
                self.width,
            )

        if self.height is not None:

            self._capture.set(
                cv2.CAP_PROP_FRAME_HEIGHT,
                self.height,
            )

        if self.fps is not None:

            self._capture.set(
                cv2.CAP_PROP_FPS,
                self.fps,
            )

    # -----------------------------------------------------------------
    # OpenCV camera properties
    # -----------------------------------------------------------------

    def _apply_opencv_properties(
        self,
    ) -> None:

        if not self.is_open:
            return

        if self.focus_mode is not None:

            focus_mode = (
                self.focus_mode
                .strip()
                .lower()
            )

            if focus_mode == "auto":

                self._capture.set(
                    cv2.CAP_PROP_AUTOFOCUS,
                    1,
                )

            elif focus_mode == "manual":

                self._capture.set(
                    cv2.CAP_PROP_AUTOFOCUS,
                    0,
                )

                if self.focus_value is not None:

                    self._capture.set(
                        cv2.CAP_PROP_FOCUS,
                        float(
                            self.focus_value
                        ),
                    )

        if self.exposure_mode is not None:

            exposure_mode = (
                self.exposure_mode
                .strip()
                .lower()
            )

            if exposure_mode == "auto":

                self._capture.set(
                    cv2.CAP_PROP_AUTO_EXPOSURE,
                    0.75,
                )

            elif exposure_mode == "manual":

                self._capture.set(
                    cv2.CAP_PROP_AUTO_EXPOSURE,
                    0.25,
                )

                if (
                    self.exposure_value
                    is not None
                ):

                    self._capture.set(
                        cv2.CAP_PROP_EXPOSURE,
                        float(
                            self.exposure_value
                        ),
                    )

        properties = [
            (
                cv2.CAP_PROP_BRIGHTNESS,
                self.brightness,
            ),
            (
                cv2.CAP_PROP_CONTRAST,
                self.contrast,
            ),
            (
                cv2.CAP_PROP_SATURATION,
                self.saturation,
            ),
            (
                cv2.CAP_PROP_SHARPNESS,
                self.sharpness,
            ),
            (
                cv2.CAP_PROP_GAIN,
                self.gain,
            ),
            (
                cv2.CAP_PROP_BACKLIGHT,
                self.backlight_compensation,
            ),
        ]

        for property_id, value in (
            properties
        ):

            if value is None:
                continue

            self._capture.set(
                property_id,
                float(
                    value
                ),
            )

        if (
            self.white_balance_mode
            is not None
        ):

            mode = (
                self.white_balance_mode
                .strip()
                .lower()
            )

            if mode == "auto":

                self._capture.set(
                    cv2.CAP_PROP_AUTO_WB,
                    1,
                )

            elif mode == "manual":

                self._capture.set(
                    cv2.CAP_PROP_AUTO_WB,
                    0,
                )

                if (
                    self.white_balance_temperature
                    is not None
                ):

                    self._capture.set(
                        cv2.CAP_PROP_WB_TEMPERATURE,
                        float(
                            self.white_balance_temperature
                        ),
                    )

    # -----------------------------------------------------------------
    # duvc_ctl
    # -----------------------------------------------------------------

    def _open_controller(
        self,
    ) -> None:

        if not HAS_DUVC:
            return

        try:

            self._controller = (
                duvc.CameraController(
                    device_index=(
                        self.camera_index
                    )
                )
            )

            self._apply_duvc_properties()

        except Exception as error:

            print(
                "[AngetubeCamera] "
                "duvc_ctl unavailable for "
                f"this device: {error}"
            )

            self._controller = None

    def _close_controller(
        self,
    ) -> None:

        if self._controller is None:
            return

        try:

            self._controller.close()

        except Exception:
            pass

        self._controller = None

    def _apply_duvc_properties(
        self,
    ) -> None:

        if self._controller is None:
            return

        if self.focus_mode is not None:

            try:

                self._controller.focus_mode = (
                    self.focus_mode
                )

            except Exception:
                pass

        if (
            self.focus_mode == "manual"
            and self.focus_value is not None
        ):

            self._set_duvc_property(
                "focus",
                self.focus_value,
            )

        if self.exposure_mode is not None:

            try:

                if hasattr(
                    self._controller,
                    "exposure_mode",
                ):

                    self._controller.exposure_mode = (
                        self.exposure_mode
                    )

                elif (
                    self.exposure_mode == "auto"
                    and hasattr(
                        self._controller,
                        "_set_property_auto",
                    )
                ):

                    self._controller._set_property_auto(
                        "exposure"
                    )

            except Exception:
                pass

        if (
            self.exposure_mode == "manual"
            and self.exposure_value is not None
        ):

            self._set_duvc_property(
                "exposure",
                self.exposure_value,
            )

        properties = [
            (
                "brightness",
                self.brightness,
            ),
            (
                "contrast",
                self.contrast,
            ),
            (
                "saturation",
                self.saturation,
            ),
            (
                "sharpness",
                self.sharpness,
            ),
            (
                "gain",
                self.gain,
            ),
            (
                "backlight_compensation",
                self.backlight_compensation,
            ),
        ]

        for property_name, value in (
            properties
        ):

            if value is None:
                continue

            self._set_duvc_property(
                property_name,
                value,
            )

        if (
            self.white_balance_mode
            is not None
        ):

            try:

                if hasattr(
                    self._controller,
                    "white_balance_mode",
                ):

                    self._controller.white_balance_mode = (
                        self.white_balance_mode
                    )

                elif (
                    self.white_balance_mode == "auto"
                    and hasattr(
                        self._controller,
                        "_set_property_auto",
                    )
                ):

                    self._controller._set_property_auto(
                        "white_balance"
                    )

            except Exception:
                pass

        if (
            self.white_balance_mode == "manual"
            and self.white_balance_temperature
            is not None
        ):

            self._set_duvc_property(
                "white_balance",
                self.white_balance_temperature,
            )

    def _set_duvc_property(
        self,
        property_name: str,
        value,
    ) -> None:

        if self._controller is None:
            return

        if not hasattr(
            self._controller,
            property_name,
        ):
            return

        try:

            clamped_value = (
                self._clamp_duvc_property(
                    property_name,
                    value,
                )
            )

            setattr(
                self._controller,
                property_name,
                clamped_value,
            )

        except Exception:
            pass

    def _clamp_duvc_property(
        self,
        property_name: str,
        value,
    ):

        if self._controller is None:
            return value

        try:

            value_range = (
                self._controller
                .get_property_range(
                    property_name
                )
            )

            if isinstance(
                value_range,
                dict,
            ):

                minimum = (
                    value_range.get(
                        "min"
                    )
                )

                maximum = (
                    value_range.get(
                        "max"
                    )
                )

                if (
                    minimum is not None
                    and value < minimum
                ):

                    return minimum

                if (
                    maximum is not None
                    and value > maximum
                ):

                    return maximum

        except Exception:
            pass

        return value

    # -----------------------------------------------------------------
    # Digital zoom
    # -----------------------------------------------------------------

    def _apply_digital_zoom(
        self,
        frame: np.ndarray,
    ) -> np.ndarray:

        if self.digital_zoom <= 1.001:

            return frame

        height, width = (
            frame.shape[:2]
        )

        crop_width = max(
            10,
            int(
                width
                / self.digital_zoom
            ),
        )

        crop_height = max(
            10,
            int(
                height
                / self.digital_zoom
            ),
        )

        x_start = (
            width
            - crop_width
        ) // 2

        y_start = (
            height
            - crop_height
        ) // 2

        x_end = (
            x_start
            + crop_width
        )

        y_end = (
            y_start
            + crop_height
        )

        cropped = frame[
            y_start:y_end,
            x_start:x_end,
        ]

        return (
            cv2.resize(
                cropped,
                (
                    width,
                    height,
                ),
                interpolation=(
                    cv2.INTER_LINEAR
                ),
            )
        )

    # -----------------------------------------------------------------
    # Warm-up
    # -----------------------------------------------------------------

    def _warm_up(
        self,
    ) -> None:

        if not self.is_open:
            return

        for _ in range(
            self.warmup_frames
        ):

            self._capture.read()