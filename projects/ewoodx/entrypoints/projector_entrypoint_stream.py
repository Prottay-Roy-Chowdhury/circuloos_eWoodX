
"""
eWoodX projector application entrypoint.

Owns runtime configuration and launches the modular
projector composer.

Supports:
    - Standalone execution
    - Non-interactive CLI configuration
    - Application-managed execution and shutdown

Run from repository root:
    python -m projects.ewoodx.entrypoints.projector_entrypoint_stream
"""

from __future__ import annotations

import argparse
import math
import sys
import threading

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from projects.ewoodx.config import (
    CALIBRATION_ROOT,
    PROJECTOR_CALIBRATION_MODE,
)

from projects.ewoodx.operations.projector_composer import (
    EWoodXProjectorComposer,
)


# =============================================================
# PROJECTOR RUNTIME CONFIGURATION
# =============================================================

# Calibration

HOMOGRAPHY_FILE = (
    CALIBRATION_ROOT
    / "projector"
    / PROJECTOR_CALIBRATION_MODE
    / "projector_homography.npz"
)

# Display

FULLSCREEN = True
FRAME_DELAY_MS = 16

# Local sensing measurement

FILE_POLL_INTERVAL = 0.5

# Grasshopper geometry
# 0.0 disables inactivity timeout.

GH_TIMEOUT = 0.0

# Streaming
# When unavailable, local measurement monitoring continues.

ENABLE_STREAMING = True


# =============================================================
# APPLICATION SHUTDOWN LISTENER
# =============================================================

def listen_for_shutdown(
    shutdown_event: threading.Event,
) -> None:
    """
    Listen for application-managed shutdown requests.

    Only used when running in app mode.

    The listener does not directly modify composer state
    or interact with OpenCV.
    """

    try:

        while not shutdown_event.is_set():

            line = sys.stdin.readline()

            # The parent application closed stdin.

            if not line:

                shutdown_event.set()

                return

            command = line.strip().lower()

            if command in ("shutdown", "q", "quit"):

                print(
                    "[Projector] Application shutdown requested."
                )

                shutdown_event.set()

                return

    except (EOFError, OSError):

        shutdown_event.set()


# =============================================================
# PROJECTOR ENTRYPOINT
# =============================================================

class EWoodXProjectorEntrypoint:
    """
    Configure and launch one eWoodX projector application.

    The entrypoint owns startup configuration.

    The composer owns the running application's lifecycle,
    projection state, streaming, controls, and rendering.
    """

    def __init__(
        self,
        homography_file: str | Path = HOMOGRAPHY_FILE,
        fullscreen: bool = FULLSCREEN,
        frame_delay_ms: int = FRAME_DELAY_MS,
        file_poll_interval: float = FILE_POLL_INTERVAL,
        gh_timeout: float = GH_TIMEOUT,
        enable_streaming: bool = ENABLE_STREAMING,
        app_mode: bool = False,
    ) -> None:

        self.homography_file = Path(
            homography_file
        )

        self.fullscreen = bool(
            fullscreen
        )

        self.frame_delay_ms = frame_delay_ms

        self.file_poll_interval = (
            file_poll_interval
        )

        self.gh_timeout = gh_timeout

        self.enable_streaming = bool(
            enable_streaming
        )

        self.app_mode = bool(
            app_mode
        )

    def run(self) -> None:
        """
        Create and run the configured projector composer.
        """

        shutdown_event = threading.Event()

        # -----------------------------------------------------
        # Optional application-managed shutdown
        # -----------------------------------------------------

        if self.app_mode:

            listener = threading.Thread(
                target=listen_for_shutdown,
                args=(shutdown_event,),
                name="projector_shutdown_listener",
                daemon=True,
            )

            listener.start()

            print(
                "[Projector] Application mode enabled."
            )

        # -----------------------------------------------------
        # Existing projector composer
        # -----------------------------------------------------

        try:

            composer = EWoodXProjectorComposer(
                homography_file=self.homography_file,
                fullscreen=self.fullscreen,
                frame_delay_ms=self.frame_delay_ms,
                file_poll_interval=self.file_poll_interval,
                gh_timeout=self.gh_timeout,
                enable_streaming=self.enable_streaming,
            )

            if self.app_mode:

                composer.run(
                    shutdown_event=shutdown_event,
                )

            else:

                composer.run()

        finally:

            shutdown_event.set()


# =============================================================
# COMMAND-LINE CONFIGURATION
# =============================================================

def parse_arguments(
    argv: list[str] | None = None,
) -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "eWoodX projector application."
        ),
    )

    # ---------------------------------------------------------
    # Calibration
    # ---------------------------------------------------------

    parser.add_argument(
        "--homography-file",
        type=Path,
        default=HOMOGRAPHY_FILE,
        help=(
            "Projector homography calibration file."
        ),
    )

    # ---------------------------------------------------------
    # Display mode
    # ---------------------------------------------------------

    display_group = (
        parser.add_mutually_exclusive_group()
    )

    display_group.add_argument(
        "--fullscreen",
        dest="fullscreen",
        action="store_true",
        help="Enable fullscreen projection.",
    )

    display_group.add_argument(
        "--windowed",
        dest="fullscreen",
        action="store_false",
        help="Enable windowed projection.",
    )

    parser.set_defaults(
        fullscreen=FULLSCREEN,
    )

    # ---------------------------------------------------------
    # Rendering and local measurement
    # ---------------------------------------------------------

    parser.add_argument(
        "--frame-delay-ms",
        type=int,
        default=FRAME_DELAY_MS,
        help=(
            "OpenCV frame delay in milliseconds."
        ),
    )

    parser.add_argument(
        "--file-poll-interval",
        type=float,
        default=FILE_POLL_INTERVAL,
        help=(
            "Local measurement polling interval "
            "in seconds."
        ),
    )

    # ---------------------------------------------------------
    # Grasshopper
    # ---------------------------------------------------------

    parser.add_argument(
        "--gh-timeout",
        type=float,
        default=GH_TIMEOUT,
        help=(
            "Grasshopper inactivity timeout in seconds. "
            "Zero disables the timeout."
        ),
    )

    # ---------------------------------------------------------
    # Streaming
    # ---------------------------------------------------------

    streaming_group = (
        parser.add_mutually_exclusive_group()
    )

    streaming_group.add_argument(
        "--enable-streaming",
        dest="enable_streaming",
        action="store_true",
        help="Enable projector streaming.",
    )

    streaming_group.add_argument(
        "--disable-streaming",
        dest="enable_streaming",
        action="store_false",
        help="Disable projector streaming.",
    )

    parser.set_defaults(
        enable_streaming=ENABLE_STREAMING,
    )

    # ---------------------------------------------------------
    # Application-managed execution
    # ---------------------------------------------------------

    parser.add_argument(
        "--app-mode",
        action="store_true",
        help=(
            "Enable application-managed shutdown "
            "through standard input."
        ),
    )

    # ---------------------------------------------------------
    # Parse arguments
    # ---------------------------------------------------------

    arguments = parser.parse_args(argv)

    # ---------------------------------------------------------
    # Validate runtime parameters
    # ---------------------------------------------------------

    if arguments.frame_delay_ms < 1:

        parser.error(
            "--frame-delay-ms must be at least 1."
        )

    if (
        not math.isfinite(
            arguments.file_poll_interval
        )
        or arguments.file_poll_interval <= 0.0
    ):

        parser.error(
            "--file-poll-interval must be "
            "finite and positive."
        )

    if (
        not math.isfinite(
            arguments.gh_timeout
        )
        or arguments.gh_timeout < 0.0
    ):

        parser.error(
            "--gh-timeout must be finite "
            "and non-negative."
        )

    return arguments


# =============================================================
# MAIN
# =============================================================

def main(
    argv: list[str] | None = None,
) -> None:

    arguments = parse_arguments(argv)

    entrypoint = EWoodXProjectorEntrypoint(
        homography_file=arguments.homography_file,
        fullscreen=arguments.fullscreen,
        frame_delay_ms=arguments.frame_delay_ms,
        file_poll_interval=arguments.file_poll_interval,
        gh_timeout=arguments.gh_timeout,
        enable_streaming=arguments.enable_streaming,
        app_mode=arguments.app_mode,
    )

    entrypoint.run()


if __name__ == "__main__":

    main()