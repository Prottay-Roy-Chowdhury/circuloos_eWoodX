"""
eWoodX Sensing JSON & Streaming Bridge.

Connects the Design Projection middleware cleanly to the existing
circuloos_eWoodX framework:
1. Input:
   - Accepts standard eWoodX timber measurement JSON (single-timber flat or
     multi-timber capture-level format) as well as simplified dimension JSON
     (e.g. {"width_mm": 1200, "height_mm": 800} or meters).
   - Reads the latest timber_*_measurement.json from PROJECTOR_RUNTIME_ROOT.
   - Optionally subscribes to live `ewoodx.measurement` updates from
     EWoodXStreamHost.
2. Output:
   - Builds complete eWoodX projector geometry payloads directly compatible
     with ProjectorRenderer and EWoodXProjectorComposer.
   - Optionally publishes live updates on the `ewoodx.projector` stream topic
     so the calibrated OpenCV projector renders them immediately.
"""

from __future__ import annotations

import copy
import json
import math
import threading
import time
from pathlib import Path
from typing import Any, Callable

from projects.ewoodx.config.communication import (
    CONTROLLER_STREAM_PORT,
    STREAM_HOST,
)
from projects.ewoodx.config.projection import (
    PROJECTOR_RUNTIME_ROOT,
)
from projects.ewoodx.config.sensing import (
    TABLE_HEIGHT_MM,
    TABLE_WIDTH_MM,
)
from projects.ewoodx.operations.projection.projector_geometry import (
    ProjectorGeometry,
)
from projects.ewoodx.operations.streaming.stream_common import (
    MEASUREMENT,
    PROJECTOR,
    StreamEndpointBase,
)
from projects.ewoodx.operations.design.sample_scenarios import (
    make_custom_board_measurement,
)


def normalize_input_board_json(raw_data: dict[str, Any], source_name: str = "uploaded.json") -> dict[str, Any]:
    """
    Normalize any supported timber JSON input into eWoodX's prepared format.

    Supports:
    - Native eWoodX single-timber measurement JSON (contour_mm, corners_mm, etc.)
    - Native eWoodX multi-timber capture JSON (timbers: [...])
    - Simplified dimension JSON (e.g. {"length_mm": 1200, "width_mm": 800},
      {"width_mm": 1200, "height_mm": 800}, or meters {"width_m": 1.2, "height_m": 0.8})
    """
    if not isinstance(raw_data, dict):
        raise ValueError("El archivo JSON debe contener un objeto raíz ({...}).")

    # Detect simplified size-only JSON without contours
    has_geometry = bool(
        raw_data.get("contour_mm")
        or raw_data.get("corners_mm")
        or raw_data.get("timbers")
        or raw_data.get("timber_contour")
    )

    if not has_geometry:
        # Try mm fields first, then meters
        length_mm = (
            raw_data.get("length_mm")
            or raw_data.get("width_mm")
            or raw_data.get("board_width_mm")
            or raw_data.get("table_width_mm")
        )
        width_mm = (
            raw_data.get("height_mm")
            or raw_data.get("board_height_mm")
            or (raw_data.get("width_mm") if raw_data.get("length_mm") is not None else None)
            or raw_data.get("table_height_mm")
        )
        if length_mm is None and raw_data.get("length_m") is not None:
            length_mm = float(raw_data["length_m"]) * 1000.0
        if length_mm is None and raw_data.get("width_m") is not None:
            length_mm = float(raw_data["width_m"]) * 1000.0
        if width_mm is None and raw_data.get("height_m") is not None:
            width_mm = float(raw_data["height_m"]) * 1000.0
        if width_mm is None and raw_data.get("width_m") is not None and raw_data.get("length_m") is not None:
            width_mm = float(raw_data["width_m"]) * 1000.0

        if length_mm is None or width_mm is None:
            raise ValueError(
                "El JSON no contiene contornos (contour_mm / timbers) ni dimensiones reconocibles "
                "(length_mm + width_mm, width_mm + height_mm, o width_m + height_m)."
            )

        thickness_mm = float(
            raw_data.get("thickness_mm", raw_data.get("timber_thickness_mm", 20.0)) or 20.0
        )
        angle_deg = float(raw_data.get("angle_deg", 0.0) or 0.0)
        raw_data = make_custom_board_measurement(
            length_mm=float(length_mm),
            width_mm=float(width_mm),
            thickness_mm=thickness_mm,
            angle_deg=angle_deg,
            timber_id=str(raw_data.get("timber_id", "JSON-BOARD")),
        )

    prepared = ProjectorGeometry.prepare_measurement(raw_data)
    prepared["source"] = source_name
    return prepared


def extract_board_summary(measurement: dict[str, Any]) -> dict[str, Any]:
    """Extract normalized board contours, bounding box, center, and primary angle."""
    raw_contours = measurement.get("contour_mm") or []
    contours: list[list[list[float]]] = []

    if raw_contours:
        # Check if single contour [[x, y], ...] vs multiple [[[x, y], ...], ...]
        first = raw_contours[0]
        if isinstance(first, (list, tuple)) and len(first) == 2 and isinstance(first[0], (int, float)):
            contours = [[[float(p[0]), float(p[1])] for p in raw_contours]]
        else:
            for c in raw_contours:
                if isinstance(c, (list, tuple)) and len(c) >= 3:
                    contours.append([[float(p[0]), float(p[1])] for p in c])

    raw_corners = measurement.get("corners_mm") or []
    corner_groups: list[list[list[float]]] = []
    if raw_corners:
        first = raw_corners[0]
        if isinstance(first, (list, tuple)) and len(first) == 2 and isinstance(first[0], (int, float)):
            corner_groups = [[[float(p[0]), float(p[1])] for p in raw_corners]]
        else:
            for cg in raw_corners:
                if isinstance(cg, (list, tuple)) and len(cg) >= 3:
                    corner_groups.append([[float(p[0]), float(p[1])] for p in cg])

    all_pts = [pt for poly in contours for pt in poly]
    if not all_pts:
        all_pts = [pt for cg in corner_groups for pt in cg]

    if all_pts:
        min_x = min(p[0] for p in all_pts)
        max_x = max(p[0] for p in all_pts)
        min_y = min(p[1] for p in all_pts)
        max_y = max(p[1] for p in all_pts)
    else:
        min_x, min_y, max_x, max_y = 0.0, 0.0, TABLE_WIDTH_MM, TABLE_HEIGHT_MM

    # Estimate primary board orientation from longest edge of first corner group
    angle_deg = 0.0
    if corner_groups and len(corner_groups[0]) >= 2:
        cg = corner_groups[0]
        best_len = -1.0
        for i in range(len(cg)):
            p0 = cg[i]
            p1 = cg[(i + 1) % len(cg)]
            dx = p1[0] - p0[0]
            dy = p1[1] - p0[1]
            dist = math.hypot(dx, dy)
            if dist > best_len:
                best_len = dist
                ang = math.degrees(math.atan2(dy, dx))
                # Normalize to [-90, 90]
                while ang > 90.0:
                    ang -= 180.0
                while ang < -90.0:
                    ang += 180.0
                angle_deg = ang

    return {
        "source": measurement.get("source", "unknown"),
        "timber_id": measurement.get("timber_id", "N/A"),
        "length_mm": round(float(measurement.get("length_mm", max_x - min_x) or (max_x - min_x)), 2),
        "width_mm": round(float(measurement.get("width_mm", max_y - min_y) or (max_y - min_y)), 2),
        "thickness_mm": round(
            float(measurement.get("thickness_mm", measurement.get("timber_thickness_mm", 0.0)) or 0.0),
            2,
        ),
        "bounds": {
            "min_x": round(min_x, 2),
            "min_y": round(min_y, 2),
            "max_x": round(max_x, 2),
            "max_y": round(max_y, 2),
            "width_mm": round(max_x - min_x, 2),
            "height_mm": round(max_y - min_y, 2),
            "center_x": round(0.5 * (min_x + max_x), 2),
            "center_y": round(0.5 * (min_y + max_y), 2),
        },
        "angle_deg": round(angle_deg, 2),
        "contours_mm": contours,
        "corners_mm": corner_groups,
        "holes_mm": measurement.get("holes_mm") or [],
        "defects": measurement.get("defects") or [],
    }


def load_latest_runtime_measurement(runtime_root: Path | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """Load the latest timber_*_measurement.json from eWoodX projector_runtime."""
    root = Path(runtime_root or PROJECTOR_RUNTIME_ROOT)
    if not root.exists():
        return None, None
    files = list(root.glob("timber_*_measurement.json"))
    if not files:
        return None, None
    latest = max(files, key=lambda p: p.stat().st_mtime_ns)
    with latest.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return normalize_input_board_json(raw, source_name=latest.name), str(latest)


def build_ewoodx_projector_payload(
    measurement: dict[str, Any],
    mosaic_result: dict[str, Any],
    show_board_contour: bool = True,
    colors: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Build a complete geometry dictionary compatible with eWoodX
    ProjectorRenderer and EWoodXProjectorComposer (`ewoodx.projector` topic).
    """
    colors = colors or {}
    proj = mosaic_result["projection_geometry"]

    cut_combined = list(proj.get("cut_geo", []))
    joint_cut_polys = [jc["points"] for jc in proj.get("joint_cut_lines", []) if jc.get("points")]
    for jc_poly in joint_cut_polys:
        cut_combined.append(jc_poly)

    mill_combined = list(proj.get("mill_geo", []))
    # Include tile border and non-joint seam lines in mill/guide channel for calibrated projector
    for border_poly in proj.get("tile_border", []):
        mill_combined.append(border_poly)
    for seam_poly in proj.get("seam_lines", []):
        if seam_poly not in joint_cut_polys:
            mill_combined.append(seam_poly)

    payload: dict[str, Any] = {
        "source": "ewoodx_design_projector",
        "timber_id": measurement.get("timber_id", "N/A"),
        "length_mm": float(measurement.get("length_mm", 0.0) or 0.0),
        "width_mm": float(measurement.get("width_mm", 0.0) or 0.0),
        "thickness_mm": float(
            measurement.get("thickness_mm", measurement.get("timber_thickness_mm", 0.0)) or 0.0
        ),
        "contour_mm": copy.deepcopy(measurement.get("contour_mm", [])) if show_board_contour else [],
        "holes_mm": copy.deepcopy(measurement.get("holes_mm", [])) if show_board_contour else [],
        "corners_mm": copy.deepcopy(measurement.get("corners_mm", [])) if show_board_contour else [],
        "defects": copy.deepcopy(measurement.get("defects", [])) if show_board_contour else [],
        "cut_geo": cut_combined,
        "joint_cut_geo": joint_cut_polys,
        "mill_geo": mill_combined,
        "points_geo": proj.get("points_geo", []),
        "labels": proj.get("labels", []),
        "timber_color": colors.get("timber_color", "#FFFFFF"),
        "cut_color": colors.get("cut_color", "#FF3B30"),
        "mill_color": colors.get("mill_color", "#00DCFF"),
        "point_color": colors.get("point_color", "#30D158"),
        "label_color": colors.get("label_color", "#FFD60A"),
        "cut_thickness_px": 3,
        "mill_thickness_px": 2,
        "drill_radius_px": 7,
        "mosaic_meta": {
            "active_tile": mosaic_result.get("active_tile"),
            "tile_count": len(mosaic_result.get("tiles", [])),
            "projection_window": mosaic_result.get("projection_window"),
        },
    }
    return payload


class EWoodXDesignStreamBridge:
    """
    Optional non-blocking bridge to EWoodXStreamHost.

    - Subscribes to `ewoodx.measurement` to receive live camera measurements.
    - Publishes complete `ewoodx.projector` geometry payloads to drive
      EWoodXProjectorComposer live on the calibrated projector.
    """

    def __init__(
        self,
        agent_id: str = "ewoodx_design_projector_01",
        host: str = STREAM_HOST,
        port: int = CONTROLLER_STREAM_PORT,
        on_measurement: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.host = host
        self.port = int(port)
        self._on_measurement = on_measurement
        # connect() may build a status report while handling an exception.
        # status() reads connected, so a reentrant lock avoids a deadlock.
        self._lock = threading.RLock()
        self._endpoint: StreamEndpointBase | None = None
        self.last_error: str | None = None
        self.published_frames: int = 0
        self.received_measurements: int = 0
        self.last_publish_time: float = 0.0

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._endpoint is not None and self._endpoint.connected

    def connect(self, host: str | None = None, port: int | None = None) -> dict[str, Any]:
        with self._lock:
            if host:
                self.host = host
            if port is not None:
                self.port = int(port)

            if self._endpoint is not None:
                try:
                    self._endpoint.stop()
                except Exception:
                    pass
                self._endpoint = None

            endpoint = StreamEndpointBase(
                agent_id=self.agent_id,
                roles=["design", "controller"],
                host=self.host,
                port=self.port,
                stream_topics=[PROJECTOR],
                on_stream=self._handle_stream_message,
            )
            try:
                endpoint.start(subscribe=[MEASUREMENT])
                self._endpoint = endpoint
                self.last_error = None
            except Exception as exc:
                self.last_error = str(exc)
                self._endpoint = None
                return self.status()

        return self.status()

    def disconnect(self) -> dict[str, Any]:
        with self._lock:
            if self._endpoint is not None:
                # Do not publish {"gh_connected": False}: that marker belongs
                # to the existing Grasshopper producer and would disable GH.
                # Projection source release must be handled by the projector
                # once explicit source-aware arbitration is introduced.
                try:
                    self._endpoint.stop()
                except Exception:
                    pass
                self._endpoint = None
        return self.status()

    def publish_projection(self, payload: dict[str, Any]) -> bool:
        with self._lock:
            if self._endpoint is None or not self._endpoint.connected:
                return False
            try:
                self._endpoint.publish_latest(PROJECTOR, payload)
                self.published_frames += 1
                self.last_publish_time = time.time()
                self.last_error = None
                return True
            except Exception as exc:
                self.last_error = str(exc)
                return False

    def _handle_stream_message(self, message: dict[str, Any]) -> None:
        if message.get("type") != MEASUREMENT:
            return
        payload = message.get("payload")
        if not isinstance(payload, dict):
            return
        self.received_measurements += 1
        if self._on_measurement is not None:
            try:
                prepared = normalize_input_board_json(payload, source_name="ewoodx.measurement (live)")
                self._on_measurement(prepared)
            except Exception as exc:
                self.last_error = f"Error procesando stream de medición: {exc}"

    def status(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "host": self.host,
            "port": self.port,
            "agent_id": self.agent_id,
            "published_frames": self.published_frames,
            "received_measurements": self.received_measurements,
            "last_error": self.last_error,
        }
