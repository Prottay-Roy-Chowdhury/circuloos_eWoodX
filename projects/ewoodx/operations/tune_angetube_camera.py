from pathlib import Path
import re
import sys

import cv2


PROJECT_ROOT = Path(
    __file__
).resolve().parents[3]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


try:
    import duvc_ctl as duvc

    HAS_DUVC = True

except ImportError:

    duvc = None
    HAS_DUVC = False


from projects.ewoodx.config import (
    EWOODX_PROJECT_ROOT,

    ANGETUBE_CAMERA_INDEX,
    ANGETUBE_IMAGE_WIDTH,
    ANGETUBE_IMAGE_HEIGHT,
    ANGETUBE_CAMERA_FPS,
    ANGETUBE_CAMERA_FOURCC,

    ANGETUBE_FOCUS_MODE,
    ANGETUBE_FOCUS_VALUE,

    ANGETUBE_EXPOSURE_MODE,
    ANGETUBE_EXPOSURE_VALUE,

    ANGETUBE_BRIGHTNESS,
    ANGETUBE_CONTRAST,
    ANGETUBE_SATURATION,
    ANGETUBE_SHARPNESS,
    ANGETUBE_GAIN,
    ANGETUBE_BACKLIGHT_COMPENSATION,

    ANGETUBE_WHITE_BALANCE_MODE,
    ANGETUBE_WHITE_BALANCE_TEMPERATURE,

    ANGETUBE_DIGITAL_ZOOM,
)


class EWoodXAngetubeCameraTuning:
    """
    Interactive eWoodX operation for tuning
    Angetube webcam parameters before camera
    calibration.

    The selected parameters can be printed
    or written directly into:

    projects/ewoodx/config/sensing.py
    """

    def __init__(
        self,
    ) -> None:

        self.config_file = (
            EWOODX_PROJECT_ROOT
            / "config"
            / "sensing.py"
        )

        self.camera_index = (
            ANGETUBE_CAMERA_INDEX
        )

        self.width = (
            ANGETUBE_IMAGE_WIDTH
        )

        self.height = (
            ANGETUBE_IMAGE_HEIGHT
        )

        self.fps = (
            ANGETUBE_CAMERA_FPS
        )

        self.fourcc = (
            ANGETUBE_CAMERA_FOURCC
        )

        self.focus_mode = (
            ANGETUBE_FOCUS_MODE
        )

        self.focus_value = int(
            ANGETUBE_FOCUS_VALUE
        )

        self.exposure_mode = (
            ANGETUBE_EXPOSURE_MODE
        )

        self.exposure_value = int(
            ANGETUBE_EXPOSURE_VALUE
        )

        self.brightness = int(
            ANGETUBE_BRIGHTNESS
        )

        self.contrast = int(
            ANGETUBE_CONTRAST
        )

        self.saturation = int(
            ANGETUBE_SATURATION
        )

        self.sharpness = int(
            ANGETUBE_SHARPNESS
        )

        self.gain = int(
            ANGETUBE_GAIN
        )

        self.backlight_compensation = int(
            ANGETUBE_BACKLIGHT_COMPENSATION
        )

        self.white_balance_mode = (
            ANGETUBE_WHITE_BALANCE_MODE
        )

        self.white_balance_temperature = int(
            ANGETUBE_WHITE_BALANCE_TEMPERATURE
        )

        self.digital_zoom = float(
            ANGETUBE_DIGITAL_ZOOM
        )

        self.controller = None
        self.capture = None

        self.focus_min = 0
        self.focus_max = 1023

        self.exposure_min = -13
        self.exposure_max = -1

        self.brightness_min = 1
        self.brightness_max = 64

        self.contrast_min = 1
        self.contrast_max = 64

    # -----------------------------------------------------------------
    # Main operation
    # -----------------------------------------------------------------

    def run(
        self,
    ) -> None:

        print()
        print(
            "eWoodX Angetube Camera Tuning"
        )

        print(
            "============================"
        )

        print()

        if not HAS_DUVC:

            print(
                "[eWoodX] duvc_ctl is not installed."
            )

            print(
                "[eWoodX] OpenCV camera controls "
                "will be used where available."
            )

        self._open()

        self._apply_current_settings()

        self._print_controls()

        window_name = (
            "eWoodX Angetube Camera Tuning"
        )

        cv2.namedWindow(
            window_name,
            cv2.WINDOW_NORMAL,
        )

        cv2.resizeWindow(
            window_name,
            1280,
            720,
        )

        try:

            while True:

                success, frame = (
                    self.capture.read()
                )

                if (
                    not success
                    or frame is None
                ):

                    raise RuntimeError(
                        "Could not read frame "
                        "from Angetube webcam."
                    )

                frame = (
                    self._apply_digital_zoom(
                        frame
                    )
                )

                display = (
                    self._build_preview(
                        frame
                    )
                )

                cv2.imshow(
                    window_name,
                    display,
                )

                key = (
                    cv2.waitKey(1)
                    & 0xFF
                )

                if key in (
                    ord("q"),
                    ord("Q"),
                    27,
                ):

                    break

                # -----------------------------------------------------
                # Focus presets
                # -----------------------------------------------------

                elif key == ord("1"):
                    self._set_focus(
                        300
                    )

                elif key == ord("2"):
                    self._set_focus(
                        350
                    )

                elif key == ord("3"):
                    self._set_focus(
                        400
                    )

                elif key == ord("4"):
                    self._set_focus(
                        450
                    )

                elif key == ord("5"):
                    self._set_focus(
                        500
                    )

                elif key == ord("6"):
                    self._set_focus(
                        600
                    )

                # -----------------------------------------------------
                # Focus step
                # -----------------------------------------------------

                elif key in (
                    ord("+"),
                    ord("="),
                ):

                    self._set_focus(
                        self.focus_value
                        + 10
                    )

                elif key in (
                    ord("-"),
                    ord("_"),
                ):

                    self._set_focus(
                        self.focus_value
                        - 10
                    )

                # -----------------------------------------------------
                # Focus mode
                # -----------------------------------------------------

                elif key in (
                    ord("a"),
                    ord("A"),
                ):

                    self._set_focus_mode(
                        "auto"
                    )

                elif key in (
                    ord("m"),
                    ord("M"),
                ):

                    self._set_focus_mode(
                        "manual"
                    )

                # -----------------------------------------------------
                # Digital zoom
                # -----------------------------------------------------

                elif key in (
                    ord("["),
                    ord("z"),
                ):

                    self.digital_zoom = max(
                        1.0,
                        round(
                            self.digital_zoom
                            - 0.1,
                            2,
                        ),
                    )

                    print(
                        "[eWoodX] Zoom -> "
                        f"{self.digital_zoom:.2f}x"
                    )

                elif key in (
                    ord("]"),
                    ord("Z"),
                ):

                    self.digital_zoom = min(
                        4.0,
                        round(
                            self.digital_zoom
                            + 0.1,
                            2,
                        ),
                    )

                    print(
                        "[eWoodX] Zoom -> "
                        f"{self.digital_zoom:.2f}x"
                    )

                elif key == ord("0"):

                    self.digital_zoom = 1.0

                    print(
                        "[eWoodX] Zoom -> 1.00x"
                    )

                elif key == ord("7"):

                    self.digital_zoom = 1.5

                    print(
                        "[eWoodX] Zoom -> 1.50x"
                    )

                elif key == ord("8"):

                    self.digital_zoom = 2.0

                    print(
                        "[eWoodX] Zoom -> 2.00x"
                    )

                elif key == ord("9"):

                    self.digital_zoom = 3.0

                    print(
                        "[eWoodX] Zoom -> 3.00x"
                    )

                # -----------------------------------------------------
                # Exposure
                # -----------------------------------------------------

                elif key in (
                    ord("e"),
                    ord("E"),
                ):

                    if (
                        self.exposure_mode
                        == "auto"
                    ):

                        self._set_exposure_mode(
                            "manual"
                        )

                    else:

                        self._set_exposure_mode(
                            "auto"
                        )

                elif key == ord("("):

                    self._set_exposure_value(
                        self.exposure_value
                        - 1
                    )

                elif key == ord(")"):

                    self._set_exposure_value(
                        self.exposure_value
                        + 1
                    )

                # -----------------------------------------------------
                # Brightness
                # -----------------------------------------------------

                elif key == ord("b"):

                    self._set_brightness(
                        self.brightness
                        - 1
                    )

                elif key == ord("B"):

                    self._set_brightness(
                        self.brightness
                        + 1
                    )

                # -----------------------------------------------------
                # Contrast
                # -----------------------------------------------------

                elif key == ord("c"):

                    self._set_contrast(
                        self.contrast
                        - 1
                    )

                elif key == ord("C"):

                    self._set_contrast(
                        self.contrast
                        + 1
                    )

                # -----------------------------------------------------
                # Configuration actions
                # -----------------------------------------------------

                elif key in (
                    ord("p"),
                    ord("P"),
                ):

                    self._print_config()

                elif key in (
                    ord("s"),
                    ord("S"),
                ):

                    self._save_config()

        finally:

            self._close()

            cv2.destroyAllWindows()

    # -----------------------------------------------------------------
    # Camera lifecycle
    # -----------------------------------------------------------------

    def _open(
        self,
    ) -> None:

        self._open_controller()

        self.capture = (
            cv2.VideoCapture(
                self.camera_index,
                cv2.CAP_DSHOW,
            )
        )

        if not self.capture.isOpened():

            self._close_controller()

            raise RuntimeError(
                "Could not open Angetube webcam "
                f"at index {self.camera_index}."
            )

        codec = (
            cv2.VideoWriter_fourcc(
                *self.fourcc
            )
        )

        self.capture.set(
            cv2.CAP_PROP_FOURCC,
            codec,
        )

        self.capture.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            self.width,
        )

        self.capture.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            self.height,
        )

        self.capture.set(
            cv2.CAP_PROP_FPS,
            self.fps,
        )

        print(
            "[eWoodX] Camera opened."
        )

        print(
            "[eWoodX] Requested resolution:"
        )

        print(
            f"{self.width} x {self.height}"
        )

        print(
            "[eWoodX] Actual resolution:"
        )

        print(
            (
                int(
                    self.capture.get(
                        cv2.CAP_PROP_FRAME_WIDTH
                    )
                ),
                int(
                    self.capture.get(
                        cv2.CAP_PROP_FRAME_HEIGHT
                    )
                ),
            )
        )

    def _close(
        self,
    ) -> None:

        if self.capture is not None:

            self.capture.release()

            self.capture = None

        self._close_controller()

    # -----------------------------------------------------------------
    # duvc_ctl
    # -----------------------------------------------------------------

    def _open_controller(
        self,
    ) -> None:

        if not HAS_DUVC:
            return

        try:

            self.controller = (
                duvc.CameraController(
                    device_index=(
                        self.camera_index
                    )
                )
            )

            self._read_property_ranges()

            print(
                "[eWoodX] duvc_ctl connected."
            )

        except Exception as error:

            print(
                "[eWoodX] duvc_ctl connection note:"
            )

            print(
                error
            )

            self.controller = None

    def _close_controller(
        self,
    ) -> None:

        if self.controller is None:
            return

        try:

            self.controller.close()

        except Exception:
            pass

        self.controller = None

    def _read_property_ranges(
        self,
    ) -> None:

        if self.controller is None:
            return

        ranges = {
            "focus": (
                "focus_min",
                "focus_max",
            ),
            "exposure": (
                "exposure_min",
                "exposure_max",
            ),
            "brightness": (
                "brightness_min",
                "brightness_max",
            ),
            "contrast": (
                "contrast_min",
                "contrast_max",
            ),
        }

        for property_name, (
            minimum_attribute,
            maximum_attribute,
        ) in ranges.items():

            try:

                value_range = (
                    self.controller
                    .get_property_range(
                        property_name
                    )
                )

                if not isinstance(
                    value_range,
                    dict,
                ):
                    continue

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

                if minimum is not None:

                    setattr(
                        self,
                        minimum_attribute,
                        minimum,
                    )

                if maximum is not None:

                    setattr(
                        self,
                        maximum_attribute,
                        maximum,
                    )

            except Exception:
                pass

    # -----------------------------------------------------------------
    # Initial settings
    # -----------------------------------------------------------------

    def _apply_current_settings(
        self,
    ) -> None:

        self._set_focus_mode(
            self.focus_mode,
            print_status=False,
        )

        if (
            self.focus_mode
            == "manual"
        ):

            self._set_focus(
                self.focus_value,
                print_status=False,
            )

        self._set_exposure_mode(
            self.exposure_mode,
            print_status=False,
        )

        if (
            self.exposure_mode
            == "manual"
        ):

            self._set_exposure_value(
                self.exposure_value,
                print_status=False,
            )

        self._set_brightness(
            self.brightness,
            print_status=False,
        )

        self._set_contrast(
            self.contrast,
            print_status=False,
        )

        self._apply_fixed_settings()


    def _apply_fixed_settings(
        self,
    ) -> None:
        """
        Apply the fixed Angetube image settings
        used by calibration and sensing.
        """

        if self.capture is not None:

            properties = [
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

            for property_id, value in properties:

                self.capture.set(
                    property_id,
                    float(value),
                )

            mode = (
                self.white_balance_mode
                .strip()
                .lower()
            )

            if mode == "auto":

                self.capture.set(
                    cv2.CAP_PROP_AUTO_WB,
                    1,
                )

            elif mode == "manual":

                self.capture.set(
                    cv2.CAP_PROP_AUTO_WB,
                    0,
                )

                self.capture.set(
                    cv2.CAP_PROP_WB_TEMPERATURE,
                    float(
                        self.white_balance_temperature
                    ),
                )

        if self.controller is not None:

            fixed_properties = {
                "saturation": (
                    self.saturation
                ),
                "sharpness": (
                    self.sharpness
                ),
                "gain": (
                    self.gain
                ),
                "backlight_compensation": (
                    self.backlight_compensation
                ),
            }

            for name, value in (
                fixed_properties.items()
            ):

                try:

                    if hasattr(
                        self.controller,
                        name,
                    ):

                        setattr(
                            self.controller,
                            name,
                            value,
                        )

                except Exception:
                    pass

            try:

                if (
                    self.white_balance_mode
                    == "auto"
                ):

                    if hasattr(
                        self.controller,
                        "white_balance_mode",
                    ):

                        self.controller.white_balance_mode = (
                            "auto"
                        )

                    elif hasattr(
                        self.controller,
                        "_set_property_auto",
                    ):

                        self.controller._set_property_auto(
                            "white_balance"
                        )

                else:

                    if hasattr(
                        self.controller,
                        "white_balance_mode",
                    ):

                        self.controller.white_balance_mode = (
                            "manual"
                        )

                    if hasattr(
                        self.controller,
                        "white_balance",
                    ):

                        self.controller.white_balance = (
                            self.white_balance_temperature
                        )

            except Exception:
                pass

    # -----------------------------------------------------------------
    # Focus
    # -----------------------------------------------------------------

    def _set_focus_mode(
        self,
        mode: str,
        print_status: bool = True,
    ) -> None:

        mode = (
            mode
            .strip()
            .lower()
        )

        if mode not in (
            "auto",
            "manual",
        ):
            return

        self.focus_mode = (
            mode
        )

        if self.capture is not None:

            self.capture.set(
                cv2.CAP_PROP_AUTOFOCUS,
                1
                if mode == "auto"
                else 0,
            )

        if self.controller is not None:

            try:

                self.controller.focus_mode = (
                    mode
                )

            except Exception:
                pass

        if (
            mode == "manual"
        ):

            self._set_focus(
                self.focus_value,
                print_status=False,
            )

        if print_status:

            print(
                "[eWoodX] Focus mode -> "
                f"{mode.upper()}"
            )

    def _set_focus(
        self,
        value: int,
        print_status: bool = True,
    ) -> None:

        value = int(
            max(
                self.focus_min,
                min(
                    self.focus_max,
                    value,
                ),
            )
        )

        self.focus_value = (
            value
        )

        self.focus_mode = (
            "manual"
        )

        if self.capture is not None:

            self.capture.set(
                cv2.CAP_PROP_AUTOFOCUS,
                0,
            )

            self.capture.set(
                cv2.CAP_PROP_FOCUS,
                float(value),
            )

        if self.controller is not None:

            try:

                self.controller.focus_mode = (
                    "manual"
                )

            except Exception:
                pass

            try:

                self.controller.focus = (
                    value
                )

            except Exception:
                pass

        if print_status:

            print(
                "[eWoodX] Focus -> "
                f"{value}"
            )

    # -----------------------------------------------------------------
    # Exposure
    # -----------------------------------------------------------------

    def _set_exposure_mode(
        self,
        mode: str,
        print_status: bool = True,
    ) -> None:

        mode = (
            mode
            .strip()
            .lower()
        )

        if mode not in (
            "auto",
            "manual",
        ):
            return

        self.exposure_mode = (
            mode
        )

        if self.capture is not None:

            self.capture.set(
                cv2.CAP_PROP_AUTO_EXPOSURE,
                0.75
                if mode == "auto"
                else 0.25,
            )

        if self.controller is not None:

            try:

                if hasattr(
                    self.controller,
                    "exposure_mode",
                ):

                    self.controller.exposure_mode = (
                        mode
                    )

                elif (
                    mode == "auto"
                    and hasattr(
                        self.controller,
                        "_set_property_auto",
                    )
                ):

                    self.controller._set_property_auto(
                        "exposure"
                    )

            except Exception:
                pass

        if (
            mode == "manual"
        ):

            self._set_exposure_value(
                self.exposure_value,
                print_status=False,
            )

        if print_status:

            print(
                "[eWoodX] Exposure mode -> "
                f"{mode.upper()}"
            )

    def _set_exposure_value(
        self,
        value: int,
        print_status: bool = True,
    ) -> None:

        value = int(
            max(
                self.exposure_min,
                min(
                    self.exposure_max,
                    value,
                ),
            )
        )

        self.exposure_value = (
            value
        )

        self.exposure_mode = (
            "manual"
        )

        if self.capture is not None:

            self.capture.set(
                cv2.CAP_PROP_AUTO_EXPOSURE,
                0.25,
            )

            self.capture.set(
                cv2.CAP_PROP_EXPOSURE,
                float(value),
            )

        if self.controller is not None:

            try:

                self.controller.exposure = (
                    value
                )

            except Exception:
                pass

        if print_status:

            print(
                "[eWoodX] Exposure -> "
                f"{value}"
            )

    # -----------------------------------------------------------------
    # Brightness / contrast
    # -----------------------------------------------------------------

    def _set_brightness(
        self,
        value: int,
        print_status: bool = True,
    ) -> None:

        value = int(
            max(
                self.brightness_min,
                min(
                    self.brightness_max,
                    value,
                ),
            )
        )

        self.brightness = (
            value
        )

        if self.capture is not None:

            self.capture.set(
                cv2.CAP_PROP_BRIGHTNESS,
                float(value),
            )

        if self.controller is not None:

            try:

                self.controller.brightness = (
                    value
                )

            except Exception:
                pass

        if print_status:

            print(
                "[eWoodX] Brightness -> "
                f"{value}"
            )

    def _set_contrast(
        self,
        value: int,
        print_status: bool = True,
    ) -> None:

        value = int(
            max(
                self.contrast_min,
                min(
                    self.contrast_max,
                    value,
                ),
            )
        )

        self.contrast = (
            value
        )

        if self.capture is not None:

            self.capture.set(
                cv2.CAP_PROP_CONTRAST,
                float(value),
            )

        if self.controller is not None:

            try:

                self.controller.contrast = (
                    value
                )

            except Exception:
                pass

        if print_status:

            print(
                "[eWoodX] Contrast -> "
                f"{value}"
            )

    # -----------------------------------------------------------------
    # Digital zoom
    # -----------------------------------------------------------------

    def _apply_digital_zoom(
        self,
        frame,
    ):

        if self.digital_zoom <= 1.0:
            return frame

        height, width = (
            frame.shape[:2]
        )

        crop_width = int(
            width
            / self.digital_zoom
        )

        crop_height = int(
            height
            / self.digital_zoom
        )

        x1 = (
            width - crop_width
        ) // 2

        y1 = (
            height - crop_height
        ) // 2

        cropped = (
            frame[
                y1:y1 + crop_height,
                x1:x1 + crop_width,
            ]
        )

        return cv2.resize(
            cropped,
            (
                width,
                height,
            ),
            interpolation=(
                cv2.INTER_LINEAR
            ),
        )

    # -----------------------------------------------------------------
    # Preview
    # -----------------------------------------------------------------

    def _build_preview(
        self,
        frame,
    ):

        preview = (
            frame.copy()
        )

        overlay = (
            preview.copy()
        )

        cv2.rectangle(
            overlay,
            (
                20,
                15,
            ),
            (
                1050,
                190,
            ),
            (
                0,
                0,
                0,
            ),
            -1,
        )

        cv2.addWeighted(
            overlay,
            0.65,
            preview,
            0.35,
            0,
            preview,
        )

        lines = [
            (
                "Focus: "
                f"{self.focus_value} "
                f"[{self.focus_min}-{self.focus_max}] "
                f"({self.focus_mode.upper()})"
            ),
            (
                "Zoom: "
                f"{self.digital_zoom:.2f}x "
                "[1.0-4.0]"
            ),
            (
                "Exposure: "
                f"{self.exposure_value} "
                f"[{self.exposure_min}-{self.exposure_max}] "
                f"({self.exposure_mode.upper()})"
            ),
            (
                "Brightness: "
                f"{self.brightness} "
                f"[{self.brightness_min}-{self.brightness_max}]"
            ),
            (
                "Contrast: "
                f"{self.contrast} "
                f"[{self.contrast_min}-{self.contrast_max}]"
            ),
            (
                "P = print config | "
                "S = save config | "
                "Q = quit"
            ),
        ]

        for index, line in enumerate(
            lines
        ):

            cv2.putText(
                preview,
                line,
                (
                    30,
                    45
                    + index * 26,
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.62,
                (
                    255,
                    255,
                    255,
                ),
                2,
            )

        return preview

    # -----------------------------------------------------------------
    # Config output
    # -----------------------------------------------------------------

    def _current_config(
        self,
    ) -> dict:

        return {
            "ANGETUBE_FOCUS_MODE": (
                self.focus_mode
            ),
            "ANGETUBE_FOCUS_VALUE": (
                self.focus_value
            ),
            "ANGETUBE_EXPOSURE_MODE": (
                self.exposure_mode
            ),
            "ANGETUBE_EXPOSURE_VALUE": (
                self.exposure_value
            ),
            "ANGETUBE_BRIGHTNESS": (
                self.brightness
            ),
            "ANGETUBE_CONTRAST": (
                self.contrast
            ),
            "ANGETUBE_DIGITAL_ZOOM": (
                self.digital_zoom
            ),
        }

    def _print_config(
        self,
    ) -> None:

        values = (
            self._current_config()
        )

        print()
        print(
            "=" * 60
        )

        print(
            "ANGETUBE CAMERA CONFIGURATION"
        )

        print(
            "=" * 60
        )

        for name, value in (
            values.items()
        ):

            print(
                self._format_config_assignment(
                    name,
                    value,
                ),
                end="",
            )

        print(
            "=" * 60
        )

        print()

    def _save_config(
        self,
    ) -> None:

        if not self.config_file.exists():

            raise FileNotFoundError(
                "eWoodX sensing config file "
                "not found: "
                f"{self.config_file}"
            )

        text = (
            self.config_file
            .read_text(
                encoding="utf-8"
            )
        )

        for name, value in (
            self._current_config()
            .items()
        ):

            replacement = (
                self._format_config_assignment(
                    name,
                    value,
                )
                .rstrip(
                    "\n"
                )
            )

            pattern = (
                rf"(?ms)^"
                rf"{re.escape(name)}"
                rf"\s*=\s*\("
                rf".*?"
                rf"^\)"
            )

            updated_text, count = (
                re.subn(
                    pattern,
                    replacement,
                    text,
                    count=1,
                )
            )

            if count != 1:

                raise RuntimeError(
                    "Could not uniquely update "
                    f"{name} in "
                    f"{self.config_file}"
                )

            text = (
                updated_text
            )

        self.config_file.write_text(
            text,
            encoding="utf-8",
        )

        print()
        print(
            "[eWoodX] Camera parameters saved:"
        )

        print(
            self.config_file
        )

        self._print_config()

    @staticmethod
    def _format_config_assignment(
        name: str,
        value,
    ) -> str:

        if isinstance(
            value,
            str,
        ):

            value_text = (
                f"\"{value}\""
            )

        elif isinstance(
            value,
            float,
        ):

            value_text = (
                f"{value:.2f}"
            )

        else:

            value_text = (
                str(value)
            )

        return (
            f"{name} = (\n"
            f"    {value_text}\n"
            f")\n"
        )

    # -----------------------------------------------------------------
    # Help
    # -----------------------------------------------------------------

    @staticmethod
    def _print_controls(
    ) -> None:

        print()
        print(
            "Controls:"
        )

        print(
            "  1-6      Focus presets "
            "(300, 350, 400, 450, 500, 600)"
        )

        print(
            "  +/-      Focus +/- 10"
        )

        print(
            "  A        Auto focus"
        )

        print(
            "  M        Manual focus"
        )

        print(
            "  [ / ]    Zoom -/+ 0.1"
        )

        print(
            "  z / Z    Zoom -/+ 0.1"
        )

        print(
            "  0        Zoom 1.0x"
        )

        print(
            "  7/8/9    Zoom 1.5x / 2.0x / 3.0x"
        )

        print(
            "  E        Toggle exposure auto/manual"
        )

        print(
            "  ( / )    Exposure -/+ 1"
        )

        print(
            "  b / B    Brightness -/+ 1"
        )

        print(
            "  c / C    Contrast -/+ 1"
        )

        print(
            "  P        Print current config"
        )

        print(
            "  S        Save current values to sensing.py"
        )

        print(
            "  Q / ESC  Quit"
        )

        print()


def main() -> None:

    operation = (
        EWoodXAngetubeCameraTuning()
    )

    operation.run()


if __name__ == "__main__":
    main()