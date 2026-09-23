from pathlib import Path
import sys
import json
import socket
import threading
import time

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
    PROJECTOR_RUNTIME_ROOT,
    PROJECTOR_CALIBRATION_MODE,
    PROJECTOR_WIDTH,
    PROJECTOR_HEIGHT,
    PROJECTOR_SCREEN_ORIGIN_X,
    PROJECTOR_SCREEN_ORIGIN_Y,
    PROJECTOR_HEIGHT_MM,
    PROJECTOR_POS_X_MM,
    PROJECTOR_POS_Y_MM,
    PROJECTOR_OFFSET_X_MM,
    PROJECTOR_OFFSET_Y_MM,
    TIMBER_THICKNESS_MM,
)


class ProjectorState:
    """
    Thread-safe storage for the latest geometry
    received by the projector TCP server.
    """

    def __init__(
        self,
        initial_data: dict,
        initial_thickness_mm: float = 0.0,
    ) -> None:

        self.lock = (
            threading.Lock()
        )

        self.last_received_time = (
            0.0
        )

        self.packet_count = (
            0
        )

        self.client_address = (
            None
        )

        self.is_connected = (
            False
        )

        self.data = (
            initial_data
        )

        self.thickness_mm = float(
            initial_thickness_mm
        )

        if (
            "thickness_mm"
            in self.data
            and self.data[
                "thickness_mm"
            ] > 0
        ):

            self.thickness_mm = float(
                self.data[
                    "thickness_mm"
                ]
            )

    def update_from_json(
        self,
        json_data,
        client_addr,
    ) -> None:

        with self.lock:

            self.last_received_time = (
                time.time()
            )

            self.packet_count += 1

            self.client_address = (
                client_addr
            )

            self.is_connected = (
                True
            )

            self.data = (
                json_data
            )

            if (
                "thickness_mm"
                in json_data
                and json_data[
                    "thickness_mm"
                ] is not None
            ):

                try:

                    value = float(
                        json_data[
                            "thickness_mm"
                        ]
                    )

                    if value >= 0.0:

                        self.thickness_mm = (
                            value
                        )

                except (
                    ValueError,
                    TypeError,
                ):
                    pass

    def set_disconnected(
        self,
    ) -> None:

        with self.lock:

            self.is_connected = (
                False
            )

    def set_thickness(
        self,
        thickness_mm: float,
    ) -> None:

        with self.lock:

            self.thickness_mm = max(
                0.0,
                float(
                    thickness_mm
                ),
            )

    def get_snapshot(
        self,
    ):

        with self.lock:

            return (
                dict(
                    self.data
                ),
                self.is_connected,
                self.packet_count,
                self.last_received_time,
                self.thickness_mm,
            )


class EWoodXProjectorLiveViewer:
    """
    Real-time eWoodX projector viewer.

    Receives newline-delimited JSON geometry
    from Grasshopper over TCP and renders the
    geometry onto the calibrated projector.

    The operational workflow follows the tested
    eWoodX reference implementation.
    """

    WINDOW_NAME = (
        "eWoodX Projector Live Viewer"
    )

    SERVER_HOST = (
        "0.0.0.0"
    )

    SERVER_PORT = (
        9999
    )

    CONNECTION_TIMEOUT = (
        3.0
    )

    DEFAULT_TIMBER_THICKNESS_PX = (
        2
    )

    DEFAULT_CUT_THICKNESS_PX = (
        3
    )

    DEFAULT_MILL_THICKNESS_PX = (
        2
    )

    DEFAULT_DRILL_RADIUS_PX = (
        6
    )

    DEFAULT_DRILL_THICKNESS_PX = (
        2
    )

    DEFAULT_LABEL_SCALE = (
        0.45
    )

    DEFAULT_LABEL_THICKNESS = (
        1
    )

    DARK_BG = (
        15,
        15,
        15,
    )

    def __init__(
        self,
        homography_file: Path | None = None,
        server_host: str | None = None,
        server_port: int | None = None,
    ) -> None:

        self.homography_file = (
            Path(
                homography_file
            )
            if homography_file
            is not None
            else (
                CALIBRATION_ROOT
                / "projector"
                / PROJECTOR_CALIBRATION_MODE
                / "projector_homography.npz"
            )
        )

        self.server_host = (
            server_host
            if server_host is not None
            else self.SERVER_HOST
        )

        self.server_port = (
            int(
                server_port
            )
            if server_port is not None
            else self.SERVER_PORT
        )

        self.projector_height_mm = (
            float(
                PROJECTOR_HEIGHT_MM
            )
        )

        self.projector_pos_x_mm = (
            float(
                PROJECTOR_POS_X_MM
            )
        )

        self.projector_pos_y_mm = (
            float(
                PROJECTOR_POS_Y_MM
            )
        )

        self.offset_x_mm = (
            float(
                PROJECTOR_OFFSET_X_MM
            )
        )

        self.offset_y_mm = (
            float(
                PROJECTOR_OFFSET_Y_MM
            )
        )

        self.step_mm = (
            0.5
        )

        self.show_hud = (
            True
        )

        self.show_grid = (
            False
        )

        self.homography = (
            self._load_homography()
        )

        initial_data = (
            self._initial_state()
        )

        self.state = (
            ProjectorState(
                initial_data=(
                    initial_data
                ),
                initial_thickness_mm=(
                    TIMBER_THICKNESS_MM
                ),
            )
        )

        self._server_thread = (
            None
        )

    # -----------------------------------------------------------------
    # Calibration
    # -----------------------------------------------------------------

    def _load_homography(
        self,
    ) -> np.ndarray:

        if not self.homography_file.exists():

            print(
                "Warning: Projector calibration "
                "not found at "
                f"{self.homography_file}."
            )

            print(
                "Using default identity "
                "homography for testing."
            )

            return np.eye(
                3,
                dtype=np.float32,
            )

        projector_data = np.load(
            self.homography_file,
            allow_pickle=True,
        )

        return (
            projector_data[
                "H_world_to_projector"
            ]
        )

    # -----------------------------------------------------------------
    # Initial state
    # -----------------------------------------------------------------

    def _initial_state(
        self,
    ) -> dict:
        """
        Load the latest sensed Timber measurement as the initial
        projector state.

        DEVELOPMENT_NOTE:

        PROJECTOR_RUNTIME_ROOT is a temporary compatibility bridge for
        the current projector workflow. It preserves the tested reference
        behavior of loading the latest timber_*_measurement.json file.

        Replace this lookup once projection/design obtains the required
        entity data through the database / distributed data workflow.
        """

        json_files = list(
            PROJECTOR_RUNTIME_ROOT.glob(
                "timber_*_measurement.json"
            )
        )

        if not json_files:

            return {
                "source": "None",
                "timber_id": 1,
                "length_mm": 0.0,
                "width_mm": 0.0,
                "thickness_mm": 0.0,
                "contour_mm": [],
                "corners_mm": [],
                "defects": [],
                "cut_geo": [],
                "mill_geo": [],
                "points_geo": [],
                "labels": [],
            }

        latest_file = max(
            json_files,
            key=lambda path: (
                path.stat().st_mtime
            ),
        )

        try:

            timber_data = json.loads(
                latest_file.read_text(
                    encoding="utf-8"
                )
            )

        except Exception as error:

            print(
                "[eWoodX] Could not load "
                "projector fallback JSON:"
            )

            print(
                f"  {latest_file}"
            )

            print(
                f"  {error}"
            )

            return {
                "source": "None",
                "timber_id": 1,
                "length_mm": 0.0,
                "width_mm": 0.0,
                "thickness_mm": 0.0,
                "contour_mm": [],
                "corners_mm": [],
                "defects": [],
                "cut_geo": [],
                "mill_geo": [],
                "points_geo": [],
                "labels": [],
            }

        return {
            "source": (
                latest_file.name
            ),
            "timber_id": timber_data.get(
                "timber_id",
                1,
            ),
            "length_mm": timber_data.get(
                "length_mm",
                0.0,
            ),
            "width_mm": timber_data.get(
                "width_mm",
                0.0,
            ),
            "thickness_mm": timber_data.get(
                "timber_thickness_mm",
                TIMBER_THICKNESS_MM,
            ),
            "contour_mm": timber_data.get(
                "contour_mm",
                [],
            ),
            "corners_mm": timber_data.get(
                "corners_mm",
                [],
            ),
            "defects": timber_data.get(
                "defects",
                [],
            ),
            "cut_geo": [],
            "mill_geo": [],
            "points_geo": [],
            "labels": [],
        }

    # -----------------------------------------------------------------
    # Color conversion
    # -----------------------------------------------------------------

    @staticmethod
    def _parse_color(
        color_val,
        default_bgr=(
            255,
            255,
            255,
        ),
    ):
        """
        Convert Hex string, RGB tuple/list,
        or RGB dictionary to OpenCV BGR.
        """

        if color_val is None:

            return (
                default_bgr
            )

        try:

            if isinstance(
                color_val,
                str,
            ):

                color_string = (
                    color_val
                    .strip()
                    .lstrip("#")
                )

                if len(
                    color_string
                ) in (
                    6,
                    8,
                ):

                    red = int(
                        color_string[
                            0:2
                        ],
                        16,
                    )

                    green = int(
                        color_string[
                            2:4
                        ],
                        16,
                    )

                    blue = int(
                        color_string[
                            4:6
                        ],
                        16,
                    )

                    return (
                        blue,
                        green,
                        red,
                    )

            elif isinstance(
                color_val,
                (
                    list,
                    tuple,
                ),
            ):

                if len(
                    color_val
                ) >= 3:

                    red = int(
                        color_val[0]
                    )

                    green = int(
                        color_val[1]
                    )

                    blue = int(
                        color_val[2]
                    )

                    return (
                        blue,
                        green,
                        red,
                    )

            elif isinstance(
                color_val,
                dict,
            ):

                red = int(
                    color_val.get(
                        "R",
                        color_val.get(
                            "r",
                            255,
                        ),
                    )
                )

                green = int(
                    color_val.get(
                        "G",
                        color_val.get(
                            "g",
                            255,
                        ),
                    )
                )

                blue = int(
                    color_val.get(
                        "B",
                        color_val.get(
                            "b",
                            255,
                        ),
                    )
                )

                return (
                    blue,
                    green,
                    red,
                )

        except Exception:
            pass

        return (
            default_bgr
        )

    # -----------------------------------------------------------------
    # World -> projector
    # -----------------------------------------------------------------

    def _world_to_projector(
        self,
        points_mm,
        off_x=0.0,
        off_y=0.0,
        thickness_mm=0.0,
    ) -> np.ndarray:

        if (
            points_mm is None
            or len(
                points_mm
            ) == 0
        ):

            return np.empty(
                (
                    0,
                    2,
                ),
                dtype=np.float32,
            )

        points = np.asarray(
            points_mm,
            dtype=np.float32,
        ).copy()

        if (
            points.ndim == 1
            and len(
                points
            ) == 2
        ):

            points = (
                points.reshape(
                    1,
                    2,
                )
            )

        points[
            :,
            0,
        ] += off_x

        points[
            :,
            1,
        ] += off_y

        # -------------------------------------------------------------
        # Parallax compensation
        # -------------------------------------------------------------

        if (
            thickness_mm > 0.0
            and self.projector_height_mm
            > thickness_mm
        ):

            scale_factor = (
                self.projector_height_mm
                / (
                    self.projector_height_mm
                    - thickness_mm
                )
            )

            points[
                :,
                0,
            ] = (
                self.projector_pos_x_mm
                + (
                    points[
                        :,
                        0,
                    ]
                    - self.projector_pos_x_mm
                )
                * scale_factor
            )

            points[
                :,
                1,
            ] = (
                self.projector_pos_y_mm
                + (
                    points[
                        :,
                        1,
                    ]
                    - self.projector_pos_y_mm
                )
                * scale_factor
            )

        projected = (
            cv2.perspectiveTransform(
                points.reshape(
                    -1,
                    1,
                    2,
                ),
                self.homography,
            )
        )

        return (
            projected.reshape(
                -1,
                2,
            )
        )

    # -----------------------------------------------------------------
    # TCP server
    # -----------------------------------------------------------------

    def _socket_server(
        self,
    ) -> None:

        server = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        )

        server.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )

        try:

            server.bind(
                (
                    self.server_host,
                    self.server_port,
                )
            )

            server.listen(
                5
            )

            print(
                "[TCP Server] Listening on port "
                f"{self.server_port} "
                "(Connect from Grasshopper using "
                "127.0.0.1:"
                f"{self.server_port})..."
            )

        except Exception as error:

            print(
                "[TCP Server Error] Failed to bind "
                f"{self.server_host}:"
                f"{self.server_port}: "
                f"{error}"
            )

            return

        while True:

            try:

                client, address = (
                    server.accept()
                )

                print(
                    "[TCP Server] Connected from "
                    "Grasshopper client "
                    f"{address}"
                )

                buffer = ""

                while True:

                    chunk = (
                        client.recv(
                            65536
                        )
                    )

                    if not chunk:

                        print(
                            "[TCP Server] Client "
                            f"{address} disconnected."
                        )

                        self.state.set_disconnected()

                        break

                    buffer += (
                        chunk.decode(
                            "utf-8",
                            errors="replace",
                        )
                    )

                    while (
                        "\n"
                        in buffer
                    ):

                        (
                            line,
                            buffer,
                        ) = (
                            buffer.split(
                                "\n",
                                1,
                            )
                        )

                        line = (
                            line.strip()
                        )

                        if not line:
                            continue

                        try:

                            payload = (
                                json.loads(
                                    line
                                )
                            )

                            self.state.update_from_json(
                                payload,
                                address,
                            )

                        except json.JSONDecodeError:
                            pass

            except Exception:

                self.state.set_disconnected()

                time.sleep(
                    0.5
                )

    def _start_server(
        self,
    ) -> None:

        self._server_thread = (
            threading.Thread(
                target=(
                    self._socket_server
                ),
                daemon=True,
            )
        )

        self._server_thread.start()

    # -----------------------------------------------------------------
    # Rendering
    # -----------------------------------------------------------------

    def _render_frame(
        self,
        data,
        is_connected,
        packet_count,
        thickness_mm,
    ) -> np.ndarray:

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

        # -------------------------------------------------------------
        # Timber contour
        # -------------------------------------------------------------

        contour_raw = (
            data.get(
                "contour_mm"
            )
            or data.get(
                "timber_contour"
            )
            or data.get(
                "main_border"
            )
        )

        timber_color_raw = (
            data.get(
                "timber_color",
                (
                    255,
                    255,
                    255,
                ),
            )
        )

        timber_bgr = (
            self._parse_color(
                timber_color_raw,
                default_bgr=(
                    255,
                    255,
                    255,
                ),
            )
        )

        if (
            contour_raw
            and len(
                contour_raw
            ) >= 3
        ):

            points_px = (
                self._world_to_projector(
                    contour_raw,
                    self.offset_x_mm,
                    self.offset_y_mm,
                    thickness_mm,
                )
            )

            points_int = (
                np.round(
                    points_px
                )
                .astype(
                    np.int32
                )
                .reshape(
                    -1,
                    1,
                    2,
                )
            )

            cv2.polylines(
                canvas,
                [
                    points_int
                ],
                True,
                timber_bgr,
                max(
                    1,
                    timber_thickness_px,
                ),
                cv2.LINE_AA,
            )

        # -------------------------------------------------------------
        # Timber corners
        # -------------------------------------------------------------

        corners_raw = (
            data.get(
                "corners_mm"
            )
            or data.get(
                "timber_corners"
            )
        )

        if (
            corners_raw
            and len(
                corners_raw
            ) >= 3
        ):

            corners_px = (
                self._world_to_projector(
                    corners_raw,
                    self.offset_x_mm,
                    self.offset_y_mm,
                    thickness_mm,
                )
            )

            for index, point in enumerate(
                corners_px
            ):

                px = int(
                    round(
                        point[0]
                    )
                )

                py = int(
                    round(
                        point[1]
                    )
                )

                cv2.circle(
                    canvas,
                    (
                        px,
                        py,
                    ),
                    4,
                    timber_bgr,
                    -1,
                    cv2.LINE_AA,
                )

                cv2.putText(
                    canvas,
                    f"C{index + 1}",
                    (
                        px + 6,
                        py - 6,
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.35,
                    timber_bgr,
                    1,
                    cv2.LINE_AA,
                )

        # -------------------------------------------------------------
        # Defects
        # -------------------------------------------------------------

        defects_raw = (
            data.get(
                "defects",
                [],
            )
        )

        for defect in defects_raw:

            defect_x = (
                defect.get(
                    "x_mm",
                    defect.get(
                        "x",
                        0,
                    ),
                )
            )

            defect_y = (
                defect.get(
                    "y_mm",
                    defect.get(
                        "y",
                        0,
                    ),
                )
            )

            defect_px = (
                self._world_to_projector(
                    [
                        [
                            defect_x,
                            defect_y,
                        ]
                    ],
                    self.offset_x_mm,
                    self.offset_y_mm,
                    thickness_mm,
                )[0]
            )

            px = int(
                round(
                    defect_px[0]
                )
            )

            py = int(
                round(
                    defect_px[1]
                )
            )

            cv2.drawMarker(
                canvas,
                (
                    px,
                    py,
                ),
                (
                    0,
                    165,
                    255,
                ),
                cv2.MARKER_TILTED_CROSS,
                14,
                2,
                cv2.LINE_AA,
            )

        # -------------------------------------------------------------
        # Milling geometry
        # -------------------------------------------------------------

        mill_geo = (
            data.get(
                "mill_geo"
            )
            or data.get(
                "mill"
            )
            or data.get(
                "milling",
                [],
            )
        )

        mill_color_raw = (
            data.get(
                "mill_color",
                (
                    0,
                    220,
                    255,
                ),
            )
        )

        mill_bgr = (
            self._parse_color(
                mill_color_raw,
                default_bgr=(
                    255,
                    220,
                    0,
                ),
            )
        )

        if isinstance(
            mill_geo,
            list,
        ):

            for polyline in mill_geo:

                if (
                    polyline
                    and len(
                        polyline
                    ) >= 2
                ):

                    points_px = (
                        self._world_to_projector(
                            polyline,
                            self.offset_x_mm,
                            self.offset_y_mm,
                            thickness_mm,
                        )
                    )

                    points_int = (
                        np.round(
                            points_px
                        )
                        .astype(
                            np.int32
                        )
                        .reshape(
                            -1,
                            1,
                            2,
                        )
                    )

                    cv2.polylines(
                        canvas,
                        [
                            points_int
                        ],
                        False,
                        mill_bgr,
                        max(
                            1,
                            mill_thickness_px,
                        ),
                        cv2.LINE_AA,
                    )

        # -------------------------------------------------------------
        # Cutting geometry
        # -------------------------------------------------------------

        cut_geo = (
            data.get(
                "cut_geo"
            )
            or data.get(
                "cut"
            )
            or data.get(
                "cutting",
                [],
            )
        )

        cut_color_raw = (
            data.get(
                "cut_color",
                (
                    255,
                    30,
                    30,
                ),
            )
        )

        cut_bgr = (
            self._parse_color(
                cut_color_raw,
                default_bgr=(
                    30,
                    30,
                    255,
                ),
            )
        )

        if isinstance(
            cut_geo,
            list,
        ):

            for polyline in cut_geo:

                if (
                    polyline
                    and len(
                        polyline
                    ) >= 2
                ):

                    points_px = (
                        self._world_to_projector(
                            polyline,
                            self.offset_x_mm,
                            self.offset_y_mm,
                            thickness_mm,
                        )
                    )

                    points_int = (
                        np.round(
                            points_px
                        )
                        .astype(
                            np.int32
                        )
                        .reshape(
                            -1,
                            1,
                            2,
                        )
                    )

                    cv2.polylines(
                        canvas,
                        [
                            points_int
                        ],
                        False,
                        cut_bgr,
                        max(
                            1,
                            cut_thickness_px,
                        ),
                        cv2.LINE_AA,
                    )

        # -------------------------------------------------------------
        # Drill / reference points
        # -------------------------------------------------------------

        points_geo = (
            data.get(
                "points_geo"
            )
            or data.get(
                "points",
                [],
            )
        )

        point_color_raw = (
            data.get(
                "point_color",
                (
                    0,
                    255,
                    100,
                ),
            )
        )

        point_bgr = (
            self._parse_color(
                point_color_raw,
                default_bgr=(
                    100,
                    255,
                    0,
                ),
            )
        )

        if isinstance(
            points_geo,
            list,
        ):

            for point in points_geo:

                if (
                    point
                    and len(
                        point
                    ) >= 2
                ):

                    point_px = (
                        self._world_to_projector(
                            [
                                point[
                                    :2
                                ]
                            ],
                            self.offset_x_mm,
                            self.offset_y_mm,
                            thickness_mm,
                        )[0]
                    )

                    px = int(
                        round(
                            point_px[0]
                        )
                    )

                    py = int(
                        round(
                            point_px[1]
                        )
                    )

                    cv2.circle(
                        canvas,
                        (
                            px,
                            py,
                        ),
                        max(
                            1,
                            drill_radius_px,
                        ),
                        point_bgr,
                        max(
                            1,
                            drill_thickness_px,
                        ),
                        cv2.LINE_AA,
                    )

                    cv2.drawMarker(
                        canvas,
                        (
                            px,
                            py,
                        ),
                        point_bgr,
                        cv2.MARKER_CROSS,
                        max(
                            4,
                            drill_radius_px
                            * 2,
                        ),
                        1,
                        cv2.LINE_AA,
                    )

        # -------------------------------------------------------------
        # Labels
        # -------------------------------------------------------------

        labels_raw = (
            data.get(
                "labels",
                [],
            )
        )

        label_color_raw = (
            data.get(
                "label_color",
                (
                    255,
                    180,
                    0,
                ),
            )
        )

        label_bgr = (
            self._parse_color(
                label_color_raw,
                default_bgr=(
                    0,
                    180,
                    255,
                ),
            )
        )

        if isinstance(
            labels_raw,
            list,
        ):

            for item in labels_raw:

                if isinstance(
                    item,
                    dict,
                ):

                    text = str(
                        item.get(
                            "text",
                            "",
                        )
                    )

                    position = (
                        item.get(
                            "pos",
                            [
                                0,
                                0,
                            ],
                        )
                    )

                elif (
                    isinstance(
                        item,
                        (
                            list,
                            tuple,
                        ),
                    )
                    and len(
                        item
                    ) >= 2
                ):

                    text = str(
                        item[0]
                    )

                    position = (
                        item[1]
                    )

                else:

                    text = str(
                        item
                    )

                    position = [
                        200,
                        200,
                    ]

                if (
                    text
                    and len(
                        position
                    ) >= 2
                ):

                    position_px = (
                        self._world_to_projector(
                            [
                                position[
                                    :2
                                ]
                            ],
                            self.offset_x_mm,
                            self.offset_y_mm,
                            thickness_mm,
                        )[0]
                    )

                    px = int(
                        round(
                            position_px[0]
                        )
                    )

                    py = int(
                        round(
                            position_px[1]
                        )
                    )

                    cv2.putText(
                        canvas,
                        text,
                        (
                            px,
                            py,
                        ),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        label_scale,
                        label_bgr,
                        max(
                            1,
                            label_thickness_px,
                        ),
                        cv2.LINE_AA,
                    )

        # -------------------------------------------------------------
        # HUD
        # -------------------------------------------------------------

        if self.show_hud:

            hud_height = (
                36
            )

            hud_y = (
                PROJECTOR_HEIGHT
                - hud_height
            )

            cv2.rectangle(
                canvas,
                (
                    0,
                    hud_y,
                ),
                (
                    PROJECTOR_WIDTH,
                    PROJECTOR_HEIGHT,
                ),
                self.DARK_BG,
                -1,
            )

            cv2.line(
                canvas,
                (
                    0,
                    hud_y,
                ),
                (
                    PROJECTOR_WIDTH,
                    hud_y,
                ),
                (
                    60,
                    60,
                    60,
                ),
                1,
            )

            connection_string = (
                "GH: CONNECTED "
                f"({packet_count} frames)"
                if is_connected
                else (
                    "GH: LISTENING "
                    f"(port {self.server_port})"
                )
            )

            connection_color = (
                (
                    0,
                    255,
                    0,
                )
                if is_connected
                else (
                    0,
                    165,
                    255,
                )
            )

            cv2.putText(
                canvas,
                connection_string,
                (
                    12,
                    hud_y + 23,
                ),
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
                (
                    290,
                    hud_y + 23,
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (
                    255,
                    255,
                    0,
                ),
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
                    PROJECTOR_WIDTH
                    - 440,
                    hud_y + 23,
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (
                    170,
                    170,
                    170,
                ),
                1,
                cv2.LINE_AA,
            )

        return (
            canvas
        )

    # -----------------------------------------------------------------
    # Window
    # -----------------------------------------------------------------

    def _create_window(
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

    # -----------------------------------------------------------------
    # Keyboard controls
    # -----------------------------------------------------------------

    def _handle_key(
        self,
        key,
    ) -> bool:
        """
        Handle viewer controls.

        Returns False when the viewer should exit.
        """

        (
            _,
            _,
            _,
            _,
            thickness_mm,
        ) = (
            self.state.get_snapshot()
        )

        if key in (
            27,
            ord("q"),
            ord("Q"),
        ):

            return (
                False
            )

        # -------------------------------------------------------------
        # Thickness
        # -------------------------------------------------------------

        if key == ord("t"):

            thickness_mm += (
                1.0
            )

            self.state.set_thickness(
                thickness_mm
            )

            print(
                "Thickness: "
                f"{thickness_mm:.1f} mm"
            )

        elif key == ord("T"):

            thickness_mm += (
                5.0
            )

            self.state.set_thickness(
                thickness_mm
            )

            print(
                "Thickness: "
                f"{thickness_mm:.1f} mm"
            )

        elif key == ord("g"):

            thickness_mm = max(
                0.0,
                thickness_mm
                - 1.0,
            )

            self.state.set_thickness(
                thickness_mm
            )

            print(
                "Thickness: "
                f"{thickness_mm:.1f} mm"
            )

        elif key == ord("G"):

            thickness_mm = max(
                0.0,
                thickness_mm
                - 5.0,
            )

            self.state.set_thickness(
                thickness_mm
            )

            print(
                "Thickness: "
                f"{thickness_mm:.1f} mm"
            )

        elif key == ord("0"):

            self.state.set_thickness(
                0.0
            )

            print(
                "Thickness reset to 0.0 mm "
                "(Table level)"
            )

        # -------------------------------------------------------------
        # Offset nudging
        # -------------------------------------------------------------

        elif key in (
            2490368,
            ord("w"),
            ord("W"),
        ):

            self.offset_y_mm += (
                self.step_mm
            )

        elif key in (
            2621440,
            ord("s"),
            ord("S"),
        ):

            self.offset_y_mm -= (
                self.step_mm
            )

        elif key in (
            2555904,
            ord("d"),
            ord("D"),
        ):

            self.offset_x_mm += (
                self.step_mm
            )

        elif key in (
            2424832,
            ord("a"),
            ord("A"),
        ):

            self.offset_x_mm -= (
                self.step_mm
            )

        # -------------------------------------------------------------
        # Step size
        # -------------------------------------------------------------

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
            ]

            index = min(
                len(
                    steps
                ) - 1,
                (
                    steps.index(
                        self.step_mm
                    ) + 1
                    if self.step_mm
                    in steps
                    else 2
                ),
            )

            self.step_mm = (
                steps[
                    index
                ]
            )

            print(
                "Nudge step: "
                f"{self.step_mm:.2f} mm"
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
            ]

            index = max(
                0,
                (
                    steps.index(
                        self.step_mm
                    ) - 1
                    if self.step_mm
                    in steps
                    else 2
                ),
            )

            self.step_mm = (
                steps[
                    index
                ]
            )

            print(
                "Nudge step: "
                f"{self.step_mm:.2f} mm"
            )

        # -------------------------------------------------------------
        # Reset offsets
        # -------------------------------------------------------------

        elif key in (
            ord("r"),
            ord("R"),
        ):

            self.offset_x_mm = (
                0.0
            )

            self.offset_y_mm = (
                0.0
            )

            print(
                "Offsets reset to "
                "X=0.0 mm, Y=0.0 mm"
            )

        # -------------------------------------------------------------
        # HUD
        # -------------------------------------------------------------

        elif key in (
            ord("h"),
            ord("H"),
        ):

            self.show_hud = (
                not self.show_hud
            )

        return (
            True
        )

    # -----------------------------------------------------------------
    # Information
    # -----------------------------------------------------------------

    def _print_startup_info(
        self,
    ) -> None:

        (
            current_data,
            _,
            _,
            _,
            thickness_mm,
        ) = (
            self.state.get_snapshot()
        )

        print()
        print(
            "=" * 65
        )

        print(
            "eWoodX Real-Time "
            "Projector Live Viewer Running"
        )

        print(
            "  Resolution:      "
            f"{PROJECTOR_WIDTH} x "
            f"{PROJECTOR_HEIGHT}"
        )

        print(
            "  Window Position: "
            f"X={PROJECTOR_SCREEN_ORIGIN_X}, "
            f"Y={PROJECTOR_SCREEN_ORIGIN_Y}"
        )

        print(
            "  TCP Server:      "
            f"{self.server_host}:"
            f"{self.server_port}"
        )

        print(
            "  Base Thickness:  "
            f"{thickness_mm:.1f} mm"
        )

        print(
            "  Initial Source:  "
            f"{current_data.get('source', 'None')}"
        )

        print(
            "=" * 65
        )

        print(
            "Interactive Controls:"
        )

        print(
            "  T / G           : "
            "Increase / Decrease Thickness "
            "(+/- 1.0 mm)"
        )

        print(
            "  Shift+T / G     : "
            "Increase / Decrease Thickness "
            "(+/- 5.0 mm)"
        )

        print(
            "  0 (Zero)        : "
            "Reset Thickness to 0.0 mm "
            "(Table Plane)"
        )

        print(
            "  W / S / A / D   : "
            "Nudge Real-World Offsets "
            "Y / X (+/- step)"
        )

        print(
            "  + / -           : "
            "Change Nudge Step "
            "(0.1, 0.5, 1.0, 2.0, 5.0 mm)"
        )

        print(
            "  R               : "
            "Reset Offsets to (0, 0)"
        )

        print(
            "  H               : "
            "Toggle HUD Bar"
        )

        print(
            "  ESC / Q         : "
            "Exit Viewer"
        )

        print(
            "=" * 65
        )

        print()

    # -----------------------------------------------------------------
    # Run
    # -----------------------------------------------------------------

    def run(
        self,
    ) -> None:

        self._start_server()

        self._create_window()

        self._print_startup_info()

        try:

            while True:

                (
                    current_data,
                    is_connected,
                    packet_count,
                    last_received_time,
                    thickness_mm,
                ) = (
                    self.state.get_snapshot()
                )

                if (
                    is_connected
                    and (
                        time.time()
                        - last_received_time
                        > self.CONNECTION_TIMEOUT
                    )
                ):

                    self.state.set_disconnected()

                    is_connected = (
                        False
                    )

                frame = (
                    self._render_frame(
                        current_data,
                        is_connected,
                        packet_count,
                        thickness_mm,
                    )
                )

                cv2.imshow(
                    self.WINDOW_NAME,
                    frame,
                )

                key = (
                    cv2.waitKeyEx(
                        16
                    )
                )

                if not self._handle_key(
                    key
                ):

                    break

        finally:

            cv2.destroyAllWindows()


def main() -> None:

    viewer = (
        EWoodXProjectorLiveViewer()
    )

    viewer.run()


if __name__ == "__main__":
    main()