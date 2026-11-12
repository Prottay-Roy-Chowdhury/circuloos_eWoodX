"""
eWoodX - Projector Renderer

Independent OpenCV renderer for the eWoodX projection system.

Extracted from the existing projector_live_viewer.py.

Rendering order:
    1. Timber contour
    2. Timber corners
    3. Defects
    4. Milling geometry
    5. Cutting geometry
    6. Drilling / reference points
    7. Labels
    8. Status HUD

All geometry is expressed in world coordinates (millimeters).
ProjectorGeometry handles the calibrated world-to-projector
transformation, including thickness/parallax compensation.

This module does not:
    - Read runtime JSON files
    - Open TCP connections
    - Select between sensing and Grasshopper
    - Load calibration files
    - Process keyboard commands
"""

from __future__ import annotations

import cv2
import numpy as np

from projects.ewoodx.config import (
    PROJECTOR_WIDTH,
    PROJECTOR_HEIGHT,
    PROJECTOR_SCREEN_ORIGIN_X,
    PROJECTOR_SCREEN_ORIGIN_Y,
)

from projects.ewoodx.operations.projection.projector_geometry import (
    ProjectorGeometry,
)


class ProjectorRenderer:

    WINDOW_NAME = "eWoodX Projector Live Viewer"

    DEFAULT_TIMBER_THICKNESS_PX = 2
    DEFAULT_CUT_THICKNESS_PX = 3
    DEFAULT_MILL_THICKNESS_PX = 2
    DEFAULT_DRILL_RADIUS_PX = 6
    DEFAULT_DRILL_THICKNESS_PX = 2
    DEFAULT_LABEL_SCALE = 0.45
    DEFAULT_LABEL_THICKNESS = 1

    DARK_BG = (15, 15, 15)

    def __init__(
        self,
        geometry: ProjectorGeometry,
    ) -> None:

        self.geometry = geometry

        self.offset_x_mm = 0.0
        self.offset_y_mm = 0.0

        self.step_mm = 0.5

        self.show_hud = True
        self.show_grid = False

        self.window_created = False

    # -------------------------------------------------------------
    # Geometry helpers
    # -------------------------------------------------------------

    def _world_to_projector(
        self,
        points_mm,
        thickness_mm,
    ) -> np.ndarray:

        return self.geometry.world_to_projector(
            points_mm,
            off_x=self.offset_x_mm,
            off_y=self.offset_y_mm,
            thickness_mm=thickness_mm,
        )

    def _parse_color(
        self,
        color,
        default_bgr=(255, 255, 255),
    ):

        return self.geometry.parse_color(
            color,
            default_bgr=default_bgr,
        )

    @staticmethod
    def _pixel_points(points) -> np.ndarray:
        return (
            np.round(points)
            .astype(np.int32)
            .reshape(-1, 1, 2)
        )

    
    @staticmethod
    def _normalize_contours(raw_data) -> list:
        """
        Normalize single or multiple timber contours.

        Single:
            [[x, y], [x, y], ...]

        Multiple:
            [
                [[x, y], [x, y], ...],
                [[x, y], [x, y], ...]
            ]

        Returns a list of valid Nx2 contours.
        """

        if raw_data is None:
            return []

        try:
            points = np.asarray(
                raw_data,
                dtype=np.float32,
            )

            # Single contour: Nx2
            if points.ndim == 2 and points.shape[1] == 2:
                candidates = [points]

            # Multiple contours: MxNx2
            elif points.ndim == 3 and points.shape[2] == 2:
                candidates = list(points)

            else:
                # Support contours with different
                # numbers of points.
                candidates = []

                for contour in raw_data:
                    try:
                        arr = np.asarray(
                            contour,
                            dtype=np.float32,
                        )

                        if arr.ndim == 2 and arr.shape[1] == 2:
                            candidates.append(arr)

                    except (TypeError, ValueError):
                        continue

            return [
                contour
                for contour in candidates
                if (
                    len(contour) >= 3
                    and np.isfinite(contour).all()
                )
            ]

        except (TypeError, ValueError):
            # Ragged multi-contour collections are
            # expected when contours differ in size.
            candidates = []

            for contour in raw_data:
                try:
                    arr = np.asarray(
                        contour,
                        dtype=np.float32,
                    )

                    if (
                        arr.ndim == 2
                        and arr.shape[1] == 2
                        and len(arr) >= 3
                        and np.isfinite(arr).all()
                    ):
                        candidates.append(arr)

                except (TypeError, ValueError):
                    continue

            return candidates

    # -------------------------------------------------------------
    # Main rendering
    # -------------------------------------------------------------

    def render(
        self,
        data: dict,
        is_connected: bool = False,
        packet_count: int = 0,
        thickness_mm: float = 0.0,
    ) -> np.ndarray:

        if not isinstance(data, dict):
            raise TypeError(
                "Projection data must be a dictionary."
            )

        canvas = np.zeros(
            (
                PROJECTOR_HEIGHT,
                PROJECTOR_WIDTH,
                3,
            ),
            dtype=np.uint8,
        )

        timber_thickness_px = int(
            data.get(
                "timber_thickness_px",
                data.get(
                    "timber_width",
                    self.DEFAULT_TIMBER_THICKNESS_PX,
                ),
            )
        )

        cut_thickness_px = int(
            data.get(
                "cut_thickness_px",
                data.get(
                    "cut_thickness",
                    data.get(
                        "cut_width",
                        self.DEFAULT_CUT_THICKNESS_PX,
                    ),
                ),
            )
        )

        mill_thickness_px = int(
            data.get(
                "mill_thickness_px",
                data.get(
                    "mill_thickness",
                    data.get(
                        "mill_width",
                        self.DEFAULT_MILL_THICKNESS_PX,
                    ),
                ),
            )
        )

        drill_radius_px = int(
            data.get(
                "drill_radius_px",
                data.get(
                    "point_radius",
                    data.get(
                        "point_size",
                        self.DEFAULT_DRILL_RADIUS_PX,
                    ),
                ),
            )
        )

        drill_thickness_px = int(
            data.get(
                "drill_thickness_px",
                data.get(
                    "point_thickness",
                    self.DEFAULT_DRILL_THICKNESS_PX,
                ),
            )
        )

        label_scale = float(
            data.get(
                "label_scale",
                data.get(
                    "text_size",
                    self.DEFAULT_LABEL_SCALE,
                ),
            )
        )

        label_thickness_px = int(
            data.get(
                "label_thickness",
                self.DEFAULT_LABEL_THICKNESS,
            )
        )


        # ---------------------------------------------------------
        # Timber contour
        # ---------------------------------------------------------

        contour_raw = (
            data.get("contour_mm")
            or data.get("timber_contour")
            or data.get("main_border")
        )

        timber_bgr = self._parse_color(
            data.get(
                "timber_color",
                (255, 255, 255),
            ),
            default_bgr=(255, 255, 255),
        )

        # Support both single and multiple timber contours.
        contours = self._normalize_contours(
            contour_raw
        )

        for contour in contours:

            points_px = self._world_to_projector(
                contour,
                thickness_mm,
            )

            if (
                len(points_px) < 3
                or not np.isfinite(points_px).all()
            ):
                continue

            points_int = self._pixel_points(
                points_px
            )

            cv2.polylines(
                canvas,
                [points_int],
                True,
                timber_bgr,
                max(1, timber_thickness_px),
                cv2.LINE_AA,
            )

        
        # ---------------------------------------------------------
        # Timber holes
        # ---------------------------------------------------------

        hole_contours = self._normalize_contours(
            data.get("holes_mm", [])
        )

        for hole in hole_contours:
            points_px = self._world_to_projector(
                hole,
                thickness_mm,
            )

            if (
                len(points_px) < 3
                or not np.isfinite(points_px).all()
            ):
                continue

            cv2.polylines(
                canvas,
                [self._pixel_points(points_px)],
                True,
                timber_bgr,
                max(1, timber_thickness_px),
                cv2.LINE_AA,
            )

        # ---------------------------------------------------------
        # Timber corners
        # ---------------------------------------------------------

        corners_raw = (
            data.get("corners_mm")
            or data.get("timber_corners")
        )

        corner_groups = self._normalize_contours(
            corners_raw
        )

        for group_index, corner_group in enumerate(
            corner_groups
        ):
            corners_px = self._world_to_projector(
                corner_group,
                thickness_mm,
            )

            for index, point in enumerate(corners_px):
                px = int(round(point[0]))
                py = int(round(point[1]))

                cv2.circle(
                    canvas,
                    (px, py),
                    4,
                    timber_bgr,
                    -1,
                    cv2.LINE_AA,
                )

                label = (
                    f"C{index + 1}"
                    if len(corner_groups) == 1
                    else f"T{group_index + 1}C{index + 1}"
                )

                cv2.putText(
                    canvas,
                    label,
                    (px + 6, py - 6),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.35,
                    timber_bgr,
                    1,
                    cv2.LINE_AA,
                )

        # ---------------------------------------------------------
        # Defects
        # ---------------------------------------------------------

        defects_raw = data.get(
            "defects",
            [],
        )

        for defect in defects_raw:

            defect_x = defect.get(
                "x_mm",
                defect.get("x", 0),
            )

            defect_y = defect.get(
                "y_mm",
                defect.get("y", 0),
            )

            defect_px = self._world_to_projector(
                [[defect_x, defect_y]],
                thickness_mm,
            )[0]

            px = int(round(defect_px[0]))
            py = int(round(defect_px[1]))

            cv2.drawMarker(
                canvas,
                (px, py),
                (0, 165, 255),
                cv2.MARKER_TILTED_CROSS,
                14,
                2,
                cv2.LINE_AA,
            )

        # ---------------------------------------------------------
        # Milling geometry
        # ---------------------------------------------------------

        mill_geo = (
            data.get("mill_geo")
            or data.get("mill")
            or data.get("milling", [])
        )

        mill_bgr = self._parse_color(
            data.get(
                "mill_color",
                (0, 220, 255),
            ),
            default_bgr=(255, 220, 0),
        )

        if isinstance(mill_geo, list):

            for polyline in mill_geo:

                if polyline and len(polyline) >= 2:

                    points_px = self._world_to_projector(
                        polyline,
                        thickness_mm,
                    )

                    points_int = self._pixel_points(
                        points_px
                    )

                    cv2.polylines(
                        canvas,
                        [points_int],
                        False,
                        mill_bgr,
                        max(1, mill_thickness_px),
                        cv2.LINE_AA,
                    )

        # ---------------------------------------------------------
        # Cutting geometry
        # ---------------------------------------------------------

        cut_geo = (
            data.get("cut_geo")
            or data.get("cut")
            or data.get("cutting", [])
        )

        cut_bgr = self._parse_color(
            data.get(
                "cut_color",
                (255, 30, 30),
            ),
            default_bgr=(30, 30, 255),
        )

        if isinstance(cut_geo, list):

            for polyline in cut_geo:

                if polyline and len(polyline) >= 2:

                    points_px = self._world_to_projector(
                        polyline,
                        thickness_mm,
                    )

                    points_int = self._pixel_points(
                        points_px
                    )

                    cv2.polylines(
                        canvas,
                        [points_int],
                        False,
                        cut_bgr,
                        max(1, cut_thickness_px),
                        cv2.LINE_AA,
                    )

        # ---------------------------------------------------------
        # Drill / reference points
        # ---------------------------------------------------------

        points_geo = (
            data.get("points_geo")
            or data.get("points", [])
        )

        point_bgr = self._parse_color(
            data.get(
                "point_color",
                (0, 255, 100),
            ),
            default_bgr=(100, 255, 0),
        )

        if isinstance(points_geo, list):

            for point in points_geo:

                if point and len(point) >= 2:

                    point_px = self._world_to_projector(
                        [point[:2]],
                        thickness_mm,
                    )[0]

                    px = int(round(point_px[0]))
                    py = int(round(point_px[1]))

                    cv2.circle(
                        canvas,
                        (px, py),
                        max(1, drill_radius_px),
                        point_bgr,
                        max(1, drill_thickness_px),
                        cv2.LINE_AA,
                    )

                    cv2.drawMarker(
                        canvas,
                        (px, py),
                        point_bgr,
                        cv2.MARKER_CROSS,
                        max(
                            4,
                            drill_radius_px * 2,
                        ),
                        1,
                        cv2.LINE_AA,
                    )

        # ---------------------------------------------------------
        # Labels
        # ---------------------------------------------------------

        labels_raw = data.get(
            "labels",
            [],
        )

        label_bgr = self._parse_color(
            data.get(
                "label_color",
                (255, 180, 0),
            ),
            default_bgr=(0, 180, 255),
        )

        if isinstance(labels_raw, list):

            for item in labels_raw:

                if isinstance(item, dict):

                    text = str(
                        item.get("text", "")
                    )

                    position = item.get(
                        "pos",
                        [0, 0],
                    )

                elif (
                    isinstance(item, (list, tuple))
                    and len(item) >= 2
                ):

                    text = str(item[0])
                    position = item[1]

                else:

                    text = str(item)
                    position = [200, 200]

                if text and len(position) >= 2:

                    position_px = self._world_to_projector(
                        [position[:2]],
                        thickness_mm,
                    )[0]

                    px = int(round(position_px[0]))
                    py = int(round(position_px[1]))

                    cv2.putText(
                        canvas,
                        text,
                        (px, py),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        label_scale,
                        label_bgr,
                        max(1, label_thickness_px),
                        cv2.LINE_AA,
                    )

        # ---------------------------------------------------------
        # HUD
        # ---------------------------------------------------------

        if self.show_hud:

            self._draw_hud(
                canvas=canvas,
                is_connected=is_connected,
                packet_count=packet_count,
                thickness_mm=thickness_mm,
            )

        return canvas

    # -------------------------------------------------------------
    # HUD rendering
    # -------------------------------------------------------------

    def _draw_hud(
        self,
        canvas: np.ndarray,
        is_connected: bool,
        packet_count: int,
        thickness_mm: float,
    ) -> None:

        hud_height = 36

        hud_y = (
            PROJECTOR_HEIGHT - hud_height
        )

        cv2.rectangle(
            canvas,
            (0, hud_y),
            (
                PROJECTOR_WIDTH,
                PROJECTOR_HEIGHT,
            ),
            self.DARK_BG,
            -1,
        )

        cv2.line(
            canvas,
            (0, hud_y),
            (
                PROJECTOR_WIDTH,
                hud_y,
            ),
            (60, 60, 60),
            1,
        )

        if is_connected:

            connection_string = (
                "GH: CONNECTED "
                f"({packet_count} frames)"
            )

            connection_color = (
                0, 255, 0
            )

        else:

            connection_string = (
                "GH: DISCONNECTED | SENSING"
            )

            connection_color = (
                0, 165, 255
            )

        cv2.putText(
            canvas,
            connection_string,
            (12, hud_y + 23),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            connection_color,
            1,
            cv2.LINE_AA,
        )

        parameter_string = (
            "Thick: "
            f"{thickness_mm:.1f}mm [T/G] | "
            "Offset: "
            f"X={self.offset_x_mm:+.1f}mm "
            f"Y={self.offset_y_mm:+.1f}mm "
            "[W/S/A/D]"
        )

        cv2.putText(
            canvas,
            parameter_string,
            (290, hud_y + 23),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (255, 255, 0),
            1,
            cv2.LINE_AA,
        )

        control_string = (
            f"Step:{self.step_mm:.1f}mm "
            "[+/-] | [0] Zero-T | "
            "[H] HUD | [ESC] Exit"
        )

        cv2.putText(
            canvas,
            control_string,
            (
                PROJECTOR_WIDTH - 440,
                hud_y + 23,
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (170, 170, 170),
            1,
            cv2.LINE_AA,
        )

    # -------------------------------------------------------------
    # State snapshot rendering
    # -------------------------------------------------------------

    def render_snapshot(
        self,
        snapshot,
    ) -> np.ndarray:
        """
        Render the five-element snapshot returned by
        ProjectorState.get_snapshot().
        """

        (
            data,
            is_connected,
            packet_count,
            _last_received_time,
            thickness_mm,
        ) = snapshot

        return self.render(
            data=data,
            is_connected=is_connected,
            packet_count=packet_count,
            thickness_mm=thickness_mm,
        )

    # -------------------------------------------------------------
    # OpenCV projector window
    # -------------------------------------------------------------

    def create_window(self) -> None:

        if self.window_created:
            return

        cv2.namedWindow(
            self.WINDOW_NAME,
            cv2.WINDOW_NORMAL,
        )

        cv2.moveWindow(
            self.WINDOW_NAME,
            PROJECTOR_SCREEN_ORIGIN_X,
            PROJECTOR_SCREEN_ORIGIN_Y,
        )

        cv2.setWindowProperty(
            self.WINDOW_NAME,
            cv2.WND_PROP_FULLSCREEN,
            cv2.WINDOW_FULLSCREEN,
        )

        self.window_created = True

    def show_frame(
        self,
        frame: np.ndarray,
    ) -> None:

        if not self.window_created:
            self.create_window()

        cv2.imshow(
            self.WINDOW_NAME,
            frame,
        )

    @staticmethod
    def poll_key(
        delay_ms: int = 16,
    ) -> int:

        return cv2.waitKeyEx(
            int(delay_ms)
        )

    def close(self) -> None:

        if self.window_created:

            cv2.destroyWindow(
                self.WINDOW_NAME
            )

            self.window_created = False