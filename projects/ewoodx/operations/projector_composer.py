"""
eWoodX - Projector Composer

Application coordinator for the modular eWoodX
projection system.

Coordinates:
- ProjectorState
- ProjectorGeometry
- ProjectorRenderer
- ProjectorControls
- ProjectorStreamService

Data sources:
- Local timber measurement JSON
- Live sensing measurement stream
- Grasshopper geometry stream

Responsibilities:
- Initialize projection modules.
- Start and stop optional streaming.
- Route sensing and Grasshopper updates.
- Process remote commands.
- Coordinate rendering and keyboard input.
- Manage application shutdown.

Runtime configuration is supplied by:
    projects.ewoodx.entrypoints.projector_entrypoint

The legacy projector_live_viewer.py remains independent.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np


# -------------------------------------------------------------
# Repository import path
# -------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from projects.ewoodx.config import (
    PROJECTOR_RUNTIME_ROOT,
    PROJECTOR_HEIGHT_MM,
    PROJECTOR_POS_X_MM,
    PROJECTOR_POS_Y_MM,
    PROJECTOR_OFFSET_X_MM,
    PROJECTOR_OFFSET_Y_MM,
    TIMBER_THICKNESS_MM,
    PROJECTOR_WIDTH,
    PROJECTOR_HEIGHT,
)

from projects.ewoodx.operations.projection.projector_state import (
    ProjectorState,
)

from projects.ewoodx.operations.projection.projector_geometry import (
    ProjectorGeometry,
)

from projects.ewoodx.operations.projection.projector_renderer import (
    ProjectorRenderer,
)

from projects.ewoodx.operations.projection.projector_controls import (
    ProjectorControls,
)

from projects.ewoodx.operations.streaming.projector_stream_service import (
    ProjectorStreamService,
)


# =============================================================
# PROJECTOR COMPOSER
# =============================================================

class EWoodXProjectorComposer:
    """
    Application coordinator for the modular projector.

    Runtime settings are provided by the entrypoint.

    Projection modules retain responsibility for
    calibration, geometry, state, rendering, and controls.
    """

    def __init__(
        self,
        homography_file: str | Path,
        fullscreen: bool = True,
        frame_delay_ms: int = 16,
        file_poll_interval: float = 0.5,
        gh_timeout: float = 5.0,
        enable_streaming: bool = True,
        max_blanking_duration: float = 2.0,
    ) -> None:

        # ---------------------------------------------------------
        # Runtime configuration
        # ---------------------------------------------------------

        self.homography_file = Path(
            homography_file
        )

        self.fullscreen = bool(
            fullscreen
        )

        self.frame_delay_ms = int(
            frame_delay_ms
        )

        self.file_poll_interval = float(
            file_poll_interval
        )

        self.gh_timeout = float(
            gh_timeout
        )

        self.enable_streaming = bool(
            enable_streaming
        )

        self.max_blanking_duration = float(
            max_blanking_duration
        )

        # ---------------------------------------------------------
        # Configuration validation
        # ---------------------------------------------------------

        if (
            not math.isfinite(self.file_poll_interval)
            or self.file_poll_interval <= 0.0
        ):
            raise ValueError(
                "file_poll_interval must be "
                "finite and positive."
            )

        if (
            not math.isfinite(self.gh_timeout)
            or self.gh_timeout < 0.0
        ):
            raise ValueError(
                "gh_timeout must be finite "
                "and non-negative."
            )

        if self.frame_delay_ms < 1:
            raise ValueError(
                "frame_delay_ms must be at least 1."
            )

        if (
            not math.isfinite(self.max_blanking_duration)
            or self.max_blanking_duration <= 0.0
        ):
            raise ValueError(
                "max_blanking_duration must be "
                "finite and positive."
            )

        # ---------------------------------------------------------
        # Application lifecycle
        # ---------------------------------------------------------

        self.running = False
        self.paused = False

        # ---------------------------------------------------------
        # Projection blanking state
        # ---------------------------------------------------------

        self.projection_blanked = False

        self.blanking_session_id = None
        self.blanking_owner = None
        self.blanking_started_at = None

        self.black_frame = np.zeros(
            (
                PROJECTOR_HEIGHT,
                PROJECTOR_WIDTH,
                3,
            ),
            dtype=np.uint8,
        )

        # ---------------------------------------------------------
        # Projector geometry and calibration
        # ---------------------------------------------------------

        self.geometry = ProjectorGeometry.from_calibration(
            homography_file=self.homography_file,
            projector_height_mm=PROJECTOR_HEIGHT_MM,
            projector_pos_x_mm=PROJECTOR_POS_X_MM,
            projector_pos_y_mm=PROJECTOR_POS_Y_MM,
        )

        # ---------------------------------------------------------
        # Projector state and local measurement fallback
        # ---------------------------------------------------------

        self.state = ProjectorState.from_runtime(
            runtime_root=PROJECTOR_RUNTIME_ROOT,
            initial_thickness_mm=TIMBER_THICKNESS_MM,
            file_poll_interval=self.file_poll_interval,
        )

        # ---------------------------------------------------------
        # Renderer
        # ---------------------------------------------------------

        self.renderer = ProjectorRenderer(
            geometry=self.geometry,
        )

        self.renderer.offset_x_mm = float(
            PROJECTOR_OFFSET_X_MM
        )

        self.renderer.offset_y_mm = float(
            PROJECTOR_OFFSET_Y_MM
        )

        # ---------------------------------------------------------
        # Controls
        # ---------------------------------------------------------

        self.controls = ProjectorControls(
            state=self.state,
            renderer=self.renderer,
        )

        # ---------------------------------------------------------
        # Streaming
        # ---------------------------------------------------------

        self.stream_service = (
            ProjectorStreamService()
            if self.enable_streaming
            else None
        )

        self.stream_started = False

        self.last_measurement_revision = 0
        self.last_geometry_revision = 0

    # =============================================================
    # STREAMING LIFECYCLE
    # =============================================================

    def _start_stream(self) -> None:
        """
        Start the projector streaming endpoint.

        If streaming is disabled, operate locally.

        If the streaming host is unavailable, continue
        with local measurement monitoring.
        """

        if self.stream_service is None:
            return

        try:

            self.stream_service.start()

            self.stream_started = True

            print(
                "[Projector] Streaming connected."
            )

        except (
            ConnectionError,
            OSError,
            RuntimeError,
            TimeoutError,
        ) as error:

            self.stream_started = False

            print(
                "[Projector] Streaming unavailable:"
                f" {error}"
            )

            print(
                "[Projector] Continuing with local "
                "measurement monitoring."
            )

    # =============================================================
    # STREAMING UPDATES
    # =============================================================

    def _poll_stream(self) -> None:
        """
        Route the latest streaming updates to ProjectorState.

        The streaming service owns message reception
        and latest-value buffering.

        ProjectorState owns the active source and
        sensing/Grasshopper priority.
        """

        if (
            not self.stream_started
            or self.stream_service is None
        ):
            return

        # ---------------------------------------------------------
        # Sensing measurement
        # ---------------------------------------------------------

        revision, message = (
            self.stream_service.get_latest_measurement()
        )

        if (
            message is not None
            and revision != self.last_measurement_revision
        ):

            payload = message.get(
                "payload"
            )

            if isinstance(payload, dict):

                prepared = (
                    self.geometry.prepare_measurement(
                        payload
                    )
                )

                self.state.update_measurement(
                    prepared,
                    from_stream=True,
                )

                print(
                    "[Projector] Sensing stream "
                    f"revision {revision}"
                )

            self.last_measurement_revision = revision

        # ---------------------------------------------------------
        # Grasshopper geometry
        # ---------------------------------------------------------

        revision, message = (
            self.stream_service.get_latest_geometry()
        )

        if (
            message is not None
            and revision != self.last_geometry_revision
        ):

            payload = message.get(
                "payload"
            )

            source = message.get(
                "source"
            )

            if isinstance(payload, dict):

                # Explicit GH disconnect convention.
                #
                # The streaming host does not currently
                # publish automatic publisher-disconnect
                # notifications.

                if payload.get("gh_connected") is False:

                    self.state.set_disconnected()

                    print(
                        "[Projector] Grasshopper "
                        "marked disconnected."
                    )

                else:

                    prepared = (
                        self.geometry.prepare_gh_geometry(
                            payload
                        )
                    )

                    self.state.update_gh_geometry(
                        prepared,
                        source=source,
                    )

            self.last_geometry_revision = revision

    # =============================================================
    # GRASSHOPPER INACTIVITY
    # =============================================================

    def _check_gh_timeout(self) -> None:
        """
        Optionally restore sensing when GH stops publishing.

        Disabled by default to preserve existing behavior.
        """

        if self.gh_timeout <= 0.0:
            return

        if self.state.check_gh_timeout(
            self.gh_timeout
        ):

            print(
                "[Projector] Grasshopper inactive "
                f"for {self.gh_timeout:.1f}s."
            )

            print(
                "[Projector] Restored latest "
                "sensing measurement."
            )

    # =============================================================
    # REMOTE COMMANDS
    # =============================================================

    def _process_commands(self) -> None:
        """
        Receive remote commands and delegate interpretation
        to ProjectorControls.

        Execute application actions before returning
        command acknowledgments.
        """

        if (
            not self.stream_started
            or self.stream_service is None
        ):
            return

        # Limit command processing per frame.

        for _ in range(20):

            message = self.stream_service.get_command()

            if message is None:
                break

            command = message.get("command")

            parameters = message.get(
                "parameters",
                {},
            )

            source = message.get("source")
            request_id = message.get("request_id")

            response = self.controls.handle_command(
                command=command,
                parameters=parameters,
                status=(
                    self.get_status()
                    if command == "get_status"
                    else None
                ),
            )

            # -----------------------------------------------------
            # Execute requested application action
            # -----------------------------------------------------

            if response["success"]:

                action = response.get("action")

                try:

                    if action == "pause":

                        if self.projection_blanked:
                            raise RuntimeError(
                                "Cannot pause during "
                                "an active blanking session."
                            )

                        self.paused = True

                    elif action == "resume":

                        self.paused = False

                    elif action == "stop":

                        self.running = False

                    elif action == "blank_projection":

                        response["result"] = (
                            self._blank_projection(
                                session_id=response[
                                    "result"
                                ]["session_id"],
                                source=source,
                            )
                        )

                    elif action == "restore_projection":

                        response["result"] = (
                            self._restore_projection(
                                session_id=response[
                                    "result"
                                ]["session_id"],
                                source=source,
                            )
                        )

                except (
                    KeyError,
                    TypeError,
                    ValueError,
                    RuntimeError,
                    OSError,
                    cv2.error,
                ) as error:

                    response = {
                        "success": False,
                        "result": {
                            "error": str(error),
                        },
                        "action": None,
                    }

            # -----------------------------------------------------
            # Return command result
            # -----------------------------------------------------

            if source and request_id:

                try:

                    self.stream_service.send_command_result(
                        target=source,
                        request_id=request_id,
                        success=response["success"],
                        result=response["result"],
                    )

                except (
                    ConnectionError,
                    OSError,
                ) as error:

                    print(
                        "[Projector] Command response "
                        f"failed: {error}"
                    )

            if not self.running:
                break
    
    # =============================================================
    # PROJECTION BLANKING
    # =============================================================

    def _blank_projection(
        self,
        session_id: str,
        source: str,
    ) -> dict:
        """
        Temporarily suppress the visual projection.

        Geometry reception and internal state updates
        remain active.
        """

        if not source:
            raise ValueError(
                "Blanking requires a valid source agent."
            )

        if self.paused:
            raise RuntimeError(
                "Cannot start blanking while projector "
                "is paused."
            )

        if self.projection_blanked:

            # Repeated request for the same session.
            if (
                self.blanking_session_id == session_id
                and self.blanking_owner == source
            ):
                return {
                    "session_id": session_id,
                    "projection_blanked": True,
                    "already_blanked": True,
                }

            raise RuntimeError(
                "Another blanking session is active."
            )

        self.projection_blanked = True
        self.blanking_session_id = session_id
        self.blanking_owner = source
        self.blanking_started_at = time.monotonic()

        try:

            # Submit a completely black image.
            self.renderer.show_frame(
                self.black_frame
            )

            # Process OpenCV GUI events before acknowledging.
            cv2.waitKey(1)

        except Exception:

            self._clear_blanking_state()
            raise

        print(
            "[Projector] Projection blanked:"
            f" {session_id}"
        )

        return {
            "session_id": session_id,
            "projection_blanked": True,
            "already_blanked": False,
            "max_blanking_duration": (
                self.max_blanking_duration
            ),
        }

    def _clear_blanking_state(self) -> None:
        """Reset temporary blanking state."""

        self.projection_blanked = False
        self.blanking_session_id = None
        self.blanking_owner = None
        self.blanking_started_at = None

    def _restore_projection(
        self,
        session_id: str,
        source: str,
    ) -> dict:
        """
        Restore normal projection for the active session.
        """

        if not self.projection_blanked:

            return {
                "session_id": session_id,
                "projection_blanked": False,
                "already_restored": True,
            }

        if self.blanking_session_id != session_id:

            raise RuntimeError(
                "Blanking session ID does not match."
            )

        if self.blanking_owner != source:

            raise RuntimeError(
                "Blanking session owner does not match."
            )

        self._resume_projection_output()

        print(
            "[Projector] Projection restored:"
            f" {session_id}"
        )

        return {
            "session_id": session_id,
            "projection_blanked": False,
            "already_restored": False,
        }

    def _resume_projection_output(self) -> None:
        """
        Clear blanking and immediately display the latest
        geometry using the existing source priority.
        """

        self._clear_blanking_state()

        frame = self.renderer.render_snapshot(
            self.state.get_snapshot()
        )

        self.renderer.show_frame(frame)

        cv2.waitKey(1)

    def _check_blanking_timeout(self) -> None:
        """
        Automatically restore projection if the sensing
        agent fails to release the blanking session.
        """

        if not self.projection_blanked:
            return

        if self.blanking_started_at is None:
            return

        elapsed = (
            time.monotonic()
            - self.blanking_started_at
        )

        if elapsed < self.max_blanking_duration:
            return

        session_id = self.blanking_session_id

        print(
            "[Projector] Blanking timeout:"
            f" {session_id}"
        )

        self._resume_projection_output()

        print(
            "[Projector] Projection automatically restored."
        )

    # =============================================================
    # APPLICATION STATUS
    # =============================================================

    def get_status(self) -> dict:
        """
        Aggregate application, streaming and projector status.
        """

        state_status = (
            self.state.get_status()
        )

        return {
            **state_status,
            "stream_connected": (
                self.stream_service.connected
                if self.stream_service is not None
                else False
            ),
            "stream_started": self.stream_started,
            "stream_enabled": self.enable_streaming,
            "paused": self.paused,
            "projection_blanked": (
                self.projection_blanked
            ),
            "blanking_session_id": (
                self.blanking_session_id
            ),
            "blanking_owner": (
                self.blanking_owner
            ),
            "max_blanking_duration": (
                self.max_blanking_duration
            ),
            "fullscreen": self.fullscreen,
            "homography_file": str(
                self.homography_file
            ),
            "local_measurement_enabled": True,
            "controls": (
                self.controls.get_parameters()
            ),
        }

    # =============================================================
    # STARTUP INFORMATION
    # =============================================================

    def _print_startup_info(self) -> None:

        print()
        print("=" * 60)
        print("EWOODX MODULAR PROJECTOR")
        print("=" * 60)

        print(
            "Calibration:",
            self.homography_file,
        )

        print(
            "Measurement directory:",
            PROJECTOR_RUNTIME_ROOT,
        )

        print(
            "Initial source:",
            self.state.get_active_source(),
        )

        if self.enable_streaming:

            print(
                "Streaming: enabled "
                "(local JSON fallback)"
            )

        else:

            print(
                "Streaming: disabled "
                "(local JSON monitoring)"
            )

        print(
            "GH timeout:",
            (
                f"{self.gh_timeout:.1f}s"
                if self.gh_timeout > 0.0
                else "disabled"
            ),
        )

        print()
        print("Controls:")
        print("  T / t       Thickness +5 / +1 mm")
        print("  G / g       Thickness -5 / -1 mm")
        print("  0           Thickness = 0 mm")
        print("  W / S       Offset Y +/-")
        print("  A / D       Offset X -/+")
        print("  Arrow keys  Offset nudging")
        print("  + / -       Nudge step")
        print("  R           Reset offsets")
        print("  H           Toggle HUD")
        print("  Q / ESC     Exit")
        print("=" * 60)
        print()

    # =============================================================
    # MAIN APPLICATION LOOP
    # =============================================================

    def run(self) -> None:
        """
        Run the projector application.

        Data and commands continue to be processed
        even when rendering is paused.
        """

        self._print_startup_info()

        self.running = True

        try:

            self._start_stream()

            self.renderer.create_window()

            if not self.fullscreen:

                cv2.setWindowProperty(
                    self.renderer.WINDOW_NAME,
                    cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_NORMAL,
                )

            while self.running:

                # -------------------------------------------------
                # Update projection sources
                # -------------------------------------------------

                self._poll_stream()

                self.state.poll_measurement_file()

                self._check_gh_timeout()

                self._check_blanking_timeout()

                # -------------------------------------------------
                # Remote commands
                # -------------------------------------------------

                self._process_commands()

                if not self.running:
                    break

                # -------------------------------------------------
                # Render current state
                # -------------------------------------------------
                
                if self.projection_blanked:

                    self.renderer.show_frame(
                        self.black_frame
                    )

                elif not self.paused:

                    frame = (
                        self.renderer.render_snapshot(
                            self.state.get_snapshot()
                        )
                    )

                    self.renderer.show_frame(
                        frame
                    )

                # -------------------------------------------------
                # Keyboard input
                # -------------------------------------------------

                key = self.renderer.poll_key(
                    self.frame_delay_ms
                )

                if key != -1:

                    self.running = (
                        self.controls.handle_key(
                            key
                        )
                    )

        except KeyboardInterrupt:

            print(
                "\n[Projector] Interrupted."
            )

        finally:

            self.running = False

            if self.stream_service is not None:

                self.stream_service.stop()

            self.renderer.close()

            print(
                "[Projector] Shutdown complete."
            )