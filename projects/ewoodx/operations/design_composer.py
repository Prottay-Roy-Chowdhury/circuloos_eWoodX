"""eWoodX Design Composer: timber-aware design and mosaic coordination.

This operation owns design state, geometry, and optional stream publication.
The browser application is merely one interface to this composer.
"""

from __future__ import annotations

import copy
import json
import math
import threading
from typing import Any, Callable

import cv2
import numpy as np
from pydantic import BaseModel, Field

from projects.ewoodx.config.communication import (
    CONTROLLER_STREAM_PORT,
    STREAM_HOST,
)
from projects.ewoodx.config.sensing import (
    TABLE_HEIGHT_MM,
    TABLE_WIDTH_MM,
)
from projects.ewoodx.operations.design.design_parsers import (
    ParsedDesign,
    parse_design_file,
    vectorize_raster_contours,
)
from projects.ewoodx.operations.design.ewoodx_bridge import (
    EWoodXDesignStreamBridge,
    build_ewoodx_projector_payload,
    extract_board_summary,
    load_latest_runtime_measurement,
    normalize_input_board_json,
)
from projects.ewoodx.operations.design.mosaic_engine import (
    CompletedRegion,
    DesignTransform,
    MosaicConfig,
    MosaicEngine,
    compute_board_edge_fiducials,
    effective_scale,
    reanchor_transform_to_moved_board,
    suggest_next_board_offset,
    suggest_next_board_placement,
    workspace_to_scaled_design,
)
from projects.ewoodx.operations.design.sample_scenarios import (
    generate_sample_assembly_dxf,
    generate_sample_blueprint_pdf,
    generate_sample_fitting_dxf,
    generate_sample_mosaic_dxf,
    generate_sample_sketch_png,
    get_builtin_board_scenarios,
    make_custom_board_measurement,
)
from projects.ewoodx.operations.design.sandbox_runtime import (
    EWoodXSandbox,
)


# ---------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------

class CustomBoardRequest(BaseModel):
    length_mm: float = Field(1200.0, gt=50.0, le=5000.0)
    width_mm: float = Field(800.0, gt=50.0, le=5000.0)
    thickness_mm: float = Field(22.0, ge=0.0, le=500.0)
    angle_deg: float = Field(0.0, ge=-180.0, le=180.0)


class TransformUpdateRequest(BaseModel):
    offset_x_mm: float | None = None
    offset_y_mm: float | None = None
    delta_x_mm: float | None = None
    delta_y_mm: float | None = None
    rotation_deg: float | None = None
    delta_rotation_deg: float | None = None
    scale: float | None = None
    target_width_mm: float | None = None
    target_height_mm: float | None = None
    flip_x: bool | None = None
    flip_y: bool | None = None
    locked_to_board: bool | None = None
    confirm_scale: bool | None = None
    action: str | None = None  # center_on_board | align_top_left | align_board_angle | fit_mosaic_origin | reset


class MosaicUpdateRequest(BaseModel):
    mode: str | None = None
    tile_source: str | None = None
    custom_tile_w_mm: float | None = None
    custom_tile_h_mm: float | None = None
    overlap_mm: float | None = None
    margin_mm: float | None = None
    active_tile_index: int | None = None
    step: int | None = None
    show_registration_marks: bool | None = None
    show_tile_border: bool | None = None
    clip_to_board_in_single: bool | None = None
    skip_empty_tiles: bool | None = None


class ProjectorDisplayRequest(BaseModel):
    show_board_contour: bool | None = None
    show_hud: bool | None = None
    blanked: bool | None = None
    mirror_x: bool | None = None
    mirror_y: bool | None = None
    fine_offset_x_mm: float | None = None
    fine_offset_y_mm: float | None = None
    raster_mode: str | None = None
    raster_opacity: float | None = None
    line_width_px: float | None = None


class LayerUpdateRequest(BaseModel):
    name: str
    visible: bool | None = None
    role: str | None = None
    color: str | None = None


class DxfUnitRequest(BaseModel):
    unit: str


class PdfPageRequest(BaseModel):
    page_index: int


class VectorizeRequest(BaseModel):
    threshold: int = Field(160, ge=10, le=245)
    invert: bool = True
    simplify_mm: float = Field(1.2, ge=0.2, le=20.0)


class StreamConnectRequest(BaseModel):
    host: str = STREAM_HOST
    port: int = CONTROLLER_STREAM_PORT


class WorkspaceTableRequest(BaseModel):
    table_width_mm: float = Field(TABLE_WIDTH_MM, gt=200.0, le=6000.0)
    table_height_mm: float = Field(TABLE_HEIGHT_MM, gt=200.0, le=6000.0)


class SandboxNudgeRequest(BaseModel):
    dx_mm: float = 40.0
    dy_mm: float = 0.0
    d_angle_deg: float = 0.0


class SandboxAutoFeedRequest(BaseModel):
    enabled: bool
    mode: str = "jitter"
    interval_s: float = Field(3.0, ge=0.8, le=30.0)


class PartToggleRequest(BaseModel):
    part_id: str | None = None
    prepared: bool | None = None
    reset: bool = False


class RescanBoardRequest(BaseModel):
    dx_mm: float | None = None
    dy_mm: float | None = None
    d_angle_deg: float | None = None
    auto_project: bool = True
    measurement: dict[str, Any] | None = None


def _rigid_transform_points(
    points: list[list[float]],
    dx: float,
    dy: float,
    d_angle_deg: float,
    cx: float,
    cy: float,
) -> list[list[float]]:
    rad = math.radians(d_angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    out = []
    for p in points:
        rx = p[0] - cx
        ry = p[1] - cy
        nx = cx + rx * cos_a - ry * sin_a + dx
        ny = cy + rx * sin_a + ry * cos_a + dy
        out.append([round(nx, 2), round(ny, 2)])
    return out


def _rigid_shift_measurement(
    measurement: dict[str, Any],
    dx_mm: float,
    dy_mm: float,
    d_angle_deg: float,
) -> dict[str, Any]:
    """Return a copy of an eWoodX measurement rigidly translated & rotated on the table."""
    m = copy.deepcopy(measurement)

    def _shift_poly_or_group(val: Any, cx: float, cy: float) -> Any:
        if not val:
            return val
        first = val[0]
        if isinstance(first, (list, tuple)) and len(first) == 2 and isinstance(first[0], (int, float)):
            return _rigid_transform_points(val, dx_mm, dy_mm, d_angle_deg, cx, cy)
        return [_rigid_transform_points(poly, dx_mm, dy_mm, d_angle_deg, cx, cy) for poly in val]

    def _shift_item(item: dict[str, Any]) -> None:
        raw_c = item.get("contour_mm") or item.get("corners_mm") or []
        if not raw_c:
            return
        flat_pts = raw_c if (isinstance(raw_c[0][0], (int, float))) else [pt for poly in raw_c for pt in poly]
        if not flat_pts:
            return
        cx = sum(p[0] for p in flat_pts) / len(flat_pts)
        cy = sum(p[1] for p in flat_pts) / len(flat_pts)
        if item.get("contour_mm"):
            item["contour_mm"] = _shift_poly_or_group(item["contour_mm"], cx, cy)
        if item.get("corners_mm"):
            item["corners_mm"] = _shift_poly_or_group(item["corners_mm"], cx, cy)
        if item.get("holes_mm"):
            item["holes_mm"] = [
                _rigid_transform_points(h, dx_mm, dy_mm, d_angle_deg, cx, cy) for h in item["holes_mm"]
            ]
        for d in item.get("defects") or []:
            if "x_mm" in d and "y_mm" in d:
                shifted = _rigid_transform_points([[d["x_mm"], d["y_mm"]]], dx_mm, dy_mm, d_angle_deg, cx, cy)[0]
                d["x_mm"], d["y_mm"] = shifted[0], shifted[1]

    if isinstance(m.get("timbers"), list):
        for t in m["timbers"]:
            _shift_item(t)
    else:
        _shift_item(m)
    return m


# ---------------------------------------------------------------------
# Session state manager
# ---------------------------------------------------------------------

class EWoodXDesignComposer:
    """Thread-safe design operation used by a CLI or operator interface."""

    def connect_stream(self, host: str | None = None, port: int | None = None) -> dict[str, Any]:
        """Connect the existing Stream Host; never start a second host."""
        status = self.stream_bridge.connect(host=host, port=port)
        if status["connected"]:
            self.stream_bridge.publish_projection(self.get_ewoodx_payload())
        return status

    def disconnect_stream(self) -> dict[str, Any]:
        """Stop publishing without sending Grasshopper's disconnect marker."""
        return self.stream_bridge.disconnect()

    def stop(self) -> None:
        """Gracefully release the design stream endpoint."""
        self.disconnect_stream()

    def __init__(
        self,
        start_with_test_scenario: str | None = None,
        sandbox: EWoodXSandbox | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self.sandbox = sandbox
        self.table_width_mm: float = float(TABLE_WIDTH_MM)
        self.table_height_mm: float = float(TABLE_HEIGHT_MM)

        self.scenarios = get_builtin_board_scenarios()
        self.measurement: dict[str, Any] = normalize_input_board_json(
            self.scenarios["board_1200x800"]["measurement"],
            source_name="Escenario: Tabla 1,20 × 0,80 m",
        )
        self.board_summary: dict[str, Any] = extract_board_summary(self.measurement)

        self.design: ParsedDesign | None = None
        self.transform = DesignTransform()
        self.mosaic = MosaicConfig(mode="progressive")
        self.completed_regions: list[CompletedRegion] = []
        self.reviewing_region_index: int | None = None
        self._live_backup: dict[str, Any] | None = None
        self.prepared_part_ids: set[str] = set()
        self.last_rescan: dict[str, Any] | None = None
        self.projector_display: dict[str, Any] = {
            "show_board_contour": True,
            "show_hud": True,
            "blanked": False,
            "mirror_x": False,
            "mirror_y": False,
            "fine_offset_x_mm": 0.0,
            "fine_offset_y_mm": 0.0,
            "raster_mode": "invert_high_contrast",
            "raster_opacity": 0.9,
            "line_width_px": 2.5,
        }

        self.revision: int = 0
        self._on_change: Callable[[dict[str, Any]], None] | None = None

        self.stream_bridge = EWoodXDesignStreamBridge(
            on_measurement=self._on_live_stream_measurement,
        )

        # Load startup state
        if start_with_test_scenario:
            self.load_full_test_preset(start_with_test_scenario)
        else:
            # Prefer latest runtime measurement if available, else default 1200x800 scenario
            runtime_meas, runtime_path = load_latest_runtime_measurement()
            if runtime_meas is not None:
                self.measurement = runtime_meas
                self.board_summary = extract_board_summary(self.measurement)
            self.revision = 1

    def set_change_callback(self, callback: Callable[[dict[str, Any]], None] | None) -> None:
        """Optional observer for UI notification; no web-server dependency."""
        self._on_change = callback

    def _board_bounds_tuple(self) -> tuple[float, float, float, float]:
        b = self.board_summary["bounds"]
        return (b["min_x"], b["min_y"], b["max_x"], b["max_y"])

    def _on_live_stream_measurement(self, prepared: dict[str, Any]) -> None:
        with self._lock:
            self._apply_new_measurement_locked(prepared)
        self._notify_change()

    def _apply_new_measurement_locked(self, prepared: dict[str, Any]) -> None:
        prev_id = str(self.board_summary.get("timber_id", ""))
        old_contours = copy.deepcopy(self.board_summary.get("contours_mm") or [])
        old_bounds = self._board_bounds_tuple()

        self.measurement = prepared
        self.board_summary = extract_board_summary(prepared)
        new_id = str(self.board_summary.get("timber_id", ""))

        # Exit history review when a fresh board is scanned
        if self.reviewing_region_index is not None:
            self.reviewing_region_index = None
            self._live_backup = None

        if self.design is not None and self.transform.locked_to_board:
            # Exact SE(2) rigid-body tracking (translation + rotation) when locked to board!
            new_off_x, new_off_y, new_rot, delta_info = reanchor_transform_to_moved_board(
                design=self.design,
                transform=self.transform,
                old_contours_mm=old_contours,
                old_bounds=old_bounds,
                new_contours_mm=self.board_summary.get("contours_mm"),
                new_bounds=self._board_bounds_tuple(),
            )
            self.transform.offset_x_mm = new_off_x
            self.transform.offset_y_mm = new_off_y
            self.transform.rotation_deg = new_rot
            b = self.board_summary["bounds"]
            self.transform.board_rel_x_mm = self.transform.offset_x_mm - b["min_x"]
            self.transform.board_rel_y_mm = self.transform.offset_y_mm - b["min_y"]
            if abs(delta_info["dx_mm"]) > 0.5 or abs(delta_info["dy_mm"]) > 0.5 or abs(delta_info["d_angle_deg"]) > 0.15:
                self.last_rescan = {**delta_info, "prev_contours_mm": old_contours}
        elif (
            self.design is not None
            and self.mosaic.mode == "progressive"
            and new_id != prev_id
        ):
            self.last_rescan = None
            # Square, minimum-waste auto-nesting for any newly scanned reclaimed board!
            off_x, off_y, rot_deg = suggest_next_board_placement(
                design=self.design,
                transform=self.transform,
                board_bounds=self._board_bounds_tuple(),
                completed_regions=self.completed_regions,
                board_contours_mm=self.board_summary.get("contours_mm"),
                overlap_mm=self.mosaic.overlap_mm,
            )
            self.transform.offset_x_mm = off_x
            self.transform.offset_y_mm = off_y
            self.transform.rotation_deg = rot_deg
        else:
            self.last_rescan = None

    def _compute_snapshot_locked(self) -> dict[str, Any]:
        mosaic_result = MosaicEngine.compute(
            design=self.design,
            transform=self.transform,
            board_bounds=self._board_bounds_tuple(),
            table_size_mm=(self.table_width_mm, self.table_height_mm),
            mosaic_cfg=self.mosaic,
            board_contours_mm=self.board_summary.get("contours_mm"),
            completed_regions=self.completed_regions,
            reviewing_region_index=self.reviewing_region_index,
            prepared_part_ids=self.prepared_part_ids,
        )

        # Clamp active_tile_index safely when tile count shrinks
        tiles = mosaic_result["tiles"]
        if tiles and self.mosaic.active_tile_index >= len(tiles):
            self.mosaic.active_tile_index = len(tiles) - 1
            mosaic_result = MosaicEngine.compute(
                design=self.design,
                transform=self.transform,
                board_bounds=self._board_bounds_tuple(),
                table_size_mm=(self.table_width_mm, self.table_height_mm),
                mosaic_cfg=self.mosaic,
                board_contours_mm=self.board_summary.get("contours_mm"),
                completed_regions=self.completed_regions,
                reviewing_region_index=self.reviewing_region_index,
                prepared_part_ids=self.prepared_part_ids,
            )

        ewoodx_payload = build_ewoodx_projector_payload(
            measurement=self.measurement,
            mosaic_result=mosaic_result,
            show_board_contour=bool(self.projector_display.get("show_board_contour", True)),
        )

        return {
            "revision": self.revision,
            "workspace": {
                "table_width_mm": self.table_width_mm,
                "table_height_mm": self.table_height_mm,
            },
            "board": self.board_summary,
            "design": self.design.to_summary_dict() if self.design else None,
            "transform": self.transform.to_dict(),
            "mosaic_config": self.mosaic.to_dict(),
            "mosaic": mosaic_result,
            "projector_display": copy.deepcopy(self.projector_display),
            "stream": self.stream_bridge.status(),
            "sandbox": self.sandbox.status() if self.sandbox is not None else {"enabled": False},
            "rescan": copy.deepcopy(self.last_rescan),
            "ewoodx_payload_stats": {
                "cut_polylines": len(ewoodx_payload["cut_geo"]),
                "mill_polylines": len(ewoodx_payload["mill_geo"]),
                "points": len(ewoodx_payload["points_geo"]),
                "labels": len(ewoodx_payload["labels"]),
                "thickness_mm": ewoodx_payload["thickness_mm"],
            },
        }, ewoodx_payload

    def get_state_snapshot(self) -> dict[str, Any]:
        with self._lock:
            snapshot, _ = self._compute_snapshot_locked()
            return snapshot

    def get_ewoodx_payload(self) -> dict[str, Any]:
        with self._lock:
            _, payload = self._compute_snapshot_locked()
            return payload

    def _notify_change(self) -> dict[str, Any]:
        with self._lock:
            self.revision += 1
            snapshot, payload = self._compute_snapshot_locked()
            if self.stream_bridge.connected and not self.projector_display.get("blanked", False):
                self.stream_bridge.publish_projection(payload)

        callback = self._on_change
        if callback is not None:
            callback(snapshot)
        return snapshot

    # -----------------------------------------------------------------
    # Board actions
    # -----------------------------------------------------------------

    def set_workspace_table(self, width_mm: float, height_mm: float) -> dict[str, Any]:
        with self._lock:
            self.table_width_mm = float(width_mm)
            self.table_height_mm = float(height_mm)
        return self._notify_change()

    def load_board_scenario(self, scenario_id: str) -> dict[str, Any]:
        if scenario_id not in self.scenarios:
            raise KeyError(f"Escenario no encontrado: {scenario_id}")
        sc = self.scenarios[scenario_id]
        prepared = normalize_input_board_json(sc["measurement"], source_name=f"Escenario: {sc['name']}")
        with self._lock:
            if self.sandbox is not None and scenario_id in self.sandbox.scenarios:
                self.sandbox.current_scenario_id = scenario_id
                self.sandbox.current_measurement = copy.deepcopy(sc["measurement"])
            self._apply_new_measurement_locked(prepared)
        return self._notify_change()

    def set_custom_board(self, req: CustomBoardRequest) -> dict[str, Any]:
        raw = make_custom_board_measurement(
            length_mm=req.length_mm,
            width_mm=req.width_mm,
            thickness_mm=req.thickness_mm,
            angle_deg=req.angle_deg,
            center_x_mm=self.table_width_mm * 0.5,
            center_y_mm=self.table_height_mm * 0.5,
            timber_id=f"CUSTOM-{int(req.length_mm)}x{int(req.width_mm)}",
        )
        prepared = normalize_input_board_json(raw, source_name=f"Manual {int(req.length_mm)}×{int(req.width_mm)} mm")
        with self._lock:
            self._apply_new_measurement_locked(prepared)
        return self._notify_change()

    def load_board_json_bytes(self, raw_bytes: bytes, filename: str) -> dict[str, Any]:
        try:
            raw = json.loads(raw_bytes.decode("utf-8"))
        except Exception as exc:
            raise ValueError(f"JSON inválido: {exc}") from exc
        prepared = normalize_input_board_json(raw, source_name=filename)
        with self._lock:
            self._apply_new_measurement_locked(prepared)
        return self._notify_change()

    def load_runtime_board(self) -> tuple[dict[str, Any], str]:
        prepared, path_str = load_latest_runtime_measurement()
        if prepared is None or path_str is None:
            raise FileNotFoundError(
                "No se encontró ningún archivo timber_*_measurement.json en projector_runtime/."
            )
        with self._lock:
            self._apply_new_measurement_locked(prepared)
        return self._notify_change(), path_str

    def rescan_moved_board(self, req: RescanBoardRequest | None = None) -> dict[str, Any]:
        """
        Re-scan an accidentally bumped/moved piece on the workbench, rigidly
        re-anchor the digital drawing (translation + rotation) so every cut line
        stays at the exact same physical millimeter on the timber, and immediately
        re-project onto the board's new table coordinates.
        """
        req = req or RescanBoardRequest()
        with self._lock:
            if self.reviewing_region_index is not None:
                self._restore_live_backup_locked()

            old_contours = copy.deepcopy(self.board_summary.get("contours_mm") or [])
            old_bounds = self._board_bounds_tuple()
            old_b = self.board_summary["bounds"]

            prepared: dict[str, Any] | None = None
            source_mode = "rescan"

            if req.measurement is not None:
                prepared = normalize_input_board_json(req.measurement, source_name="Re-scan JSON")
                source_mode = "payload"
            elif req.dx_mm is not None or req.dy_mm is not None or req.d_angle_deg is not None:
                dx = float(req.dx_mm or 0.0)
                dy = float(req.dy_mm or 0.0)
                dang = float(req.d_angle_deg or 0.0)
                shifted = _rigid_shift_measurement(self.measurement, dx, dy, dang)
                prepared = normalize_input_board_json(shifted, source_name="Re-escanear (movida)")
                if self.sandbox is not None:
                    self.sandbox.current_measurement = copy.deepcopy(shifted)
                source_mode = "simulated"
            else:
                # Try fresh live runtime file if available and actually moved from current board
                runtime_meas, runtime_path = load_latest_runtime_measurement()
                if runtime_meas is not None:
                    rt_sum = extract_board_summary(runtime_meas)
                    rt_b = rt_sum["bounds"]
                    moved_dist = math.hypot(
                        rt_b["center_x"] - old_b["center_x"],
                        rt_b["center_y"] - old_b["center_y"],
                    )
                    ang_diff = abs(((rt_sum["angle_deg"] - self.board_summary["angle_deg"] + 90.0) % 180.0) - 90.0)
                    if moved_dist > 1.0 or ang_diff > 0.25:
                        prepared = runtime_meas
                        source_mode = f"runtime:{runtime_path}"

                if prepared is None:
                    # Offline / Sandbox evaluation fallback: simulate a realistic accidental bump
                    # safely inside the calibrated table bounds so operator can verify rigid tracking!
                    room_right = self.table_width_mm - 35.0 - old_b["max_x"]
                    room_left = old_b["min_x"] - 35.0
                    room_down = self.table_height_mm - 35.0 - old_b["max_y"]
                    room_up = old_b["min_y"] - 35.0

                    dx = min(90.0, max(25.0, room_right * 0.7)) if room_right >= room_left else -min(90.0, max(25.0, room_left * 0.7))
                    dy = -min(45.0, max(15.0, room_up * 0.65)) if room_up >= room_down else min(45.0, max(15.0, room_down * 0.65))
                    dang = 4.2 if self.board_summary["angle_deg"] <= 8.0 else -4.2

                    shifted = _rigid_shift_measurement(self.measurement, dx, dy, dang)
                    prepared = normalize_input_board_json(shifted, source_name="Re-escanear (simulado)")
                    if self.sandbox is not None:
                        self.sandbox.current_measurement = copy.deepcopy(shifted)
                    source_mode = "simulated"

            self.measurement = prepared
            self.board_summary = extract_board_summary(prepared)
            new_contours = self.board_summary.get("contours_mm") or []
            new_bounds = self._board_bounds_tuple()

            delta_info: dict[str, Any] = {
                "dx_mm": 0.0,
                "dy_mm": 0.0,
                "d_angle_deg": 0.0,
                "prev_center_mm": [old_b["center_x"], old_b["center_y"]],
                "new_center_mm": [self.board_summary["bounds"]["center_x"], self.board_summary["bounds"]["center_y"]],
                "size_diff_mm": 0.0,
                "size_match": True,
                "source_mode": source_mode,
                "prev_contours_mm": old_contours,
            }

            if self.design is not None:
                new_off_x, new_off_y, new_rot, d_info = reanchor_transform_to_moved_board(
                    design=self.design,
                    transform=self.transform,
                    old_contours_mm=old_contours,
                    old_bounds=old_bounds,
                    new_contours_mm=new_contours,
                    new_bounds=new_bounds,
                )
                self.transform.offset_x_mm = new_off_x
                self.transform.offset_y_mm = new_off_y
                self.transform.rotation_deg = new_rot
                b = self.board_summary["bounds"]
                self.transform.board_rel_x_mm = self.transform.offset_x_mm - b["min_x"]
                self.transform.board_rel_y_mm = self.transform.offset_y_mm - b["min_y"]
                delta_info = {**d_info, "source_mode": source_mode, "prev_contours_mm": old_contours}

            self.last_rescan = delta_info

            if req.auto_project:
                self.projector_display["blanked"] = False

        snap = self._notify_change()
        # Explicitly publish re-anchored projection payload over EWoodXStreamHost if connected
        stream_sent = False
        if req.auto_project:
            with self._lock:
                if self.stream_bridge.connected:
                    stream_sent = self.stream_bridge.publish_projection(self.get_ewoodx_payload())
        return {
            "rescanned": True,
            "stream_sent": stream_sent,
            "rescan": delta_info,
            "state": snap,
        }

    # -----------------------------------------------------------------
    # Design actions
    # -----------------------------------------------------------------

    def _center_design_on_board_locked(self) -> None:
        if self.design is None:
            return
        b = self.board_summary["bounds"]
        s = effective_scale(self.design, self.transform)
        sw = self.design.base_width_mm * s
        sh = self.design.base_height_mm * s
        self.transform.offset_x_mm = b["center_x"] - sw * 0.5
        self.transform.offset_y_mm = b["center_y"] - sh * 0.5
        if self.transform.locked_to_board:
            self.transform.board_rel_x_mm = self.transform.offset_x_mm - b["min_x"]
            self.transform.board_rel_y_mm = self.transform.offset_y_mm - b["min_y"]

    def _fit_mosaic_origin_locked(self) -> None:
        if self.design is None:
            return
        proj_win = MosaicEngine.resolve_projection_window(
            self._board_bounds_tuple(),
            (self.table_width_mm, self.table_height_mm),
            self.mosaic,
        )
        self.transform.offset_x_mm = proj_win["x0"]
        self.transform.offset_y_mm = proj_win["y0"]
        self.mosaic.active_tile_index = 0
        if self.transform.locked_to_board:
            b = self.board_summary["bounds"]
            self.transform.board_rel_x_mm = self.transform.offset_x_mm - b["min_x"]
            self.transform.board_rel_y_mm = self.transform.offset_y_mm - b["min_y"]

    def load_design_bytes(
        self,
        raw_bytes: bytes,
        filename: str,
        unit_override: str | None = None,
        pdf_page_index: int = 0,
        auto_mosaic_if_large: bool = False,
    ) -> dict[str, Any]:
        parsed = parse_design_file(
            raw_bytes=raw_bytes,
            filename=filename,
            unit_override=unit_override,
            pdf_page_index=pdf_page_index,
        )
        with self._lock:
            self.design = parsed
            self.transform = DesignTransform(scale=1.0, locked_to_board=False)
            self.mosaic.active_tile_index = 0
            self.completed_regions = []
            self.reviewing_region_index = None
            self._live_backup = None
            self.prepared_part_ids = set()
            self.last_rescan = None

            # Center fitting designs on the board; align oversized designs cleanly to top-left
            b = self.board_summary["bounds"]
            exceeds = (
                parsed.base_width_mm > b["width_mm"] + 1.0
                or parsed.base_height_mm > b["height_mm"] + 1.0
            )
            if self.mosaic.mode == "progressive":
                off_x, off_y, rot_deg = suggest_next_board_placement(
                    design=self.design,
                    transform=self.transform,
                    board_bounds=self._board_bounds_tuple(),
                    completed_regions=self.completed_regions,
                    board_contours_mm=self.board_summary.get("contours_mm"),
                    overlap_mm=self.mosaic.overlap_mm,
                )
                self.transform.offset_x_mm = off_x
                self.transform.offset_y_mm = off_y
                self.transform.rotation_deg = rot_deg
            elif auto_mosaic_if_large and exceeds:
                self.mosaic.mode = "mosaic"
                self._fit_mosaic_origin_locked()
            elif exceeds and self.mosaic.mode == "mosaic":
                self._fit_mosaic_origin_locked()
            else:
                if auto_mosaic_if_large and not exceeds:
                    self.mosaic.mode = "single"
                self._center_design_on_board_locked()

        return self._notify_change()

    def load_sample_design(self, sample_id: str) -> dict[str, Any]:
        if sample_id == "panel_fit_dxf":
            return self.load_design_bytes(
                generate_sample_fitting_dxf(),
                "ejemplo_panel_960x620mm.dxf",
                auto_mosaic_if_large=True,
            )
        if sample_id == "mosaic_large_dxf":
            return self.load_design_bytes(
                generate_sample_mosaic_dxf(),
                "ejemplo_mesa_mosaico_2200x1300mm.dxf",
                auto_mosaic_if_large=True,
            )
        if sample_id == "blueprint_pdf":
            return self.load_design_bytes(
                generate_sample_blueprint_pdf(),
                "ejemplo_plano_escala_1a5.pdf",
                auto_mosaic_if_large=False,
            )
        if sample_id == "sketch_png":
            return self.load_design_bytes(
                generate_sample_sketch_png(),
                "ejemplo_plantilla_imagen.png",
                auto_mosaic_if_large=False,
            )
        if sample_id == "assembly_frame_dxf":
            return self.load_design_bytes(
                generate_sample_assembly_dxf(),
                "ejemplo_ensamblaje_bastidor_1600x900mm.dxf",
                auto_mosaic_if_large=False,
            )
        raise KeyError(f"Diseño de prueba no encontrado: {sample_id}")

    def load_full_test_preset(self, preset_id: str) -> dict[str, Any]:
        """One-click end-to-end test presets combining board JSON + design + mode."""
        if preset_id == "progressive_demo":
            self.load_board_scenario("board_1200x800")
            self.mosaic.mode = "progressive"
            self.mosaic.tile_source = "board"
            self.mosaic.overlap_mm = 0.0
            self.mosaic.show_registration_marks = True
            self.load_sample_design("mosaic_large_dxf")
            # Stamp Board #1 (1200x800) so user immediately sees hatched completed region #1,
            # then scan a DIFFERENT reclaimed board (#2: 1100x800 rotated 5.5 deg) auto-squared & nested!
            self.commit_current_board()
            return self.load_board_scenario("board_1100x800_angled")
        if preset_id == "fit_dxf":
            self.load_board_scenario("board_1200x800")
            self.mosaic.mode = "single"
            self.mosaic.tile_source = "board"
            return self.load_sample_design("panel_fit_dxf")
        if preset_id == "mosaic_2x2":
            self.load_board_scenario("board_1200x800")
            self.mosaic.mode = "mosaic"
            self.mosaic.tile_source = "board"
            self.mosaic.overlap_mm = 50.0
            self.mosaic.show_registration_marks = True
            return self.load_sample_design("mosaic_large_dxf")
        if preset_id == "pdf_scale":
            self.load_board_scenario("board_1200x800")
            self.mosaic.mode = "progressive"
            return self.load_sample_design("blueprint_pdf")
        if preset_id == "angled_board":
            self.load_board_scenario("board_1100x800_angled")
            self.mosaic.mode = "single"
            self.load_sample_design("panel_fit_dxf")
            return self.update_transform(TransformUpdateRequest(action="align_board_angle"))
        raise KeyError(f"Preset de prueba desconocido: {preset_id}")

    def set_dxf_units(self, unit: str) -> dict[str, Any]:
        with self._lock:
            if self.design is None or self.design.file_format != "dxf" or self.design.raw_bytes is None:
                raise ValueError("Solo se pueden cambiar las unidades de origen en un diseño DXF cargado.")
            raw = self.design.raw_bytes
            fname = self.design.filename
        return self.load_design_bytes(raw, fname, unit_override=unit)

    def set_pdf_page(self, page_index: int) -> dict[str, Any]:
        with self._lock:
            if self.design is None or self.design.file_format != "pdf" or self.design.raw_bytes is None:
                raise ValueError("No hay un archivo PDF cargado.")
            raw = self.design.raw_bytes
            fname = self.design.filename
            prev_scale = self.transform.scale
        snap = self.load_design_bytes(raw, fname, pdf_page_index=page_index)
        with self._lock:
            self.transform.scale = prev_scale
            if self.design:
                self.design.needs_scale_prompt = False
        return self._notify_change()

    def vectorize_current_raster(self, req: VectorizeRequest) -> dict[str, Any]:
        with self._lock:
            if self.design is None or not self.design.has_raster or self.design.raster_png_bytes is None:
                raise ValueError("No hay ninguna imagen o PDF rasterizado cargado.")
            polys = vectorize_raster_contours(
                png_bytes=self.design.raster_png_bytes,
                base_width_mm=self.design.base_width_mm,
                base_height_mm=self.design.base_height_mm,
                threshold=req.threshold,
                invert=req.invert,
                simplify_mm=req.simplify_mm,
            )
            # Replace previous vectorized contours while keeping native PDF vectors if any
            self.design.polylines = [
                pl for pl in self.design.polylines if pl.get("layer") != "Vectorized_Contours"
            ] + polys
            self.design.layers = [
                ly for ly in self.design.layers if ly.get("name") != "Vectorized_Contours"
            ]
            if polys:
                self.design.layers.append({
                    "name": "Vectorized_Contours",
                    "role": "cut",
                    "color": "#00DCFF",
                    "visible": True,
                    "entity_count": len(polys),
                })
        return self._notify_change()

    def clear_design(self) -> dict[str, Any]:
        with self._lock:
            self.design = None
            self.transform = DesignTransform()
            self.mosaic.active_tile_index = 0
            self.completed_regions = []
            self.reviewing_region_index = None
            self._live_backup = None
            self.prepared_part_ids = set()
            self.last_rescan = None
        return self._notify_change()

    # -----------------------------------------------------------------
    # Progressive Reclaimed-Timber Nesting Actions (Next / Back / Undo)
    # -----------------------------------------------------------------

    def _restore_live_backup_locked(self) -> None:
        if self._live_backup is not None:
            self.measurement = copy.deepcopy(self._live_backup["measurement"])
            self.board_summary = extract_board_summary(self.measurement)
            self.transform = DesignTransform(**self._live_backup["transform"])
            self._live_backup = None
        self.reviewing_region_index = None

    def _enter_review_locked(self, region_index: int) -> None:
        if self.reviewing_region_index is None:
            self._live_backup = {
                "measurement": copy.deepcopy(self.measurement),
                "transform": self.transform.to_dict(),
            }
        reg = self.completed_regions[region_index - 1]
        self.reviewing_region_index = region_index
        if reg.measurement_snapshot:
            self.measurement = copy.deepcopy(reg.measurement_snapshot)
            self.board_summary = extract_board_summary(self.measurement)
        if reg.transform_snapshot:
            self.transform = DesignTransform(**reg.transform_snapshot)

    def commit_current_board(self) -> dict[str, Any]:
        """Stamp the currently scanned board footprint as DONE and auto-nest next area."""
        with self._lock:
            if self.design is None:
                return self.get_state_snapshot()

            if self.reviewing_region_index is not None:
                if self.reviewing_region_index < len(self.completed_regions):
                    self._enter_review_locked(self.reviewing_region_index + 1)
                else:
                    self._restore_live_backup_locked()
                return self._notify_change()

            s = effective_scale(self.design, self.transform)
            scaled_w = self.design.base_width_mm * s
            scaled_h = self.design.base_height_mm * s
            contours = self.board_summary.get("contours_mm") or []
            if contours:
                primary_world = contours[0]
            else:
                bx0, by0, bx1, by1 = self._board_bounds_tuple()
                primary_world = [[bx0, by0], [bx1, by0], [bx1, by1], [bx0, by1]]

            poly_design = [
                workspace_to_scaled_design(p[0], p[1], scaled_w, scaled_h, self.transform)
                for p in primary_world
            ]
            board_num = len(self.completed_regions) + 1
            ov = max(0.0, min(self.mosaic.overlap_mm, 120.0))
            fids = compute_board_edge_fiducials(
                board_poly_design_mm=poly_design,
                scaled_w=scaled_w,
                scaled_h=scaled_h,
                completed_regions=self.completed_regions,
                board_number=board_num,
                inset_mm=max(14.0, min(28.0, ov * 0.5)),
            )

            region = CompletedRegion(
                index=board_num,
                board_id=str(self.board_summary.get("timber_id", f"B{board_num}")),
                board_length_mm=float(self.board_summary.get("length_mm", 0.0)),
                board_width_mm=float(self.board_summary.get("width_mm", 0.0)),
                polygon_design_mm=poly_design,
                fiducials_design_mm=fids,
                transform_snapshot=self.transform.to_dict(),
                measurement_snapshot=copy.deepcopy(self.measurement),
            )
            self.completed_regions.append(region)
            self.last_rescan = None

            # Unlock & auto-position onto next remaining uncovered zone of the drawing!
            self.transform.locked_to_board = False
            off_x, off_y, rot_deg = suggest_next_board_placement(
                design=self.design,
                transform=self.transform,
                board_bounds=self._board_bounds_tuple(),
                completed_regions=self.completed_regions,
                board_contours_mm=self.board_summary.get("contours_mm"),
                overlap_mm=self.mosaic.overlap_mm,
            )
            self.transform.offset_x_mm = off_x
            self.transform.offset_y_mm = off_y
            self.transform.rotation_deg = rot_deg

        return self._notify_change()

    def step_next(self) -> dict[str, Any]:
        with self._lock:
            mode = self.mosaic.mode
        if mode == "progressive":
            return self.commit_current_board()
        return self.update_mosaic(MosaicUpdateRequest(step=1))

    def step_back(self) -> dict[str, Any]:
        with self._lock:
            if self.mosaic.mode != "progressive":
                pass
            elif not self.completed_regions:
                return self.get_state_snapshot()
            elif self.reviewing_region_index is None:
                self._enter_review_locked(len(self.completed_regions))
                return self._notify_change()
            elif self.reviewing_region_index > 1:
                self._enter_review_locked(self.reviewing_region_index - 1)
                return self._notify_change()
            else:
                return self.get_state_snapshot()
        return self.update_mosaic(MosaicUpdateRequest(step=-1))

    def undo_last_region(self) -> dict[str, Any]:
        with self._lock:
            if self.reviewing_region_index is not None:
                self._restore_live_backup_locked()
            if self.completed_regions:
                removed = self.completed_regions.pop()
                if removed.transform_snapshot:
                    self.transform = DesignTransform(**removed.transform_snapshot)
                    self.transform.locked_to_board = False
        return self._notify_change()

    def reset_regions(self) -> dict[str, Any]:
        with self._lock:
            if self.reviewing_region_index is not None:
                self._restore_live_backup_locked()
            self.completed_regions = []
            if self.design is not None:
                if self.mosaic.mode == "progressive":
                    off_x, off_y, rot_deg = suggest_next_board_placement(
                        design=self.design,
                        transform=self.transform,
                        board_bounds=self._board_bounds_tuple(),
                        completed_regions=self.completed_regions,
                        board_contours_mm=self.board_summary.get("contours_mm"),
                        overlap_mm=self.mosaic.overlap_mm,
                    )
                    self.transform.offset_x_mm = off_x
                    self.transform.offset_y_mm = off_y
                    self.transform.rotation_deg = rot_deg
                else:
                    self._fit_mosaic_origin_locked()
        return self._notify_change()

    def auto_nest_current(self) -> dict[str, Any]:
        with self._lock:
            if self.design is None or self.transform.locked_to_board:
                return self.get_state_snapshot()
            off_x, off_y, rot_deg = suggest_next_board_placement(
                design=self.design,
                transform=self.transform,
                board_bounds=self._board_bounds_tuple(),
                completed_regions=self.completed_regions,
                board_contours_mm=self.board_summary.get("contours_mm"),
                overlap_mm=self.mosaic.overlap_mm,
            )
            self.transform.offset_x_mm = off_x
            self.transform.offset_y_mm = off_y
            self.transform.rotation_deg = rot_deg
        return self._notify_change()

    def toggle_part_prepared(self, req: PartToggleRequest) -> dict[str, Any]:
        with self._lock:
            if req.reset:
                self.prepared_part_ids = set()
            elif req.part_id:
                if req.prepared is None:
                    if req.part_id in self.prepared_part_ids:
                        self.prepared_part_ids.remove(req.part_id)
                    else:
                        self.prepared_part_ids.add(req.part_id)
                elif req.prepared:
                    self.prepared_part_ids.add(req.part_id)
                else:
                    self.prepared_part_ids.discard(req.part_id)
        return self._notify_change()

    def build_parts_csv(self) -> bytes:
        snap = self.get_state_snapshot()
        parts = snap["mosaic"].get("parts") or {}
        items = parts.get("items") or []
        groups_by_key = {g["key"]: g["count"] for g in (parts.get("groups") or [])}
        lines = [
            "ID,Capa,Grupo_Cantidad,Largo_OBB_mm,Ancho_OBB_mm,Angulo_deg,AABB_X_mm,AABB_Y_mm,Perimetro_mm,Preparada"
        ]
        for it in items:
            gcount = groups_by_key.get(it["group_key"], 1)
            prep_str = "SI" if it.get("prepared") else "NO"
            layer_clean = str(it.get("layer", "")).replace(",", ";")
            lines.append(
                f'{it["id"]},{layer_clean},{gcount},{it["length_mm"]},{it["width_mm"]},'
                f'{it["angle_deg"]},{it["aabb_w_mm"]},{it["aabb_h_mm"]},{it["perimeter_mm"]},{prep_str}'
            )
        return ("\ufeff" + "\n".join(lines) + "\n").encode("utf-8")

    def update_layer(self, req: LayerUpdateRequest) -> dict[str, Any]:
        with self._lock:
            if self.design is None:
                raise ValueError("No hay diseño cargado.")
            for layer in self.design.layers:
                if layer["name"] == req.name:
                    if req.visible is not None:
                        layer["visible"] = bool(req.visible)
                    if req.role in ("cut", "mill", "points", "reference"):
                        layer["role"] = req.role
                    if req.color:
                        layer["color"] = req.color
                    break
        return self._notify_change()

    # -----------------------------------------------------------------
    # Transform & Locking actions
    # -----------------------------------------------------------------

    def update_transform(self, req: TransformUpdateRequest) -> dict[str, Any]:
        with self._lock:
            if self.design is None:
                return self.get_state_snapshot()

            # Allow toggling lock first
            if req.locked_to_board is not None:
                self.transform.locked_to_board = bool(req.locked_to_board)
                if self.transform.locked_to_board:
                    b = self.board_summary["bounds"]
                    self.transform.board_rel_x_mm = self.transform.offset_x_mm - b["min_x"]
                    self.transform.board_rel_y_mm = self.transform.offset_y_mm - b["min_y"]

            # Scale changes are STRICTLY FORBIDDEN for DXF (scale_locked=True)
            if not self.design.scale_locked:
                prev_scale = self.transform.scale
                if req.scale is not None and req.scale > 0:
                    self.transform.scale = max(0.005, min(float(req.scale), 500.0))
                    self.design.needs_scale_prompt = False
                elif req.target_width_mm is not None and req.target_width_mm > 0:
                    self.transform.scale = max(
                        0.005,
                        min(float(req.target_width_mm) / max(self.design.base_width_mm, 1e-6), 500.0),
                    )
                    self.design.needs_scale_prompt = False
                elif req.target_height_mm is not None and req.target_height_mm > 0:
                    self.transform.scale = max(
                        0.005,
                        min(float(req.target_height_mm) / max(self.design.base_height_mm, 1e-6), 500.0),
                    )
                    self.design.needs_scale_prompt = False
                if abs(self.transform.scale - prev_scale) > 1e-6:
                    self.completed_regions = []
                    self.reviewing_region_index = None
                    self._live_backup = None
                if req.confirm_scale:
                    self.design.needs_scale_prompt = False
            else:
                self.transform.scale = 1.0

            # Position/rotation edits only allowed when NOT locked to board
            if not self.transform.locked_to_board:
                if any(
                    v is not None
                    for v in (
                        req.offset_x_mm,
                        req.offset_y_mm,
                        req.delta_x_mm,
                        req.delta_y_mm,
                        req.rotation_deg,
                        req.delta_rotation_deg,
                        req.action,
                    )
                ):
                    self.last_rescan = None
                if req.offset_x_mm is not None:
                    self.transform.offset_x_mm = float(req.offset_x_mm)
                if req.offset_y_mm is not None:
                    self.transform.offset_y_mm = float(req.offset_y_mm)
                if req.delta_x_mm is not None:
                    self.transform.offset_x_mm += float(req.delta_x_mm)
                if req.delta_y_mm is not None:
                    self.transform.offset_y_mm += float(req.delta_y_mm)
                if req.rotation_deg is not None:
                    self.transform.rotation_deg = float(req.rotation_deg) % 360.0
                if req.delta_rotation_deg is not None:
                    self.transform.rotation_deg = (self.transform.rotation_deg + float(req.delta_rotation_deg)) % 360.0
                if req.flip_x is not None:
                    self.transform.flip_x = bool(req.flip_x)
                if req.flip_y is not None:
                    self.transform.flip_y = bool(req.flip_y)

                if req.action == "center_on_board":
                    self._center_design_on_board_locked()
                elif req.action == "align_top_left":
                    b = self.board_summary["bounds"]
                    self.transform.offset_x_mm = b["min_x"] + self.mosaic.margin_mm
                    self.transform.offset_y_mm = b["min_y"] + self.mosaic.margin_mm
                elif req.action == "align_board_angle":
                    self.transform.rotation_deg = self.board_summary["angle_deg"]
                    self._center_design_on_board_locked()
                elif req.action == "fit_mosaic_origin":
                    self._fit_mosaic_origin_locked()
                elif req.action == "reset":
                    self.transform.rotation_deg = 0.0
                    self.transform.flip_x = False
                    self.transform.flip_y = False
                    if not self.design.scale_locked:
                        self.transform.scale = 1.0
                    self._center_design_on_board_locked()

        return self._notify_change()

    # -----------------------------------------------------------------
    # Mosaic & Projector Display actions
    # -----------------------------------------------------------------

    def update_mosaic(self, req: MosaicUpdateRequest) -> dict[str, Any]:
        with self._lock:
            prev_mode = self.mosaic.mode
            if req.mode in ("progressive", "single", "mosaic"):
                self.mosaic.mode = req.mode
            if req.tile_source in ("board", "table", "custom"):
                self.mosaic.tile_source = req.tile_source
            if req.custom_tile_w_mm is not None:
                self.mosaic.custom_tile_w_mm = max(50.0, float(req.custom_tile_w_mm))
            if req.custom_tile_h_mm is not None:
                self.mosaic.custom_tile_h_mm = max(50.0, float(req.custom_tile_h_mm))
            if req.overlap_mm is not None:
                self.mosaic.overlap_mm = max(0.0, min(500.0, float(req.overlap_mm)))
            if req.margin_mm is not None:
                self.mosaic.margin_mm = max(0.0, min(300.0, float(req.margin_mm)))
            if req.show_registration_marks is not None:
                self.mosaic.show_registration_marks = bool(req.show_registration_marks)
            if req.show_tile_border is not None:
                self.mosaic.show_tile_border = bool(req.show_tile_border)
            if req.clip_to_board_in_single is not None:
                self.mosaic.clip_to_board_in_single = bool(req.clip_to_board_in_single)
            if req.skip_empty_tiles is not None:
                self.mosaic.skip_empty_tiles = bool(req.skip_empty_tiles)

            # When entering mosaic mode cleanly, reset to tile 0
            if prev_mode != "mosaic" and self.mosaic.mode == "mosaic":
                self.mosaic.active_tile_index = 0

            if req.active_tile_index is not None:
                self.mosaic.active_tile_index = max(0, int(req.active_tile_index))
            elif req.step is not None:
                # Step wraps cleanly across available tiles
                snapshot, _ = self._compute_snapshot_locked()
                total = max(1, len(snapshot["mosaic"]["tiles"]))
                self.mosaic.active_tile_index = (self.mosaic.active_tile_index + int(req.step)) % total

        return self._notify_change()

    def update_projector_display(self, req: ProjectorDisplayRequest) -> dict[str, Any]:
        with self._lock:
            for field_name in (
                "show_board_contour",
                "show_hud",
                "blanked",
                "mirror_x",
                "mirror_y",
                "fine_offset_x_mm",
                "fine_offset_y_mm",
                "raster_mode",
                "raster_opacity",
                "line_width_px",
            ):
                val = getattr(req, field_name)
                if val is not None:
                    self.projector_display[field_name] = val
        return self._notify_change()

    def get_processed_raster_png(self, mode: str = "original") -> bytes:
        with self._lock:
            if self.design is None or not self.design.has_raster or self.design.raster_png_bytes is None:
                raise FileNotFoundError("No hay imagen rasterizada disponible.")
            raw_png = self.design.raster_png_bytes

        if mode == "original":
            return raw_png

        arr = np.frombuffer(raw_png, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
        if img is None:
            return raw_png

        if img.ndim == 2:
            gray = img
        elif img.shape[2] == 4:
            # Composite transparent background over white before inverting
            alpha = img[:, :, 3:4].astype(np.float32) / 255.0
            bgr = img[:, :, :3].astype(np.float32)
            comp = (bgr * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
            gray = cv2.cvtColor(comp, cv2.COLOR_BGR2GRAY)
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if mode == "binary_white":
            _, mask = cv2.threshold(gray, 185, 255, cv2.THRESH_BINARY_INV)
            out = np.zeros((gray.shape[0], gray.shape[1], 4), dtype=np.uint8)
            out[:, :, 0] = 255
            out[:, :, 1] = 255
            out[:, :, 2] = 255
            out[:, :, 3] = mask
        else:
            # invert_high_contrast: dark lines on light paper become luminous white/cyan on black
            inv = 255 - gray
            inv = np.clip((inv.astype(np.float32) - 25.0) * 1.45, 0, 255).astype(np.uint8)
            out = np.zeros((gray.shape[0], gray.shape[1], 4), dtype=np.uint8)
            out[:, :, 0] = inv
            out[:, :, 1] = inv
            out[:, :, 2] = inv
            out[:, :, 3] = inv

        ok, encoded = cv2.imencode(".png", out)
        return encoded.tobytes() if ok else raw_png

