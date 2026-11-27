"""Independent Windows-friendly entrypoint for the eWoodX Design Composer.

From repository root:
    python -m projects.ewoodx.entrypoints.design_entrypoint_stream
    python -m projects.ewoodx.entrypoints.design_entrypoint_stream --test-scenario mosaic_2x2
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from projects.ewoodx.web_app.web_app import (
    create_app,
)


def _find_available_port(host: str, preferred_port: int, max_tries: int = 20) -> int:
    for port in range(preferred_port, preferred_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    return preferred_port


def _open_browser_when_ready(url: str, open_projector: bool = False) -> None:
    time.sleep(0.9)
    try:
        webbrowser.open(url)
        if open_projector:
            time.sleep(0.4)
            webbrowser.open(f"{url}/projector")
    except Exception:
        pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="eWoodX Design-to-Projection & Mosaic Middleware",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="HTTP port (default: 8765)",
    )
    parser.add_argument(
        "--test-scenario",
        choices=["progressive_demo", "mosaic_2x2", "fit_dxf", "angled_board", "pdf_scale"],
        default=None,
        help="Start directly with a built-in evaluation test scenario.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open the web browser on startup.",
    )
    parser.add_argument(
        "--open-projector",
        action="store_true",
        help="Also open the dedicated /projector window on startup.",
    )
    parser.add_argument(
        "--sandbox",
        action="store_true",
        help="Start full local sandbox (EWoodXStreamHost + simulated camera + OpenCV ProjectorRenderer).",
    )
    parser.add_argument(
        "--app-mode",
        action="store_true",
        help="Exit gracefully on 'q' or EOF on stdin (for the PySide6 process manager).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    port = _find_available_port(args.host, args.port)
    url = f"http://{args.host}:{port}"

    app = create_app(
        start_with_test_scenario=args.test_scenario,
        enable_sandbox=args.sandbox,
    )

    print()
    print("=" * 64)
    if args.sandbox:
        print("  eWoodX · SANDBOX COMPLETO (CAMARA + STREAMHOST + PROYECTOR)")
    else:
        print("  eWoodX · DESIGN-TO-PROJECTION & MOSAIC MIDDLEWARE")
    print("=" * 64)
    print(f"  Interfaz de control : {url}")
    print(f"  Pantalla proyector  : {url}/projector")
    if args.sandbox and app.state.sandbox is not None:
        sb = app.state.sandbox
        print(
            f"  StreamHost TCP      : {sb.host_addr} "
            f"(sensing:{sb.sensing_port} / proj:{sb.projector_port} / ctrl:{sb.controller_port})"
        )
        print(f"  Frame OpenCV real   : {url}/api/sandbox/opencv-frame")
    if args.test_scenario:
        print(f"  Escenario de prueba : {args.test_scenario}")
    print("  Pulsa Ctrl+C en esta ventana para cerrar la aplicación.")
    print("=" * 64)
    print()

    if not args.no_browser and not args.app_mode:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(url, args.open_projector),
            daemon=True,
        ).start()

    config = uvicorn.Config(app, host=args.host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    if args.app_mode:
        def listen_for_shutdown() -> None:
            while not server.should_exit:
                line = sys.stdin.readline()
                if not line or line.strip().lower() in {"q", "quit", "stop", "exit"}:
                    server.should_exit = True
                    return

        threading.Thread(target=listen_for_shutdown, daemon=True).start()

    server.run()


if __name__ == "__main__":
    main()
