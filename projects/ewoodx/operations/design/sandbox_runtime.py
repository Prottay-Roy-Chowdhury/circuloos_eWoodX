"""
Full Offline Sandbox Runtime for eWoodX Design-to-Projection Middleware.

Spins up the ENTIRE eWoodX streaming loop locally with simulated hardware so
the operator can test and evaluate the complete pipeline without a physical
camera or ceiling projector:

  Simulated Camera (SensingStreamService)
          │  ewoodx.measurement (JSON)
          ▼
  Real EWoodXStreamHost (TCP broker)
          │  ewoodx.measurement ──► Design-to-Projection App
          │  ewoodx.projector   ◄── Design-to-Projection App
          ▼
  Simulated Projector Receiver (ProjectorStreamService)
          │
          ▼
  Real eWoodX ProjectorGeometry + ProjectorRenderer (OpenCV 1280x800)
"""

from __future__ import annotations

import copy
import math
import random
import socket
import threading
import time
from typing import Any

import cv2
import numpy as np

from projects.ewoodx.config.projection import (
    PROJECTOR_HEIGHT,
    PROJECTOR_HEIGHT_MM,
    PROJECTOR_POS_X_MM,
    PROJECTOR_POS_Y_MM,
    PROJECTOR_WIDTH,
)
from projects.ewoodx.config.sensing import (
    TABLE_HEIGHT_MM,
    TABLE_WIDTH_MM,
)
from projects.ewoodx.operations.design.sample_scenarios import (
    get_builtin_board_scenarios,
)
from projects.ewoodx.operations.projection.projector_geometry import (
    ProjectorGeometry,
)
from projects.ewoodx.operations.projection.projector_renderer import (
    ProjectorRenderer,
)
from projects.ewoodx.operations.streaming.projector_stream_service import (
    ProjectorStreamService,
)
from projects.ewoodx.operations.streaming.sensing_stream_service import (
    SensingStreamService,
)
from projects.ewoodx.operations.streaming.stream_host import (
    EWoodXStreamHost,
)


def _find_free_port_triplet(base_port: int = 6201) -> tuple[int, int, int]:
    """Return (sensing_port, projector_port, controller_port) that are free."""
    candidates = [base_port, 16201, 26201, 36201]
    for start in candidates:
        ports = (start, start + 1, start + 2)
        sockets = []
        ok = True
        for port in ports:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                sockets.append(s)
            except OSError:
                ok = False
                break
        for s in sockets:
            s.close()
        if ok:
            return ports
    return (16201, 16202, 16203)


def _build_simulated_homography() -> np.ndarray:
    """
    Build a calibrated world-mm (TABLE_WIDTH_MM x TABLE_HEIGHT_MM) ->
    projector-pixel (PROJECTOR_WIDTH x PROJECTOR_HEIGHT) homography with padding.
    """
    pad_x = 40.0
    pad_y = 40.0
    usable_w = max(100.0, float(PROJECTOR_WIDTH) - 2.0 * pad_x)
    usable_h = max(100.0, float(PROJECTOR_HEIGHT) - 2.0 * pad_y - 36.0)
    scale = min(usable_w / TABLE_WIDTH_MM, usable_h / TABLE_HEIGHT_MM)
    ox = (PROJECTOR_WIDTH - TABLE_WIDTH_MM * scale) * 0.5
    oy = (PROJECTOR_HEIGHT - 36.0 - TABLE_HEIGHT_MM * scale) * 0.5
    return np.array(
        [
            [scale, 0.0, ox],
            [0.0, scale, oy],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )


def _transform_points_2d(
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


class EWoodXSandbox:
    """Self-contained local sandbox simulating camera JSON input and eWoodX OpenCV projector."""

    def __init__(self, preferred_base_port: int = 6201) -> None:
        self._lock = threading.RLock()
        self.sensing_port, self.projector_port, self.controller_port = _find_free_port_triplet(
            preferred_base_port
        )
        self.host_addr = "127.0.0.1"
        self.running = False

        self.scenarios = get_builtin_board_scenarios()
        self.scenario_order = list(self.scenarios.keys())
        self.current_scenario_id = "board_1200x800"
        self.current_measurement = copy.deepcopy(
            self.scenarios[self.current_scenario_id]["measurement"]
        )

        # Real eWoodX streaming components
        self.stream_host: EWoodXStreamHost | None = None
        self.camera_service: SensingStreamService | None = None
        self.projector_service: ProjectorStreamService | None = None

        # Real eWoodX OpenCV renderer receiving ewoodx.projector packets
        self.projector_geometry = ProjectorGeometry(
            homography=_build_simulated_homography(),
            projector_height_mm=PROJECTOR_HEIGHT_MM,
            projector_pos_x_mm=PROJECTOR_POS_X_MM,
            projector_pos_y_mm=PROJECTOR_POS_Y_MM,
        )
        self.projector_renderer = ProjectorRenderer(geometry=self.projector_geometry)
        self.projector_renderer.show_hud = True

        self.camera_frames_sent = 0
        self.projector_frames_received = 0
        self.latest_projector_payload: dict[str, Any] | None = None
        self.latest_rendered_jpeg: bytes | None = None
        self.last_event: str = "Sandbox inicializado"

        # Auto-feed camera simulation thread
        self.auto_feed_enabled = False
        self.auto_feed_mode = "jitter"  # "jitter" | "cycle"
        self.auto_feed_interval_s = 3.0
        self._cycle_idx = 0
        self._stop_event = threading.Event()
        self._auto_thread: threading.Thread | None = None

    def start(self) -> None:
        with self._lock:
            if self.running:
                return

            self.stream_host = EWoodXStreamHost(
                host=self.host_addr,
                sensing_port=self.sensing_port,
                projector_port=self.projector_port,
                controller_port=self.controller_port,
            )
            self.stream_host.start()

            self.camera_service = SensingStreamService(
                agent_id="sandbox_camera_01",
                host=self.host_addr,
                port=self.sensing_port,
            )
            self.camera_service.start()

            self.projector_service = ProjectorStreamService(
                agent_id="sandbox_projector_01",
                host=self.host_addr,
                port=self.projector_port,
                on_stream=self._on_projector_stream,
            )
            self.projector_service.start()

            self.running = True
            self._stop_event.clear()
            self._auto_thread = threading.Thread(
                target=self._auto_feed_loop,
                name="sandbox-camera-autofeed",
                daemon=True,
            )
            self._auto_thread.start()
            self.last_event = (
                f"StreamHost activo (puertos {self.sensing_port}/{self.projector_port}/{self.controller_port})"
            )

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            self.running = False
            self.auto_feed_enabled = False
            for svc in (self.camera_service, self.projector_service, self.stream_host):
                if svc is not None:
                    try:
                        svc.stop()
                    except Exception:
                        pass
            self.camera_service = None
            self.projector_service = None
            self.stream_host = None

    def _on_projector_stream(self, message: dict[str, Any]) -> None:
        msg_type = message.get("type")
        payload = message.get("payload")
        if not isinstance(payload, dict):
            return

        with self._lock:
            if msg_type == "ewoodx.projector":
                if payload.get("gh_connected") is False:
                    return
                self.projector_frames_received += 1
                self.latest_projector_payload = copy.deepcopy(payload)
                self._render_opencv_frame_locked(payload, is_connected=True)
            elif msg_type == "ewoodx.measurement" and self.latest_projector_payload is None:
                prepared = ProjectorGeometry.prepare_measurement(payload)
                self._render_opencv_frame_locked(prepared, is_connected=False)

    def _render_opencv_frame_locked(self, data: dict[str, Any], is_connected: bool) -> None:
        thickness = float(data.get("thickness_mm", data.get("timber_thickness_mm", 0.0)) or 0.0)
        frame = self.projector_renderer.render(
            data=data,
            is_connected=is_connected,
            packet_count=self.projector_frames_received,
            thickness_mm=thickness,
        )
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        if ok:
            self.latest_rendered_jpeg = buf.tobytes()

    def get_opencv_frame_jpeg(self, fallback_payload: dict[str, Any] | None = None) -> bytes:
        with self._lock:
            if self.latest_rendered_jpeg is not None:
                return self.latest_rendered_jpeg
            if fallback_payload is not None:
                self._render_opencv_frame_locked(fallback_payload, is_connected=True)
                if self.latest_rendered_jpeg is not None:
                    return self.latest_rendered_jpeg

            blank = np.zeros((PROJECTOR_HEIGHT, PROJECTOR_WIDTH, 3), dtype=np.uint8)
            cv2.putText(
                blank,
                "eWoodX Sandbox Projector - esperando stream...",
                (40, PROJECTOR_HEIGHT // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (180, 180, 180),
                2,
                cv2.LINE_AA,
            )
            _, buf = cv2.imencode(".jpg", blank)
            return buf.tobytes()

    # -----------------------------------------------------------------
    # Simulated Camera Input Actions
    # -----------------------------------------------------------------

    def emit_scenario(self, scenario_id: str) -> dict[str, Any]:
        if scenario_id not in self.scenarios:
            raise KeyError(f"Escenario de cámara desconocido: {scenario_id}")
        with self._lock:
            self.current_scenario_id = scenario_id
            self.current_measurement = copy.deepcopy(self.scenarios[scenario_id]["measurement"])
            self._publish_camera_locked(self.current_measurement)
            self.last_event = f"Cámara simulada envió: {self.scenarios[scenario_id]['name']}"
            return self.status()

    def nudge_current_board(
        self,
        dx_mm: float = 0.0,
        dy_mm: float = 0.0,
        d_angle_deg: float = 0.0,
    ) -> dict[str, Any]:
        """Simulate physically sliding or rotating the wooden board on the table."""
        with self._lock:
            m = copy.deepcopy(self.current_measurement)

            def shift_single(item: dict[str, Any]) -> None:
                pts = item.get("contour_mm") or item.get("corners_mm") or []
                if not pts:
                    return
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                if item.get("contour_mm"):
                    item["contour_mm"] = _transform_points_2d(
                        item["contour_mm"], dx_mm, dy_mm, d_angle_deg, cx, cy
                    )
                if item.get("corners_mm"):
                    item["corners_mm"] = _transform_points_2d(
                        item["corners_mm"], dx_mm, dy_mm, d_angle_deg, cx, cy
                    )
                if item.get("holes_mm"):
                    item["holes_mm"] = [
                        _transform_points_2d(h, dx_mm, dy_mm, d_angle_deg, cx, cy)
                        for h in item["holes_mm"]
                    ]
                for d in item.get("defects") or []:
                    if "x_mm" in d and "y_mm" in d:
                        shifted = _transform_points_2d(
                            [[d["x_mm"], d["y_mm"]]], dx_mm, dy_mm, d_angle_deg, cx, cy
                        )[0]
                        d["x_mm"], d["y_mm"] = shifted[0], shifted[1]

            if isinstance(m.get("timbers"), list):
                for t in m["timbers"]:
                    shift_single(t)
            else:
                shift_single(m)

            self.current_measurement = m
            self._publish_camera_locked(self.current_measurement)
            self.last_event = (
                f"Tabla movida en mesa: dX={dx_mm:+.0f} mm, dY={dy_mm:+.0f} mm, dAng={d_angle_deg:+.1f}°"
            )
            return self.status()

    def set_auto_feed(
        self,
        enabled: bool,
        mode: str = "jitter",
        interval_s: float = 3.0,
    ) -> dict[str, Any]:
        with self._lock:
            self.auto_feed_enabled = bool(enabled)
            if mode in ("jitter", "cycle"):
                self.auto_feed_mode = mode
            self.auto_feed_interval_s = max(0.8, min(float(interval_s), 30.0))
            self.last_event = (
                f"Stream automático cámara: {'ACTIVO' if self.auto_feed_enabled else 'PAUSADO'} "
                f"({self.auto_feed_mode}, cada {self.auto_feed_interval_s:.1f}s)"
            )
            return self.status()

    def _publish_camera_locked(self, measurement: dict[str, Any]) -> None:
        if self.camera_service is None or not self.camera_service.connected:
            return
        self.camera_frames_sent += 1
        self.camera_service.publish_measurement(
            measurement,
            frame_id=self.camera_frames_sent,
            valid=True,
        )

    def _auto_feed_loop(self) -> None:
        while not self._stop_event.is_set():
            interval = self.auto_feed_interval_s
            if self._stop_event.wait(timeout=interval):
                break
            with self._lock:
                if not self.running or not self.auto_feed_enabled:
                    continue
                if self.auto_feed_mode == "cycle":
                    self._cycle_idx = (self._cycle_idx + 1) % len(self.scenario_order)
                    sid = self.scenario_order[self._cycle_idx]
                    self.current_scenario_id = sid
                    self.current_measurement = copy.deepcopy(self.scenarios[sid]["measurement"])
                    self._publish_camera_locked(self.current_measurement)
                    self.last_event = f"Auto-ciclo cámara -> {self.scenarios[sid]['name']}"
                else:
                    # Realistic sensor micro-jitter (+/- 1.5 mm)
                    jx = random.uniform(-1.5, 1.5)
                    jy = random.uniform(-1.5, 1.5)
                    jittered = copy.deepcopy(self.current_measurement)
                    if not isinstance(jittered.get("timbers"), list):
                        for key in ("contour_mm", "corners_mm"):
                            if jittered.get(key):
                                jittered[key] = [
                                    [round(p[0] + jx, 2), round(p[1] + jy, 2)]
                                    for p in jittered[key]
                                ]
                    self._publish_camera_locked(jittered)
                    self.last_event = f"Auto-captura cámara #{self.camera_frames_sent} (jitter {jx:+.1f}, {jy:+.1f} mm)"

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": True,
                "running": self.running,
                "host": self.host_addr,
                "sensing_port": self.sensing_port,
                "projector_port": self.projector_port,
                "controller_port": self.controller_port,
                "current_scenario_id": self.current_scenario_id,
                "camera_frames_sent": self.camera_frames_sent,
                "projector_frames_received": self.projector_frames_received,
                "auto_feed_enabled": self.auto_feed_enabled,
                "auto_feed_mode": self.auto_feed_mode,
                "auto_feed_interval_s": self.auto_feed_interval_s,
                "last_event": self.last_event,
            }
