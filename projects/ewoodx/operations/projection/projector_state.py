"""
eWoodX - Projector State

Thread-safe state management for the eWoodX projector.

Maintains two independent geometry sources:

1. Sensing measurements
   - Loaded initially from local runtime JSON.
   - Updated by local JSON monitoring or live sensing stream.
   - Available without Grasshopper.

2. Grasshopper geometry
   - Complete geometry payload, including timber and design.
   - Takes priority while Grasshopper is active.
   - Never merged with sensing geometry.

Also manages:
- Latest local measurement selection.
- Runtime measurement JSON monitoring.
- Sensing stream priority over local JSON.
- Timber thickness.
- Grasshopper connection state and optional timeout.

Does not handle:
- TCP communication or stream subscriptions
- Homography transformations
- OpenCV rendering
- Keyboard or remote commands
"""

from __future__ import annotations

import copy
import json
import math
import threading
import time

from pathlib import Path

from projects.ewoodx.operations.projection.projector_geometry import (
    ProjectorGeometry,
)

class ProjectorState:
    """
    Thread-safe storage for projector geometry and parameters.

    Existing state interfaces remain compatible with the
    projector renderer, controls, and streaming composer.
    """

    def __init__(
        self,
        initial_data: dict,
        initial_thickness_mm: float = 0.0,
        runtime_root: str | Path | None = None,
        file_poll_interval: float = 0.5,
    ) -> None:

        if not isinstance(initial_data, dict):
            raise TypeError(
                "initial_data must be a dictionary."
            )

        self.lock = threading.RLock()

        # ---------------------------------------------------------
        # Sensing measurement state
        # ---------------------------------------------------------

        self.measurement_data = copy.deepcopy(
            initial_data
        )

        # Latest local runtime JSON.
        self.local_measurement_data = copy.deepcopy(
            initial_data
        )

        # Latest sensing stream measurement.
        self.stream_measurement_data = None
        self.stream_last_received_monotonic = 0.0

        # Stream is considered active only while fresh.
        self.sensing_timeout_seconds = 5.0

        self.measurement_revision = 0
        self.measurement_last_received_time = 0.0

        # Once a live sensing measurement arrives,
        # local JSON no longer replaces it.

        self.live_measurement_received = False

        # ---------------------------------------------------------
        # Local runtime measurement monitoring
        # ---------------------------------------------------------

        self.runtime_root = (
            Path(runtime_root)
            if runtime_root is not None
            else None
        )

        self.file_poll_interval = float(
            file_poll_interval
        )

        if (
            not math.isfinite(self.file_poll_interval)
            or self.file_poll_interval <= 0.0
        ):
            raise ValueError(
                "file_poll_interval must be finite "
                "and positive."
            )

        self.last_file_check = 0.0
        self.last_file_signature = None

        # ---------------------------------------------------------
        # Grasshopper geometry state
        # ---------------------------------------------------------

        self.gh_data = None

        self.is_connected = False
        self.last_received_time = 0.0
        self.packet_count = 0
        self.client_address = None

        # ---------------------------------------------------------
        # Projection parameters
        # ---------------------------------------------------------

        self.thickness_mm = max(
            0.0,
            float(initial_thickness_mm),
        )

        self._update_thickness(
            initial_data
        )

    # -------------------------------------------------------------
    # Default sensing measurement
    # -------------------------------------------------------------

    @staticmethod
    def empty_measurement() -> dict:
        """
        Default projector geometry when no measurement exists.

        Preserves the original viewer's empty-state schema.
        """

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

    # -------------------------------------------------------------
    # Local measurement file helpers
    # -------------------------------------------------------------

    @staticmethod
    def _measurement_files(
        runtime_root: Path,
    ) -> list[Path]:
        """
        Find local projector measurement files.

        Uses the existing eWoodX filename convention.
        """

        return list(
            runtime_root.glob(
                "timber_*_measurement.json"
            )
        )

    @classmethod
    def _latest_measurement_file(
        cls,
        runtime_root: Path,
    ) -> Path | None:
        """
        Select the most recently modified measurement file.
        """

        files = cls._measurement_files(
            runtime_root
        )

        if not files:
            return None

        return max(
            files,
            key=lambda path: path.stat().st_mtime_ns,
        )

    @staticmethod
    def _file_signature(
        path: Path,
    ) -> tuple:
        """
        Identify a measurement file version by
        its path, modification time, and size.
        """

        stat = path.stat()

        return (
            str(path.resolve()),
            stat.st_mtime_ns,
            stat.st_size,
        )
    
    @staticmethod
    def _read_measurement_file(
        path: Path,
        default_thickness_mm: float = 0.0,
    ) -> dict:
        """Load and normalize a local runtime measurement."""

        with path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            raw_data = json.load(handle)

        if not isinstance(raw_data, dict):
            raise ValueError(
                "Measurement JSON must contain a dictionary."
            )

        data = ProjectorGeometry.prepare_measurement(
            raw_data
        )

        data["source"] = path.name

        if data.get("thickness_mm") is None:
            data["thickness_mm"] = default_thickness_mm

        return data

    # -------------------------------------------------------------
    # Runtime-based initialization
    # -------------------------------------------------------------

    @classmethod
    def from_runtime(
        cls,
        runtime_root: str | Path,
        initial_thickness_mm: float = 0.0,
        file_poll_interval: float = 0.5,
    ) -> ProjectorState:
        """
        Initialize ProjectorState from the latest local
        timber measurement JSON.

        If no valid measurement exists, use empty geometry.

        This replaces the composer's previous
        _load_initial_measurement() implementation.
        """

        runtime_root = Path(
            runtime_root
        )

        initial_data = cls.empty_measurement()
        initial_signature = None

        try:

            path = cls._latest_measurement_file(
                runtime_root
            )

            if path is None:

                print(
                    "[Projector] No local timber "
                    "measurement found."
                )

            else:

                initial_data = (
                    cls._read_measurement_file(
                        path,
                        default_thickness_mm=(
                            initial_thickness_mm
                        ),
                    )
                )

                initial_signature = (
                    cls._file_signature(
                        path
                    )
                )

                print(
                    "[Projector] Initial measurement:"
                )

                print(
                    f"  {path.name}"
                )

        except (
            OSError,
            ValueError,
            TypeError,
        ) as error:

            print(
                "[Projector] Initial measurement "
                f"load failed: {error}"
            )

        state = cls(
            initial_data=initial_data,
            initial_thickness_mm=initial_thickness_mm,
            runtime_root=runtime_root,
            file_poll_interval=file_poll_interval,
        )

        state.last_file_signature = (
            initial_signature
        )

        return state

    # -------------------------------------------------------------
    # Continuous local measurement monitoring
    # -------------------------------------------------------------

    def poll_measurement_file(self) -> bool:
        """
        Monitor the latest local runtime measurement.

        Local JSON is retained as fallback even after
        live sensing updates have been received.
        """

        with self.lock:
         
            if self.runtime_root is None:
                return False

            now = time.monotonic()

            if (
                now - self.last_file_check
                < self.file_poll_interval
            ):
                return False

            self.last_file_check = now

            try:

                path = self._latest_measurement_file(
                    self.runtime_root
                )

                if path is None:
                    return False

                signature = self._file_signature(
                    path
                )

                if signature == self.last_file_signature:
                    return False

                data = self._read_measurement_file(
                    path,
                    default_thickness_mm=(
                        self.thickness_mm
                    ),
                )

                # Update through the existing state interface.
                # GH priority remains unchanged.

                self.update_measurement(
                    data
                )

                self.last_file_signature = signature

                print(
                    "[Projector] Local measurement updated:"
                    f" {path.name}"
                )

                return True

            except (
                OSError,
                ValueError,
                TypeError,
            ) as error:

                print(
                    "[Projector] Local measurement "
                    f"update failed: {error}"
                )

                return False

    # -------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------

    def _update_thickness(
        self,
        data: dict,
    ) -> None:
        """
        Update thickness from the active data source.

        Supports:
        - thickness_mm
        - timber_thickness_mm

        Must be called while holding the state lock,
        except during initialization.
        """

        value = data.get(
            "thickness_mm"
        )

        if value is None:
            value = data.get(
                "timber_thickness_mm"
            )

        if value is None:
            return

        try:
            value = float(value)

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return

        if (
            math.isfinite(value)
            and value >= 0.0
        ):
            self.thickness_mm = value

    
    def _active_sensing_data(self) -> dict:
        """
        Select live sensing while fresh, otherwise
        fall back to the latest local runtime JSON.

        Must be called while holding self.lock.
        """

        if (
            self.stream_measurement_data is not None
            and self.stream_last_received_monotonic > 0.0
            and (
                time.monotonic()
                - self.stream_last_received_monotonic
            ) <= self.sensing_timeout_seconds
        ):
            return self.stream_measurement_data

        return self.local_measurement_data

    def refresh_sensing_source(self) -> bool:
        """
        Update the selected sensing data when its source
        changes or its content has been updated.
        """

        with self.lock:
            selected = self._active_sensing_data()

            if selected == self.measurement_data:
                return False

            self.measurement_data = copy.deepcopy(
                selected
            )
            self.measurement_revision += 1

            if not self._gh_active():
                self._update_thickness(
                    self.measurement_data
                )

            return True

    def _gh_active(self) -> bool:
        """
        Return whether Grasshopper geometry is active.

        Must be called while holding self.lock.
        """

        return (
            self.is_connected
            and self.gh_data is not None
        )

    # -------------------------------------------------------------
    # Sensing measurement updates
    # -------------------------------------------------------------

    def update_measurement(
        self,
        measurement: dict,
        from_stream: bool = False,
    ) -> None:
        """
        Monitor the latest local runtime measurement.

        Local JSON is retained as fallback even after
        live sensing updates have been received.
        """

        if not isinstance(measurement, dict):
            raise TypeError(
                "measurement must be a dictionary."
            )

        with self.lock:
            prepared = copy.deepcopy(measurement)

            if from_stream:
                self.live_measurement_received = True

                self.stream_measurement_data = prepared
                self.stream_last_received_monotonic = (
                    time.monotonic()
                )

            else:
                self.local_measurement_data = prepared

            self.measurement_last_received_time = (
                time.time()
            )

            self.refresh_sensing_source()

    # -------------------------------------------------------------
    # Grasshopper geometry updates
    # -------------------------------------------------------------

    def update_gh_geometry(
        self,
        geometry: dict,
        source=None,
    ) -> None:
        """
        Replace the latest complete GH geometry payload.

        GH geometry is a complete representation,
        not an overlay merged with sensing data.
        """

        if not isinstance(
            geometry,
            dict,
        ):
            raise TypeError(
                "geometry must be a dictionary."
            )

        with self.lock:

            self.gh_data = copy.deepcopy(
                geometry
            )

            self.last_received_time = time.time()

            self.packet_count += 1

            self.client_address = source

            self.is_connected = True

            self._update_thickness(
                geometry
            )

    def update_from_json(
        self,
        json_data: dict,
        client_addr=None,
    ) -> None:
        """
        Compatibility method for the original
        projector viewer state interface.
        """

        self.update_gh_geometry(
            geometry=json_data,
            source=client_addr,
        )

    # -------------------------------------------------------------
    # Grasshopper connection state
    # -------------------------------------------------------------

    def set_disconnected(self) -> None:
        """
        Mark Grasshopper as disconnected.

        The latest sensing measurement becomes active.

        Stored GH geometry remains available for diagnostics.
        """

        with self.lock:

            self.is_connected = False

            self._update_thickness(
                self.measurement_data
            )

    def set_gh_connected(
        self,
        connected: bool,
    ) -> None:
        """
        Explicitly update Grasshopper connection status.
        """

        with self.lock:

            self.is_connected = bool(
                connected
            )

            if not self.is_connected:

                self._update_thickness(
                    self.measurement_data
                )

    def check_gh_timeout(
        self,
        timeout_seconds: float,
    ) -> bool:
        """
        Optional Grasshopper freshness check.

        Returns True when GH was active but its last
        geometry update exceeded the timeout.

        The timeout is not automatic.
        """

        timeout_seconds = float(
            timeout_seconds
        )

        if (
            not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0.0
        ):
            raise ValueError(
                "timeout_seconds must be finite "
                "and positive."
            )

        with self.lock:

            if not self.is_connected:
                return False

            if self.last_received_time <= 0.0:
                return False

            if (
                time.time() - self.last_received_time
                > timeout_seconds
            ):

                self.is_connected = False

                self._update_thickness(
                    self.measurement_data
                )

                return True

            return False

    # -------------------------------------------------------------
    # Projection thickness
    # -------------------------------------------------------------

    def set_thickness(
        self,
        thickness_mm: float,
    ) -> None:
        """
        Set projector thickness manually.

        Preserves the existing keyboard control interface.
        """

        value = float(
            thickness_mm
        )

        if (
            not math.isfinite(value)
            or value < 0.0
        ):
            raise ValueError(
                "thickness_mm must be finite "
                "and non-negative."
            )

        with self.lock:

            self.thickness_mm = value

    # -------------------------------------------------------------
    # Active geometry
    # -------------------------------------------------------------

    def get_active_source(self) -> str:
        """
        Return the currently selected geometry source.
        """

        with self.lock:

            if self._gh_active():
                return "grasshopper"

            return "sensing"

    def get_snapshot(self):
        """
        Return the existing five-element renderer snapshot.

        (
            active_geometry,
            gh_connected,
            gh_packet_count,
            gh_last_received_time,
            thickness_mm,
        )
        """

        with self.lock:

            self.refresh_sensing_source()

            if self._gh_active():

                active_data = self.gh_data

            else:

                active_data = self.measurement_data

            return (
                copy.deepcopy(active_data),
                self._gh_active(),
                self.packet_count,
                self.last_received_time,
                self.thickness_mm,
            )

    # -------------------------------------------------------------
    # Individual source snapshots
    # -------------------------------------------------------------

    def get_measurement_snapshot(
        self,
    ) -> dict:
        """
        Return a copy of the latest sensing measurement.
        """

        with self.lock:

            return copy.deepcopy(
                self.measurement_data
            )

    def get_gh_snapshot(
        self,
    ) -> dict | None:
        """
        Return a copy of the latest GH geometry.
        """

        with self.lock:

            return copy.deepcopy(
                self.gh_data
            )

    # -------------------------------------------------------------
    # Status
    # -------------------------------------------------------------

    def get_status(self) -> dict:
        """
        Return a thread-safe projector state snapshot.
        """

        with self.lock:

            return {
                "active_source": (
                    "grasshopper"
                    if self._gh_active()
                    else "sensing"
                ),
                "gh_connected": self.is_connected,
                "gh_packet_count": self.packet_count,
                "gh_last_received_time": (
                    self.last_received_time
                ),
                "gh_source": self.client_address,
                "measurement_revision": (
                    self.measurement_revision
                ),
                "measurement_last_received_time": (
                    self.measurement_last_received_time
                ),
                "live_measurement_received": (
                    self.live_measurement_received
                ),
                "runtime_root": (
                    str(self.runtime_root)
                    if self.runtime_root is not None
                    else None
                ),
                "file_poll_interval": (
                    self.file_poll_interval
                ),
                "thickness_mm": self.thickness_mm,
            }