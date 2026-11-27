
"""FastAPI interface for the independent eWoodX Design Composer."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from projects.ewoodx.operations.design_composer import (
    CustomBoardRequest,
    DxfUnitRequest,
    EWoodXDesignComposer,
    LayerUpdateRequest,
    MosaicUpdateRequest,
    PartToggleRequest,
    PdfPageRequest,
    ProjectorDisplayRequest,
    RescanBoardRequest,
    SandboxAutoFeedRequest,
    SandboxNudgeRequest,
    StreamConnectRequest,
    TransformUpdateRequest,
    VectorizeRequest,
    WorkspaceTableRequest,
)
from projects.ewoodx.operations.design.sandbox_runtime import EWoodXSandbox

STATIC_DIR = Path(__file__).resolve().parent / "static"

# ---------------------------------------------------------------------
# FastAPI application factory
# ---------------------------------------------------------------------

def create_app(
    start_with_test_scenario: str | None = None,
    enable_sandbox: bool = False,
) -> FastAPI:
    app = FastAPI(
        title="eWoodX Design-to-Projection Middleware",
        version="1.0.0",
    )
    sandbox: EWoodXSandbox | None = EWoodXSandbox() if enable_sandbox else None
    if sandbox is not None:
        sandbox.start()
        if start_with_test_scenario is None:
            start_with_test_scenario = "progressive_demo"

    session = EWoodXDesignComposer(
        start_with_test_scenario=start_with_test_scenario,
        sandbox=sandbox,
    )
    app.state.session = session
    app.state.sandbox = sandbox

    if sandbox is not None:
        # Auto-connect middleware to the local sandbox EWoodXStreamHost
        session.connect_stream(
            host=sandbox.host_addr,
            port=sandbox.controller_port,
        )

    ws_clients: set[WebSocket] = set()
    event_loop: asyncio.AbstractEventLoop | None = None

    async def broadcast_state(snapshot: dict) -> None:
        message = json.dumps({"type": "state", "data": snapshot})
        for ws in list(ws_clients):
            try:
                await ws.send_text(message)
            except Exception:
                ws_clients.discard(ws)

    def on_composer_change(snapshot: dict) -> None:
        if event_loop is not None and event_loop.is_running() and ws_clients:
            asyncio.run_coroutine_threadsafe(broadcast_state(snapshot), event_loop)

    session.set_change_callback(on_composer_change)

    @app.on_event("startup")
    async def _on_startup() -> None:
        nonlocal event_loop
        event_loop = asyncio.get_running_loop()

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:
        session.stop()
        if sandbox is not None:
            sandbox.stop()

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def index_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/projector")
    async def projector_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "projector.html")

    @app.get("/api/state")
    async def get_state() -> JSONResponse:
        return JSONResponse(session.get_state_snapshot())

    @app.get("/api/scenarios")
    async def list_scenarios() -> JSONResponse:
        boards = [
            {"id": sc["id"], "name": sc["name"], "description": sc["description"]}
            for sc in session.scenarios.values()
        ]
        designs = [
            {
                "id": "panel_fit_dxf",
                "name": "DXF 1:1 — Panel mueble (960 × 620 mm)",
                "description": "Cabe en la tabla 1,20 × 0,80 m. Incluye capas CUT, MILL y DRILL.",
            },
            {
                "id": "mosaic_large_dxf",
                "name": "DXF 1:1 — Mesa curva grande (2200 × 1300 mm)",
                "description": "Supera la tabla para probar el Mosaico 2×2 con marcas de registro.",
            },
            {
                "id": "blueprint_pdf",
                "name": "PDF — Plano técnico A4 (escala 1:5 o 1:1)",
                "description": "Permite proyectar a 1:1 real o aplicar factor de escala.",
            },
            {
                "id": "sketch_png",
                "name": "IMG — Plantilla carpintería (PNG escalable)",
                "description": "Imagen sin escala física que solicita ancho/alto real en mm.",
            },
        ]
        presets = [
            {
                "id": "progressive_demo",
                "name": "Nesting Progresivo — Tablas distintas (Recomendado)",
                "description": "Tabla #1 (1200×800) completada + Tabla #2 (1100×800 5.5°) auto-anidada.",
            },
            {
                "id": "mosaic_2x2",
                "name": "Escenario Mosaico 2×2 (Recomendado)",
                "description": "Tabla 1,20 × 0,80 m + DXF 1:1 de 2,20 × 1,30 m dividido en 4 baldosas.",
            },
            {
                "id": "fit_dxf",
                "name": "Escenario Encaje Directo DXF 1:1",
                "description": "Tabla 1,20 × 0,80 m + Panel DXF 960 × 620 mm para panear y fijar.",
            },
            {
                "id": "angled_board",
                "name": "Escenario Tabla Inclinada 1,10 × 0,80 m",
                "description": "Tabla con rotación 5.5°, agujero y nudos + alineación automática.",
            },
            {
                "id": "pdf_scale",
                "name": "Escenario Plano PDF con Escala",
                "description": "Tabla 1,20 × 0,80 m + PDF A4 que solicita factor de escala.",
            },
        ]
        return JSONResponse({"boards": boards, "designs": designs, "presets": presets})

    @app.post("/api/workspace/table")
    async def set_workspace_table(req: WorkspaceTableRequest) -> JSONResponse:
        return JSONResponse(session.set_workspace_table(req.table_width_mm, req.table_height_mm))

    @app.post("/api/preset/{preset_id}")
    async def run_test_preset(preset_id: str) -> JSONResponse:
        try:
            return JSONResponse(session.load_full_test_preset(preset_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/board/scenario/{scenario_id}")
    async def load_board_scenario(scenario_id: str) -> JSONResponse:
        try:
            return JSONResponse(session.load_board_scenario(scenario_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/board/custom")
    async def set_custom_board(req: CustomBoardRequest) -> JSONResponse:
        return JSONResponse(session.set_custom_board(req))

    @app.post("/api/board/upload")
    async def upload_board_json(file: UploadFile = File(...)) -> JSONResponse:
        raw = await file.read()
        try:
            return JSONResponse(session.load_board_json_bytes(raw, file.filename or "board.json"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/board/load-runtime")
    async def load_runtime_board() -> JSONResponse:
        try:
            snap, path_str = session.load_runtime_board()
            return JSONResponse({"state": snap, "loaded_path": path_str})
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/design/upload")
    async def upload_design(
        file: UploadFile = File(...),
        unit_override: str | None = Form(None),
    ) -> JSONResponse:
        raw = await file.read()
        try:
            return JSONResponse(
                session.load_design_bytes(
                    raw_bytes=raw,
                    filename=file.filename or "design.dxf",
                    unit_override=unit_override,
                    auto_mosaic_if_large=True,
                )
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/design/sample/{sample_id}")
    async def load_sample_design(sample_id: str) -> JSONResponse:
        try:
            return JSONResponse(session.load_sample_design(sample_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/design/dxf-units")
    async def set_dxf_units(req: DxfUnitRequest) -> JSONResponse:
        try:
            return JSONResponse(session.set_dxf_units(req.unit))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/design/pdf-page")
    async def set_pdf_page(req: PdfPageRequest) -> JSONResponse:
        try:
            return JSONResponse(session.set_pdf_page(req.page_index))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/design/vectorize")
    async def vectorize_raster(req: VectorizeRequest) -> JSONResponse:
        try:
            return JSONResponse(session.vectorize_current_raster(req))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/design/clear")
    async def clear_design() -> JSONResponse:
        return JSONResponse(session.clear_design())

    @app.post("/api/design/layer")
    async def update_layer(req: LayerUpdateRequest) -> JSONResponse:
        try:
            return JSONResponse(session.update_layer(req))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/design/raster")
    async def get_design_raster(mode: str = Query("original")) -> Response:
        try:
            png = session.get_processed_raster_png(mode=mode)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.post("/api/transform")
    async def update_transform(req: TransformUpdateRequest) -> JSONResponse:
        return JSONResponse(session.update_transform(req))

    @app.post("/api/mosaic")
    async def update_mosaic(req: MosaicUpdateRequest) -> JSONResponse:
        return JSONResponse(session.update_mosaic(req))

    @app.post("/api/projector/display")
    async def update_projector_display(req: ProjectorDisplayRequest) -> JSONResponse:
        return JSONResponse(session.update_projector_display(req))

    @app.post("/api/stream/connect")
    async def connect_stream(req: StreamConnectRequest) -> JSONResponse:
        status = session.connect_stream(host=req.host, port=req.port)
        snap = session._notify_change()
        return JSONResponse({"stream": status, "state": snap})

    @app.post("/api/stream/disconnect")
    async def disconnect_stream() -> JSONResponse:
        status = session.disconnect_stream()
        snap = session._notify_change()
        return JSONResponse({"stream": status, "state": snap})

    @app.get("/api/export/projector-json")
    async def export_projector_json() -> Response:
        payload = session.get_ewoodx_payload()
        data = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        return Response(
            content=data,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="ewoodx_projector_payload.json"'},
        )

    @app.get("/api/export/board-json")
    async def export_board_json() -> Response:
        with session._lock:
            data = json.dumps(session.measurement, indent=2, ensure_ascii=False).encode("utf-8")
        return Response(
            content=data,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="timber_measurement.json"'},
        )

    @app.post("/api/parts/toggle")
    async def toggle_part(req: PartToggleRequest) -> JSONResponse:
        return JSONResponse(session.toggle_part_prepared(req))

    @app.get("/api/export/parts-csv")
    async def export_parts_csv() -> Response:
        csv_bytes = session.build_parts_csv()
        return Response(
            content=csv_bytes,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="ewoodx_lista_piezas.csv"'},
        )

    # -----------------------------------------------------------------
    # Sandbox Simulator Endpoints (active only when enable_sandbox=True)
    # -----------------------------------------------------------------

    @app.get("/api/sandbox/status")
    async def sandbox_status() -> JSONResponse:
        if sandbox is None:
            return JSONResponse({"enabled": False})
        return JSONResponse(sandbox.status())

    @app.post("/api/sandbox/emit/{scenario_id}")
    async def sandbox_emit_scenario(scenario_id: str) -> JSONResponse:
        if sandbox is None:
            raise HTTPException(status_code=400, detail="El modo Sandbox no está activo.")
        try:
            st = sandbox.emit_scenario(scenario_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        await asyncio.sleep(0.08)
        snap = session._notify_change()
        return JSONResponse({"sandbox": st, "state": snap})

    @app.post("/api/sandbox/nudge-board")
    async def sandbox_nudge_board(req: SandboxNudgeRequest) -> JSONResponse:
        if sandbox is None:
            raise HTTPException(status_code=400, detail="El modo Sandbox no está activo.")
        st = sandbox.nudge_current_board(
            dx_mm=req.dx_mm,
            dy_mm=req.dy_mm,
            d_angle_deg=req.d_angle_deg,
        )
        await asyncio.sleep(0.08)
        snap = session._notify_change()
        return JSONResponse({"sandbox": st, "state": snap})

    @app.post("/api/sandbox/auto-feed")
    async def sandbox_auto_feed(req: SandboxAutoFeedRequest) -> JSONResponse:
        if sandbox is None:
            raise HTTPException(status_code=400, detail="El modo Sandbox no está activo.")
        st = sandbox.set_auto_feed(
            enabled=req.enabled,
            mode=req.mode,
            interval_s=req.interval_s,
        )
        snap = session._notify_change()
        return JSONResponse({"sandbox": st, "state": snap})

    @app.post("/api/scan")
    async def quick_scan() -> JSONResponse:
        """
        One-click Scan action:
        - In Sandbox mode: captures the next simulated board JSON over TCP StreamHost.
        - In Normal mode: loads latest projector_runtime measurement (or cycles sample board).
        """
        if sandbox is not None:
            order = sandbox.scenario_order
            try:
                idx = order.index(sandbox.current_scenario_id)
            except ValueError:
                idx = -1
            next_id = order[(idx + 1) % len(order)]
            st = sandbox.emit_scenario(next_id)
            await asyncio.sleep(0.08)
            snap = session._notify_change()
            return JSONResponse({"mode": "sandbox", "scenario": next_id, "sandbox": st, "state": snap})

        try:
            snap, path_str = session.load_runtime_board()
            return JSONResponse({"mode": "runtime", "loaded_path": path_str, "state": snap})
        except FileNotFoundError:
            # Offline fallback: cycle built-in board scenario so Scan always responds visually
            order = list(session.scenarios.keys())
            current_src = str(session.board_summary.get("timber_id", ""))
            next_id = order[0]
            for i, sid in enumerate(order):
                if session.scenarios[sid]["measurement"].get("timber_id") == current_src:
                    next_id = order[(i + 1) % len(order)]
                    break
            snap = session.load_board_scenario(next_id)
            return JSONResponse({"mode": "simulated", "scenario": next_id, "state": snap})

    @app.post("/api/rescan")
    async def rescan_moved_board(req: RescanBoardRequest | None = None) -> JSONResponse:
        """
        Re-scan an accidentally moved/rotated board, rigidly re-anchor the digital
        drawing (translation + rotation) at 0.00 mm relative drift, and immediately
        re-project onto the board's new table coordinates.
        """
        return JSONResponse(session.rescan_moved_board(req))

    @app.post("/api/rescan/upload")
    async def rescan_moved_board_upload(file: UploadFile = File(...)) -> JSONResponse:
        """Upload a freshly scanned JSON of the bumped board and rigidly re-anchor & re-project."""
        raw = await file.read()
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"JSON inválido: {exc}") from exc
        return JSONResponse(
            session.rescan_moved_board(RescanBoardRequest(measurement=data, auto_project=True))
        )

    @app.post("/api/send")
    async def quick_send() -> JSONResponse:
        """
        One-click Send Drawing action:
        Unblanks projector output and explicitly pushes the active tile payload
        over EWoodXStreamHost (if connected) and WebSocket (/projector).
        """
        with session._lock:
            session.projector_display["blanked"] = False
            payload = session.get_ewoodx_payload()
            stream_sent = False
            if session.stream_bridge.connected:
                stream_sent = session.stream_bridge.publish_projection(payload)
        snap = session._notify_change()
        return JSONResponse({"sent": True, "stream_sent": stream_sent, "state": snap})

    @app.post("/api/step/next")
    async def step_next() -> JSONResponse:
        return JSONResponse(session.step_next())

    @app.post("/api/step/back")
    async def step_back() -> JSONResponse:
        return JSONResponse(session.step_back())

    @app.post("/api/progressive/undo")
    async def progressive_undo() -> JSONResponse:
        return JSONResponse(session.undo_last_region())

    @app.post("/api/progressive/reset")
    async def progressive_reset() -> JSONResponse:
        return JSONResponse(session.reset_regions())

    @app.post("/api/progressive/auto-nest")
    async def progressive_auto_nest() -> JSONResponse:
        return JSONResponse(session.auto_nest_current())

    @app.get("/api/sandbox/opencv-frame")
    async def sandbox_opencv_frame() -> Response:
        if sandbox is None:
            raise HTTPException(status_code=400, detail="El modo Sandbox no está activo.")
        jpeg = sandbox.get_opencv_frame_jpeg(fallback_payload=session.get_ewoodx_payload())
        return Response(
            content=jpeg,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        ws_clients.add(ws)
        try:
            await ws.send_text(json.dumps({"type": "state", "data": session.get_state_snapshot()}))
            while True:
                # Keepalive / optional client ping
                raw = await ws.receive_text()
                if raw == "ping":
                    await ws.send_text('{"type":"pong"}')
        except WebSocketDisconnect:
            pass
        finally:
            ws_clients.discard(ws)

    return app
