"""
Generic process manager for the eWoodX application.

Responsibilities:
    - Launch independent Python modules
    - Pass startup arguments
    - Monitor process state
    - Collect process output
    - Manage graceful and forced shutdown
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from PySide6.QtCore import (
    QObject,
    QProcess,
    QTimer,
    Signal,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class ManagedProcess(QObject):

    output_received = Signal(str, str)
    state_changed = Signal(str, str)
    started = Signal(str, int)
    finished = Signal(str, int)
    error_occurred = Signal(str, str)

    def __init__(
        self,
        process_id: str,
        module: str,
        parent: QObject | None = None,
        shutdown_timeout_ms: int = 5000,
    ) -> None:

        super().__init__(parent)

        self.process_id = process_id
        self.module = module

        self.shutdown_timeout_ms = shutdown_timeout_ms

        self._stopping = False
        self._shutdown_callback = None

        self.process = QProcess(self)

        self.process.setWorkingDirectory(
            str(PROJECT_ROOT)
        )

        self.process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )

        self.process.started.connect(
            self._on_started
        )

        self.process.finished.connect(
            self._on_finished
        )

        self.process.errorOccurred.connect(
            self._on_error
        )

        self.process.readyReadStandardOutput.connect(
            self._read_output
        )

        self.shutdown_timer = QTimer(self)

        self.shutdown_timer.setSingleShot(True)

        self.shutdown_timer.timeout.connect(
            self._force_stop
        )

    # =========================================================
    # Properties
    # =========================================================

    @property
    def pid(self) -> int:

        return int(self.process.processId())

    @property
    def is_active(self) -> bool:

        return (
            self.process.state()
            != QProcess.ProcessState.NotRunning
        )

    @property
    def is_running(self) -> bool:

        return (
            self.process.state()
            == QProcess.ProcessState.Running
        )

    @property
    def is_stopping(self) -> bool:

        return self._stopping

    # =========================================================
    # Start
    # =========================================================

    def start(
        self,
        arguments: list[str] | None = None,
    ) -> bool:

        if self.is_active:
            return False

        self._stopping = False
        self.shutdown_timer.stop()

        command_arguments = [
            "-u",
            "-m",
            self.module,
        ]

        if arguments:
            command_arguments.extend(arguments)

        self._log(
            f"Starting module: {self.module}"
        )

        self.state_changed.emit(
            self.process_id,
            "Starting",
        )

        self.process.start(
            sys.executable,
            command_arguments,
        )

        return True

    # =========================================================
    # Shutdown configuration
    # =========================================================

    def set_shutdown_callback(
        self,
        callback: Callable[[], None] | None,
    ) -> None:

        self._shutdown_callback = callback

    def send_input(
        self,
        message: str,
    ) -> bool:

        if not self.is_running:
            return False

        if not message.endswith("\n"):
            message += "\n"

        data = message.encode("utf-8")

        written = self.process.write(data)

        return written == len(data)

    # =========================================================
    # Stop
    # =========================================================

    def stop(self) -> bool:

        if not self.is_active:
            return False

        if self._stopping:
            return False

        self._stopping = True

        self.state_changed.emit(
            self.process_id,
            "Stopping",
        )

        self._log("Shutdown requested.")

        self.shutdown_timer.start(
            self.shutdown_timeout_ms
        )

        # If the process is still starting, the shutdown
        # request will be sent once it has started.
        if self.is_running:

            self._request_shutdown()

        return True

    def _request_shutdown(self) -> None:

        if self._shutdown_callback is not None:

            try:

                self._shutdown_callback()

            except Exception as error:

                self._log(
                    f"Shutdown callback failed: {error}"
                )

                self.process.terminate()

        else:

            self.process.terminate()

    def _force_stop(self) -> None:

        if not self.is_active:
            return

        self._log(
            "Graceful shutdown timed out. "
            "Forcing process termination."
        )

        self.process.kill()

    # =========================================================
    # Process events
    # =========================================================

    def _on_started(self) -> None:

        self._log(
            f"Process started. PID: {self.pid}"
        )

        if self._stopping:

            self._request_shutdown()
            return

        self.state_changed.emit(
            self.process_id,
            "Running",
        )

        self.started.emit(
            self.process_id,
            self.pid,
        )

    def _on_finished(
        self,
        exit_code,
        exit_status,
    ) -> None:

        self.shutdown_timer.stop()

        self._read_output()

        self._stopping = False

        normal_exit = (
            exit_status
            == QProcess.ExitStatus.NormalExit
        )

        self._log(
            f"Process finished. "
            f"Exit code: {exit_code}, "
            f"Normal exit: {normal_exit}"
        )

        state = (
            "Stopped"
            if normal_exit and exit_code == 0
            else "Error"
        )

        self.state_changed.emit(
            self.process_id,
            state,
        )

        self.finished.emit(
            self.process_id,
            int(exit_code),
        )

    def _on_error(self, error) -> None:

        message = self.process.errorString()

        self._log(
            f"Process error: {message}"
        )

        self.error_occurred.emit(
            self.process_id,
            message,
        )

        if error == QProcess.ProcessError.FailedToStart:

            self.shutdown_timer.stop()
            self._stopping = False

            self.state_changed.emit(
                self.process_id,
                "Error",
            )

            # FailedToStart does not necessarily emit
            # the QProcess finished signal.
            self.finished.emit(
                self.process_id,
                -1,
            )

    # =========================================================
    # Output
    # =========================================================

    def _read_output(self) -> None:

        data = bytes(
            self.process.readAllStandardOutput()
        )

        output = data.decode(
            "utf-8",
            errors="replace",
        )

        if output:

            self.output_received.emit(
                self.process_id,
                output,
            )

    def _log(self, message: str) -> None:

        self.output_received.emit(
            self.process_id,
            f"[APP] {message}\n",
        )


# =============================================================
# Multiple process manager
# =============================================================

class ProcessManager(QObject):

    output_received = Signal(str, str)
    state_changed = Signal(str, str)
    process_started = Signal(str, int)
    process_finished = Signal(str, int)
    error_occurred = Signal(str, str)

    all_stopped = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
    ) -> None:

        super().__init__(parent)

        self._processes: dict[
            str,
            ManagedProcess,
        ] = {}

    # =========================================================
    # Registration
    # =========================================================

    def register(
        self,
        process_id: str,
        module: str,
        shutdown_timeout_ms: int = 5000,
    ) -> ManagedProcess:

        if process_id in self._processes:

            raise ValueError(
                f"Process already registered: "
                f"{process_id}"
            )

        managed = ManagedProcess(
            process_id=process_id,
            module=module,
            parent=self,
            shutdown_timeout_ms=shutdown_timeout_ms,
        )

        managed.output_received.connect(
            self.output_received.emit
        )

        managed.state_changed.connect(
            self.state_changed.emit
        )

        managed.started.connect(
            self.process_started.emit
        )

        managed.finished.connect(
            self._on_process_finished
        )

        managed.error_occurred.connect(
            self.error_occurred.emit
        )

        self._processes[process_id] = managed

        return managed

    # =========================================================
    # Access
    # =========================================================

    def get(
        self,
        process_id: str,
    ) -> ManagedProcess:

        if process_id not in self._processes:

            raise KeyError(
                f"Unknown process: {process_id}"
            )

        return self._processes[process_id]

    @property
    def active_processes(self) -> list[str]:

        return [
            process_id
            for process_id, managed
            in self._processes.items()
            if managed.is_active
        ]

    @property
    def has_active_processes(self) -> bool:

        return bool(self.active_processes)

    # =========================================================
    # Operations
    # =========================================================

    def start(
        self,
        process_id: str,
        arguments: list[str] | None = None,
    ) -> bool:

        return self.get(process_id).start(
            arguments
        )

    def stop(
        self,
        process_id: str,
    ) -> bool:

        return self.get(process_id).stop()

    def stop_all(self) -> None:

        for managed in reversed(
            list(self._processes.values())
        ):

            if managed.is_active:

                managed.stop()

        if not self.has_active_processes:

            self.all_stopped.emit()

    # =========================================================
    # Events
    # =========================================================

    def _on_process_finished(
        self,
        process_id: str,
        exit_code: int,
    ) -> None:

        self.process_finished.emit(
            process_id,
            exit_code,
        )

        if not self.has_active_processes:

            self.all_stopped.emit()