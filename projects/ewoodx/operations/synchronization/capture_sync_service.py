"""
eWoodX synchronized camera capture.

Coordinates temporary projector blanking with camera
acquisition using the existing eWoodX streaming protocol.

Responsibilities:
    - Maintain minimum projection visibility
    - Request projector blanking
    - Wait for projector settling
    - Discard potentially buffered camera frames
    - Capture a synchronized image
    - Restore projection immediately
    - Report synchronization timing and status

Not responsible for:
    - Camera initialization or configuration
    - Camera calibration
    - Stream connection lifecycle
    - Image processing or segmentation
    - Measurement generation
    - Entity persistence
"""

import math
import time
import uuid

from projects.ewoodx.config import (
    STREAM_PROJECTOR_ID,
    SYNC_SETTLING_TIME_MS,
    SYNC_DISCARD_FRAMES,
    SYNC_MIN_PROJECTION_TIME_MS,
    SYNC_COMMAND_TIMEOUT_MS,
)


# ============================================================
# EXCEPTIONS
# ============================================================

class CaptureSyncError(RuntimeError):
    """Synchronized capture could not be completed."""


# ============================================================
# CAPTURE SYNCHRONIZATION SERVICE
# ============================================================

class CaptureSyncService:

    def __init__(
        self,
        camera,
        stream_service,
        projector_id=STREAM_PROJECTOR_ID,
        settling_time_ms=SYNC_SETTLING_TIME_MS,
        discard_frames=SYNC_DISCARD_FRAMES,
        min_projection_time_ms=SYNC_MIN_PROJECTION_TIME_MS,
        command_timeout_ms=SYNC_COMMAND_TIMEOUT_MS,
        should_cancel=None,
    ):

        if camera is None:
            raise ValueError("Camera is required.")

        if stream_service is None:
            raise ValueError("Stream service is required.")

        if not isinstance(projector_id, str) or not projector_id:
            raise ValueError("Projector ID is required.")

        if (
            not math.isfinite(settling_time_ms)
            or settling_time_ms < 0
        ):
            raise ValueError("Invalid settling time.")

        if (
            not isinstance(discard_frames, int)
            or discard_frames < 0
        ):
            raise ValueError("Invalid discard frame count.")

        if (
            not math.isfinite(min_projection_time_ms)
            or min_projection_time_ms < 0
        ):
            raise ValueError("Invalid minimum projection time.")

        if (
            not math.isfinite(command_timeout_ms)
            or command_timeout_ms <= 0
        ):
            raise ValueError("Invalid command timeout.")

        self.camera = camera
        self.stream_service = stream_service
        self.projector_id = projector_id

        self.settling_time = settling_time_ms / 1000.0
        self.discard_frames = discard_frames
        self.min_projection_time = (
            min_projection_time_ms / 1000.0
        )
        self.command_timeout = command_timeout_ms / 1000.0

        self.should_cancel = should_cancel

        # ----------------------------------------------------
        # Synchronization state
        # ----------------------------------------------------

        self.state = "IDLE"

        self.active_session_id = None
        self.last_restored_at = None

        self.successful_captures = 0
        self.failed_captures = 0

        self.last_error = None
        self.last_timing = {}


    # ========================================================
    # CANCELLATION
    # ========================================================

    def _check_cancelled(self):

        if (
            self.should_cancel is not None
            and self.should_cancel()
        ):
            raise CaptureSyncError(
                "Synchronized capture cancelled."
            )


    def _wait(self, duration):

        deadline = time.monotonic() + duration

        while True:

            self._check_cancelled()

            remaining = deadline - time.monotonic()

            if remaining <= 0:
                return

            time.sleep(min(remaining, 0.02))


    # ========================================================
    # PROJECTOR COMMANDS
    # ========================================================

    def _execute_command(
        self,
        command,
        parameters=None,
    ):

        if not self.stream_service.connected:

            raise CaptureSyncError(
                "Stream service is not connected."
            )

        request_id = str(uuid.uuid4())

        started_at = time.monotonic()

        deadline = (
            started_at + self.command_timeout
        )

        self.stream_service.send_command(
            target=self.projector_id,
            command=command,
            parameters=parameters or {},
            request_id=request_id,
        )

        while True:

            remaining = deadline - time.monotonic()

            if remaining <= 0:

                raise CaptureSyncError(
                    f"Timeout waiting for {command} acknowledgment."
                )

            response = self.stream_service.get_result(
                timeout=min(remaining, 0.05)
            )

            if response is None:

                if not self.stream_service.connected:

                    raise CaptureSyncError(
                        "Stream disconnected while waiting "
                        f"for {command}."
                    )

                continue

            # Ignore unrelated or expired command results.
            if response.get("request_id") != request_id:
                continue

            result = response.get("result", {})

            if not response.get("success", False):

                raise CaptureSyncError(
                    f"{command} failed: {result}"
                )

            if response.get("source") != self.projector_id:

                raise CaptureSyncError(
                    f"Unexpected response source for {command}."
                )

            if not isinstance(result, dict):

                raise CaptureSyncError(
                    f"Invalid response for {command}."
                )

            elapsed = (
                time.monotonic() - started_at
            )

            return result, elapsed


    # ========================================================
    # MINIMUM PROJECTION VISIBILITY
    # ========================================================

    def _wait_for_projection_visibility(self):

        if self.last_restored_at is None:
            return 0.0

        elapsed = (
            time.monotonic()
            - self.last_restored_at
        )

        remaining = max(
            0.0,
            self.min_projection_time - elapsed,
        )

        if remaining <= 0:
            return 0.0

        self.state = "WAITING_FOR_PROJECTION"

        started_at = time.monotonic()

        self._wait(remaining)

        return time.monotonic() - started_at


    # ========================================================
    # BLANKING AND RESTORATION
    # ========================================================

    def _blank_projection(self, session_id):

        self.state = "BLANKING"

        result, elapsed = self._execute_command(
            command="blank_projection",
            parameters={
                "session_id": session_id,
            },
        )

        if result.get("session_id") != session_id:

            raise CaptureSyncError(
                "Blanking session ID mismatch."
            )

        if result.get("projection_blanked") is not True:

            raise CaptureSyncError(
                "Projector blanking was not confirmed."
            )

        max_duration = result.get(
            "max_blanking_duration"
        )

        if (
            not isinstance(max_duration, (int, float))
            or not math.isfinite(max_duration)
            or max_duration <= 0
        ):

            raise CaptureSyncError(
                "Invalid projector blanking duration."
            )

        return float(max_duration), elapsed


    def _restore_projection(self, session_id):

        self.state = "RESTORING"

        result, elapsed = self._execute_command(
            command="restore_projection",
            parameters={
                "session_id": session_id,
            },
        )

        if result.get("session_id") != session_id:

            raise CaptureSyncError(
                "Restoration session ID mismatch."
            )

        if result.get("projection_blanked") is not False:

            raise CaptureSyncError(
                "Projection restoration was not confirmed."
            )

        self.last_restored_at = time.monotonic()

        return result, elapsed


    # ========================================================
    # BLANKING DEADLINE
    # ========================================================

    @staticmethod
    def _check_blanking_deadline(deadline):

        if time.monotonic() >= deadline:

            raise CaptureSyncError(
                "Projector blanking duration exceeded."
            )


    # ========================================================
    # SYNCHRONIZED CAPTURE
    # ========================================================

    def capture(self):

        """
        Capture one synchronized camera frame.

        Returns:
            BGR image as a NumPy array.

        Raises:
            CaptureSyncError if a valid synchronized
            capture cannot be completed.

        The caller owns the camera and stream lifecycle.
        """

        if self.active_session_id is not None:

            raise CaptureSyncError(
                "A synchronization session is already active."
            )

        started_at = time.monotonic()

        timing = {
            "projection_wait_ms": 0.0,
            "blank_ack_ms": 0.0,
            "settling_ms": 0.0,
            "discard_ms": 0.0,
            "capture_ms": 0.0,
            "restore_ack_ms": 0.0,
            "sync_duration_ms": 0.0,
        }

        session_id = str(uuid.uuid4())

        frame = None
        capture_error = None
        restoration_error = None

        blank_requested = False

        self.last_error = None

        try:

            # ------------------------------------------------
            # Minimum projection visibility
            # ------------------------------------------------

            self._check_cancelled()

            projection_wait = (
                self._wait_for_projection_visibility()
            )

            timing["projection_wait_ms"] = (
                projection_wait * 1000.0
            )

            self._check_cancelled()

            # ------------------------------------------------
            # Request projector blanking
            # ------------------------------------------------

            self.active_session_id = session_id

            blank_started_at = time.monotonic()

            # Set before sending the command so restoration
            # is attempted even if acknowledgment is lost.
            blank_requested = True

            max_duration, blank_elapsed = (
                self._blank_projection(session_id)
            )

            timing["blank_ack_ms"] = (
                blank_elapsed * 1000.0
            )

            # Conservative deadline using the local request
            # timestamp, not the remote projector clock.
            blanking_deadline = (
                blank_started_at + max_duration
            )

            self._check_blanking_deadline(
                blanking_deadline
            )

            # ------------------------------------------------
            # Projector settling
            # ------------------------------------------------

            self.state = "SETTLING"

            settle_started_at = time.monotonic()

            self._wait(self.settling_time)

            timing["settling_ms"] = (
                time.monotonic() - settle_started_at
            ) * 1000.0

            self._check_blanking_deadline(
                blanking_deadline
            )

            # ------------------------------------------------
            # Discard potentially buffered frames
            # ------------------------------------------------

            self.state = "DISCARDING"

            discard_started_at = time.monotonic()

            for _ in range(self.discard_frames):

                self._check_cancelled()

                self._check_blanking_deadline(
                    blanking_deadline
                )

                discarded = self.camera.capture()

                if discarded is None:

                    raise CaptureSyncError(
                        "Failed to discard camera frame."
                    )

                del discarded

            timing["discard_ms"] = (
                time.monotonic() - discard_started_at
            ) * 1000.0

            # ------------------------------------------------
            # Capture synchronized frame
            # ------------------------------------------------

            self.state = "CAPTURING"

            self._check_cancelled()

            self._check_blanking_deadline(
                blanking_deadline
            )

            capture_started_at = time.monotonic()

            frame = self.camera.capture()

            timing["capture_ms"] = (
                time.monotonic() - capture_started_at
            ) * 1000.0

            if frame is None:

                raise CaptureSyncError(
                    "Camera returned no frame."
                )

            self._check_blanking_deadline(
                blanking_deadline
            )

            self._check_cancelled()

        except Exception as exc:

            capture_error = exc

        finally:

            # ------------------------------------------------
            # Always attempt to restore projection
            # ------------------------------------------------

            if blank_requested:

                try:

                    result, restore_elapsed = (
                        self._restore_projection(session_id)
                    )

                    timing["restore_ack_ms"] = (
                        restore_elapsed * 1000.0
                    )

                    # An already restored projector may mean
                    # that its watchdog expired during capture.
                    if result.get("already_restored", False):

                        raise CaptureSyncError(
                            "Projector was restored before "
                            "explicit restoration."
                        )

                except Exception as exc:

                    restoration_error = exc

                    # The actual restoration time is unknown.
                    # Apply a conservative visibility wait
                    # before another capture attempt.
                    self.last_restored_at = time.monotonic()

            self.active_session_id = None

            timing["sync_duration_ms"] = (
                time.monotonic() - started_at
            ) * 1000.0

            self.last_timing = timing

            if (
                capture_error is not None
                or restoration_error is not None
            ):

                self.state = "ERROR"

            else:

                self.state = "IDLE"

        # ----------------------------------------------------
        # Reject failed or uncertain captures
        # ----------------------------------------------------

        if (
            capture_error is not None
            or restoration_error is not None
        ):

            errors = []

            if capture_error is not None:
                errors.append(str(capture_error))

            if restoration_error is not None:
                errors.append(
                    f"Restoration: {restoration_error}"
                )

            self.failed_captures += 1

            self.last_error = " | ".join(errors)

            raise CaptureSyncError(
                self.last_error
            )

        self.successful_captures += 1

        return frame


    # ========================================================
    # STATUS
    # ========================================================

    def get_status(self):

        return {
            "state": self.state,

            "projector_id": self.projector_id,

            "active_session_id": self.active_session_id,

            "settling_time_ms": (
                self.settling_time * 1000.0
            ),

            "discard_frames": self.discard_frames,

            "min_projection_time_ms": (
                self.min_projection_time * 1000.0
            ),

            "command_timeout_ms": (
                self.command_timeout * 1000.0
            ),

            "successful_captures": (
                self.successful_captures
            ),

            "failed_captures": (
                self.failed_captures
            ),

            "last_error": self.last_error,

            "last_timing": dict(self.last_timing),
        }