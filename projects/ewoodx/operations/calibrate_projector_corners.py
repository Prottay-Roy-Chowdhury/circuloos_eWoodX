from pathlib import Path
import sys

import cv2
import numpy as np


PROJECT_ROOT = Path(
    __file__
).resolve().parents[3]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from projects.ewoodx.config import (
    CALIBRATION_ROOT,
    TABLE_WIDTH_MM,
    TABLE_HEIGHT_MM,

    PROJECTOR_WIDTH,
    PROJECTOR_HEIGHT,
    PROJECTOR_SCREEN_ORIGIN_X,
    PROJECTOR_SCREEN_ORIGIN_Y,
)


class EWoodXProjectorCornerCalibration:
    """
    eWoodX interactive direct 4-corner
    projector calibration.

    The operation aligns the projector with
    the four physical eWoodX workspace markers
    and calculates the world-to-projector
    homography.
    """

    WINDOW_NAME = (
        "eWoodX - 4-Corner Projector Calibration"
    )

    def __init__(
        self,
        output_file: Path | None = None,
    ) -> None:

        self.output_file = (
            Path(output_file)
            if output_file is not None
            else (
                CALIBRATION_ROOT
                / "projector"
                / "manual"
                / "projector_homography.npz"
            )
        )

        self.report_file = (
            self.output_file.with_suffix(
                ".txt"
            )
        )

        self.markers_mm = {
            1: np.array(
                [0.0, 0.0],
                dtype=np.float32,
            ),
            0: np.array(
                [TABLE_WIDTH_MM, 0.0],
                dtype=np.float32,
            ),
            2: np.array(
                [0.0, TABLE_HEIGHT_MM],
                dtype=np.float32,
            ),
            3: np.array(
                [
                    TABLE_WIDTH_MM,
                    TABLE_HEIGHT_MM,
                ],
                dtype=np.float32,
            ),
        }

        margin_ratio = 0.05

        margin_x = (
            PROJECTOR_WIDTH
            * margin_ratio
        )

        margin_y = (
            PROJECTOR_HEIGHT
            * margin_ratio
        )

        initial_positions = {
            1: [
                margin_x,
                PROJECTOR_HEIGHT - margin_y,
            ],
            0: [
                PROJECTOR_WIDTH - margin_x,
                PROJECTOR_HEIGHT - margin_y,
            ],
            2: [
                margin_x,
                margin_y,
            ],
            3: [
                PROJECTOR_WIDTH - margin_x,
                margin_y,
            ],
        }

        # -------------------------------------------------------------
        # Existing calibration seeds the initial crosshair positions.
        # -------------------------------------------------------------

        if self.output_file.exists():

            try:

                data = np.load(
                    self.output_file,
                    allow_pickle=True,
                )

                homography = (
                    data[
                        "H_world_to_projector"
                    ]
                )

                for marker_id, mm_point in (
                    self.markers_mm.items()
                ):

                    projector_point = (
                        cv2.perspectiveTransform(
                            mm_point.reshape(
                                1,
                                1,
                                2,
                            ),
                            homography,
                        )
                        .reshape(2)
                    )

                    initial_positions[
                        marker_id
                    ] = [
                        float(
                            projector_point[0]
                        ),
                        float(
                            projector_point[1]
                        ),
                    ]

            except Exception:
                pass

        self.marker_px = {
            marker_id: np.array(
                position,
                dtype=np.float32,
            )
            for marker_id, position
            in initial_positions.items()
        }

        self.active_id = 1
        self.step_px = 1.0
        self.dragging_id = None

    # -----------------------------------------------------------------
    # Mouse interaction
    # -----------------------------------------------------------------

    def mouse_callback(
        self,
        event,
        x,
        y,
        flags,
        param,
    ) -> None:

        if event == cv2.EVENT_LBUTTONDOWN:

            min_dist = 50.0
            closest = None

            for marker_id, point in (
                self.marker_px.items()
            ):

                distance = np.hypot(
                    point[0] - x,
                    point[1] - y,
                )

                if distance < min_dist:

                    min_dist = distance
                    closest = marker_id

            if closest is not None:

                self.active_id = closest
                self.dragging_id = closest

                self.marker_px[
                    closest
                ] = np.array(
                    [
                        float(x),
                        float(y),
                    ],
                    dtype=np.float32,
                )

        elif event == cv2.EVENT_MOUSEMOVE:

            if self.dragging_id is not None:

                self.marker_px[
                    self.dragging_id
                ] = np.array(
                    [
                        float(x),
                        float(y),
                    ],
                    dtype=np.float32,
                )

        elif event == cv2.EVENT_LBUTTONUP:

            self.dragging_id = None

    # -----------------------------------------------------------------
    # Rendering
    # -----------------------------------------------------------------

    def draw_crosshair(
        self,
        canvas,
        point,
        label,
        is_active=False,
        size=24,
    ) -> None:

        x = int(
            round(
                point[0]
            )
        )

        y = int(
            round(
                point[1]
            )
        )

        white = (
            255,
            255,
            255,
        )

        red = (
            0,
            0,
            255,
        )

        yellow = (
            0,
            255,
            255,
        )

        gray = (
            150,
            150,
            150,
        )

        color = (
            yellow
            if is_active
            else white
        )

        thickness = (
            2
            if is_active
            else 1
        )

        cv2.circle(
            canvas,
            (x, y),
            12,
            color,
            thickness,
            cv2.LINE_AA,
        )

        cv2.circle(
            canvas,
            (x, y),
            2,
            (
                red
                if is_active
                else color
            ),
            -1,
            cv2.LINE_AA,
        )

        gap = 4

        cv2.line(
            canvas,
            (x - size, y),
            (x - gap, y),
            color,
            thickness,
            cv2.LINE_AA,
        )

        cv2.line(
            canvas,
            (x + gap, y),
            (x + size, y),
            color,
            thickness,
            cv2.LINE_AA,
        )

        cv2.line(
            canvas,
            (x, y - size),
            (x, y - gap),
            color,
            thickness,
            cv2.LINE_AA,
        )

        cv2.line(
            canvas,
            (x, y + gap),
            (x, y + size),
            color,
            thickness,
            cv2.LINE_AA,
        )

        cv2.putText(
            canvas,
            label,
            (x + 16, y - 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            color,
            1,
            cv2.LINE_AA,
        )

        coordinate_text = (
            f"({x}, {y})"
        )

        cv2.putText(
            canvas,
            coordinate_text,
            (x + 16, y + 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            gray,
            1,
            cv2.LINE_AA,
        )

    def render(
        self,
    ) -> np.ndarray:

        canvas = np.zeros(
            (
                PROJECTOR_HEIGHT,
                PROJECTOR_WIDTH,
                3,
            ),
            dtype=np.uint8,
        )

        ordered_ids = [
            1,
            0,
            3,
            2,
        ]

        quad_points = np.array(
            [
                self.marker_px[
                    marker_id
                ]
                for marker_id
                in ordered_ids
            ],
            dtype=np.int32,
        ).reshape(
            -1,
            1,
            2,
        )

        cv2.polylines(
            canvas,
            [quad_points],
            True,
            (40, 40, 40),
            1,
            cv2.LINE_AA,
        )

        point_1 = tuple(
            np.round(
                self.marker_px[1]
            ).astype(int)
        )

        point_3 = tuple(
            np.round(
                self.marker_px[3]
            ).astype(int)
        )

        point_0 = tuple(
            np.round(
                self.marker_px[0]
            ).astype(int)
        )

        point_2 = tuple(
            np.round(
                self.marker_px[2]
            ).astype(int)
        )

        cv2.line(
            canvas,
            point_1,
            point_3,
            (25, 25, 25),
            1,
            cv2.LINE_AA,
        )

        cv2.line(
            canvas,
            point_0,
            point_2,
            (25, 25, 25),
            1,
            cv2.LINE_AA,
        )

        labels = {
            1: (
                "Marker 1 "
                "(0,0) Origin"
            ),
            0: (
                "Marker 0 "
                f"({TABLE_WIDTH_MM:.0f},0)"
            ),
            2: (
                "Marker 2 "
                f"(0,{TABLE_HEIGHT_MM:.0f})"
            ),
            3: (
                "Marker 3 "
                f"({TABLE_WIDTH_MM:.0f},"
                f"{TABLE_HEIGHT_MM:.0f})"
            ),
        }

        for marker_id in [
            1,
            0,
            2,
            3,
        ]:

            self.draw_crosshair(
                canvas,
                self.marker_px[
                    marker_id
                ],
                labels[
                    marker_id
                ],
                is_active=(
                    marker_id
                    == self.active_id
                ),
            )

        cyan = (
            255,
            255,
            0,
        )

        gray = (
            150,
            150,
            150,
        )

        title = (
            "eWoodX 4-Corner Alignment"
            "  |  Active: Marker "
            f"{self.active_id}"
            "  |  Step: "
            f"{self.step_px:.1f} px"
        )

        cv2.putText(
            canvas,
            title,
            (25, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            cyan,
            1,
            cv2.LINE_AA,
        )

        instructions = (
            "Controls: [1/0/2/3/TAB] Select Marker"
            "  |  [W/S/A/D or Arrows] Nudge"
            "  |  [+/-] Step"
            "  |  [SPACE/ENTER] Save"
            "  |  [ESC] Exit"
        )

        cv2.putText(
            canvas,
            instructions,
            (
                25,
                PROJECTOR_HEIGHT - 20,
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            gray,
            1,
            cv2.LINE_AA,
        )

        return canvas

    # -----------------------------------------------------------------
    # Save calibration
    # -----------------------------------------------------------------

    def save_calibration(
        self,
    ) -> bool:

        world_points = np.array(
            [
                self.markers_mm[1],
                self.markers_mm[0],
                self.markers_mm[2],
                self.markers_mm[3],
            ],
            dtype=np.float32,
        )

        projector_points = np.array(
            [
                self.marker_px[1],
                self.marker_px[0],
                self.marker_px[2],
                self.marker_px[3],
            ],
            dtype=np.float32,
        )

        homography, _ = (
            cv2.findHomography(
                world_points,
                projector_points,
                method=0,
            )
        )

        if homography is None:

            print(
                "ERROR: Failed to compute "
                "homography matrix."
            )

            return False

        self.output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        np.savez(
            self.output_file,
            H_world_to_projector=(
                homography
            ),
            world_points_mm=(
                world_points
            ),
            projector_points_px=(
                projector_points
            ),
            projector_resolution=(
                np.array(
                    [
                        PROJECTOR_WIDTH,
                        PROJECTOR_HEIGHT,
                    ]
                )
            ),
        )

        with self.report_file.open(
            "w",
            encoding="utf-8",
        ) as report:

            report.write(
                "eWoodX DIRECT 4-CORNER "
                "PROJECTOR CALIBRATION\n"
            )

            report.write(
                "=" * 55
                + "\n\n"
            )

            report.write(
                "World -> Projector "
                "Homography:\n"
            )

            report.write(
                np.array2string(
                    homography,
                    precision=10,
                )
                + "\n\n"
            )

            report.write(
                "Aligned Points:\n"
            )

            for marker_id in [
                1,
                0,
                2,
                3,
            ]:

                world_point = (
                    self.markers_mm[
                        marker_id
                    ]
                )

                projector_point = (
                    self.marker_px[
                        marker_id
                    ]
                )

                report.write(
                    f"Marker {marker_id}: "
                    "World=("
                    f"{world_point[0]:.1f}, "
                    f"{world_point[1]:.1f}"
                    ") mm  ->  Projector=("
                    f"{projector_point[0]:.2f}, "
                    f"{projector_point[1]:.2f}"
                    ") px\n"
                )

        print()
        print(
            "=" * 60
        )

        print(
            "CALIBRATION SAVED SUCCESSFULLY!"
        )

        print(
            f"NPZ: {self.output_file}"
        )

        print(
            f"TXT: {self.report_file}"
        )

        print()
        print(
            "Homography Matrix:"
        )

        print(
            homography
        )

        print(
            "=" * 60
        )

        print()

        return True

    # -----------------------------------------------------------------
    # Run
    # -----------------------------------------------------------------

    def run(
        self,
    ) -> None:

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

        cv2.setMouseCallback(
            self.WINDOW_NAME,
            self.mouse_callback,
        )

        print()
        print(
            "=" * 60
        )

        print(
            "eWoodX Direct 4-Corner "
            "Projector Calibration"
        )

        print(
            "=" * 60
        )

        print(
            "Look at your table surface and align "
            "the 4 crosshairs"
        )

        print(
            "directly onto the physical "
            "ArUco markers:"
        )

        print(
            "  Marker 1: Bottom-Left  "
            "(0, 0) mm"
        )

        print(
            "  Marker 0: Bottom-Right "
            f"({TABLE_WIDTH_MM:.0f}, 0) mm"
        )

        print(
            "  Marker 2: Top-Left     "
            f"(0, {TABLE_HEIGHT_MM:.0f}) mm"
        )

        print(
            "  Marker 3: Top-Right    "
            f"({TABLE_WIDTH_MM:.0f}, "
            f"{TABLE_HEIGHT_MM:.0f}) mm"
        )

        print()
        print(
            "Press SPACE or ENTER when "
            "all 4 are centered."
        )

        print(
            "=" * 60
        )

        print()

        id_list = [
            1,
            0,
            3,
            2,
        ]

        try:

            while True:

                canvas = (
                    self.render()
                )

                cv2.imshow(
                    self.WINDOW_NAME,
                    canvas,
                )

                key = cv2.waitKeyEx(
                    20
                )

                if key in (
                    27,
                    ord("q"),
                    ord("Q"),
                ):

                    print(
                        "Calibration cancelled."
                    )

                    break

                elif key in (
                    32,
                    10,
                    13,
                ):

                    if self.save_calibration():
                        break

                elif key == ord("1"):

                    self.active_id = 1

                    print(
                        "Selected Marker 1 "
                        "(Bottom-Left)"
                    )

                elif key == ord("0"):

                    self.active_id = 0

                    print(
                        "Selected Marker 0 "
                        "(Bottom-Right)"
                    )

                elif key == ord("2"):

                    self.active_id = 2

                    print(
                        "Selected Marker 2 "
                        "(Top-Left)"
                    )

                elif key == ord("3"):

                    self.active_id = 3

                    print(
                        "Selected Marker 3 "
                        "(Top-Right)"
                    )

                elif key == 9:

                    current_index = (
                        id_list.index(
                            self.active_id
                        )
                        if self.active_id
                        in id_list
                        else 0
                    )

                    self.active_id = (
                        id_list[
                            (
                                current_index
                                + 1
                            )
                            % len(
                                id_list
                            )
                        ]
                    )

                    print(
                        "Selected Marker "
                        f"{self.active_id}"
                    )

                elif key in (
                    2490368,
                    ord("w"),
                    ord("W"),
                ):

                    self.marker_px[
                        self.active_id
                    ][1] -= self.step_px

                elif key in (
                    2621440,
                    ord("s"),
                    ord("S"),
                ):

                    self.marker_px[
                        self.active_id
                    ][1] += self.step_px

                elif key in (
                    2424832,
                    ord("a"),
                    ord("A"),
                ):

                    self.marker_px[
                        self.active_id
                    ][0] -= self.step_px

                elif key in (
                    2555904,
                    ord("d"),
                    ord("D"),
                ):

                    self.marker_px[
                        self.active_id
                    ][0] += self.step_px

                elif key in (
                    ord("+"),
                    ord("="),
                    ord("]"),
                ):

                    steps = [
                        0.1,
                        0.25,
                        0.5,
                        1.0,
                        2.0,
                        5.0,
                        10.0,
                    ]

                    current_index = (
                        steps.index(
                            self.step_px
                        )
                        if self.step_px
                        in steps
                        else 3
                    )

                    self.step_px = (
                        steps[
                            min(
                                len(steps) - 1,
                                current_index + 1,
                            )
                        ]
                    )

                    print(
                        "Nudge step: "
                        f"{self.step_px} px"
                    )

                elif key in (
                    ord("-"),
                    ord("_"),
                    ord("["),
                ):

                    steps = [
                        0.1,
                        0.25,
                        0.5,
                        1.0,
                        2.0,
                        5.0,
                        10.0,
                    ]

                    current_index = (
                        steps.index(
                            self.step_px
                        )
                        if self.step_px
                        in steps
                        else 3
                    )

                    self.step_px = (
                        steps[
                            max(
                                0,
                                current_index - 1,
                            )
                        ]
                    )

                    print(
                        "Nudge step: "
                        f"{self.step_px} px"
                    )

        finally:

            cv2.destroyAllWindows()


def main() -> None:

    operation = (
        EWoodXProjectorCornerCalibration()
    )

    operation.run()


if __name__ == "__main__":
    main()