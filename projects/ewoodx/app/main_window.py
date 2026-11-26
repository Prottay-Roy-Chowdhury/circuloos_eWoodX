"""
eWoodX operator application window.

Responsibilities:
    - Display process controls and status
    - Display process output
    - Embed native OpenCV windows
    - Coordinate application shutdown
"""

from __future__ import annotations

import win32gui
import win32con

from PySide6.QtCore import (
    Qt,
    QTimer,
)

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QPlainTextEdit,
    QFrame,
    QApplication,
    QGroupBox,
)

from projects.ewoodx.app.process_manager import (
    ProcessManager,
)

from projects.ewoodx.app.window_embedder import (
    NativeWindowEmbedder,
)


# =============================================================
# Process definitions
# =============================================================

HOST_PROCESS_ID = "stream_host"

HOST_MODULE = (
    "projects.ewoodx.entrypoints."
    "stream_host_entrypoint"
)

VIEWER_PROCESS_ID = "test_viewer"

VIEWER_MODULE = (
    "projects.ewoodx.app.tests.opencv_viewer"
)

VIEWER_WINDOW_NAME = (
    "eWoodX OpenCV Test Viewer"
)


class EWoodXMainWindow(QMainWindow):

    def __init__(self) -> None:

        super().__init__()

        self.setWindowTitle(
            "eWoodX - Operator Application"
        )

        self.resize(1100, 850)

        self.embedder = NativeWindowEmbedder()

        self.process_manager = ProcessManager(self)

        self.window_search_attempts = 0

        self.closing = False

        self._host_ready = False
        self._host_output_buffer = ""

        self._build_ui()
        self._setup_processes()
        self._setup_timers()

    # =========================================================
    # Interface
    # =========================================================

    def _build_ui(self) -> None:

        central = QWidget()

        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        layout.setContentsMargins(
            16, 16, 16, 16
        )

        layout.setSpacing(12)

        # -----------------------------------------------------
        # Header
        # -----------------------------------------------------

        title = QLabel("eWoodX")

        title.setStyleSheet(
            "font-size: 28px;"
            "font-weight: bold;"
        )

        subtitle = QLabel(
            "Operator Application"
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # -----------------------------------------------------
        # System controls
        # -----------------------------------------------------

        system_group = QGroupBox(
            "System Processes"
        )

        system_layout = QVBoxLayout(
            system_group
        )

        # Stream Host
        host_row = QHBoxLayout()

        host_title = QLabel("Stream Host")

        host_title.setMinimumWidth(140)

        self.host_start_button = QPushButton(
            "Start"
        )

        self.host_stop_button = QPushButton(
            "Stop"
        )

        self.host_stop_button.setEnabled(False)

        self.host_status_label = QLabel(
            "Stopped"
        )

        self.host_status_label.setMinimumWidth(180)

        host_row.addWidget(host_title)
        host_row.addWidget(self.host_start_button)
        host_row.addWidget(self.host_stop_button)
        host_row.addStretch()
        host_row.addWidget(self.host_status_label)

        system_layout.addLayout(host_row)

        # OpenCV test viewer
        viewer_row = QHBoxLayout()

        viewer_title = QLabel("OpenCV Test Viewer")

        viewer_title.setMinimumWidth(140)

        self.viewer_start_button = QPushButton(
            "Start"
        )

        self.viewer_stop_button = QPushButton(
            "Stop"
        )

        self.viewer_focus_button = QPushButton(
            "Focus Viewer"
        )

        self.viewer_stop_button.setEnabled(False)

        self.viewer_focus_button.setEnabled(False)

        self.viewer_status_label = QLabel(
            "Stopped"
        )

        self.viewer_status_label.setMinimumWidth(180)

        viewer_row.addWidget(viewer_title)
        viewer_row.addWidget(self.viewer_start_button)
        viewer_row.addWidget(self.viewer_stop_button)
        viewer_row.addWidget(self.viewer_focus_button)
        viewer_row.addStretch()
        viewer_row.addWidget(self.viewer_status_label)

        system_layout.addLayout(viewer_row)

        layout.addWidget(system_group)

        # -----------------------------------------------------
        # Viewer container
        # -----------------------------------------------------

        self.viewer_frame = QFrame()

        self.viewer_frame.setStyleSheet(
            "QFrame {"
            "background-color: #202020;"
            "border: 1px solid #505050;"
            "}"
        )

        self.viewer_layout = QVBoxLayout(
            self.viewer_frame
        )

        self.viewer_layout.setContentsMargins(
            0, 0, 0, 0
        )

        self.placeholder = QLabel(
            "OpenCV viewer not running"
        )

        self.placeholder.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.placeholder.setStyleSheet(
            "color: #aaaaaa;"
            "font-size: 16px;"
            "border: none;"
        )

        self.viewer_layout.addWidget(
            self.placeholder
        )

        layout.addWidget(
            self.viewer_frame,
            stretch=1,
        )

        # -----------------------------------------------------
        # Logs
        # -----------------------------------------------------

        log_header = QHBoxLayout()

        log_header.addWidget(
            QLabel("Process Output")
        )

        log_header.addStretch()

        self.clear_log_button = QPushButton(
            "Clear Log"
        )

        log_header.addWidget(
            self.clear_log_button
        )

        layout.addLayout(log_header)

        self.log_view = QPlainTextEdit()

        self.log_view.setReadOnly(True)

        self.log_view.setMaximumHeight(200)

        self.log_view.document().setMaximumBlockCount(
            2000
        )

        layout.addWidget(self.log_view)

        # -----------------------------------------------------
        # Signals
        # -----------------------------------------------------

        self.host_start_button.clicked.connect(
            self.start_host
        )

        self.host_stop_button.clicked.connect(
            self.stop_host
        )

        self.viewer_start_button.clicked.connect(
            self.start_viewer
        )

        self.viewer_stop_button.clicked.connect(
            self.stop_viewer
        )

        self.viewer_focus_button.clicked.connect(
            self.embedder.focus
        )

        self.clear_log_button.clicked.connect(
            self.log_view.clear
        )

    # =========================================================
    # Process registration
    # =========================================================

    def _setup_processes(self) -> None:

        # Stream Host
        self.host_process = (
            self.process_manager.register(
                process_id=HOST_PROCESS_ID,
                module=HOST_MODULE,
                shutdown_timeout_ms=5000,
            )
        )

        self.host_process.set_shutdown_callback(
            self._request_host_shutdown
        )

        # OpenCV test viewer
        self.viewer_process = (
            self.process_manager.register(
                process_id=VIEWER_PROCESS_ID,
                module=VIEWER_MODULE,
                shutdown_timeout_ms=3000,
            )
        )

        self.viewer_process.set_shutdown_callback(
            self._request_viewer_shutdown
        )

        # Common process signals
        self.process_manager.output_received.connect(
            self._on_process_output
        )

        self.process_manager.state_changed.connect(
            self._on_process_state_changed
        )

        self.process_manager.process_started.connect(
            self._on_process_started
        )

        self.process_manager.process_finished.connect(
            self._on_process_finished
        )

        self.process_manager.all_stopped.connect(
            self._on_all_processes_stopped
        )

    # =========================================================
    # Timers
    # =========================================================

    def _setup_timers(self) -> None:

        self.window_search_timer = QTimer(self)

        self.window_search_timer.setInterval(200)

        self.window_search_timer.timeout.connect(
            self._find_and_embed_window
        )

    # =========================================================
    # Stream Host
    # =========================================================

    def start_host(self) -> None:

        if self.closing:
            return

        if self.host_process.is_active:
            return

        self._host_ready = False
        self._host_output_buffer = ""

        self.process_manager.start(
            HOST_PROCESS_ID,
            arguments=["--app-mode"],
        )

    def stop_host(self) -> None:

        self.process_manager.stop(
            HOST_PROCESS_ID
        )

    def _request_host_shutdown(self) -> None:

        sent = self.host_process.send_input(
            "shutdown"
        )

        if sent:

            self._log(
                "[APP] Host shutdown command sent."
            )

        else:

            self._log(
                "[APP] Failed to send host "
                "shutdown command."
            )

            # The process manager's timeout will
            # handle forced termination if needed.

    # =========================================================
    # OpenCV test viewer
    # =========================================================

    def start_viewer(self) -> None:

        if self.closing:
            return

        self.window_search_attempts = 0

        self.process_manager.start(
            VIEWER_PROCESS_ID
        )

    def stop_viewer(self) -> None:

        self.window_search_timer.stop()

        self.viewer_focus_button.setEnabled(False)

        self.process_manager.stop(
            VIEWER_PROCESS_ID
        )

    def _request_viewer_shutdown(self) -> None:

        self.window_search_timer.stop()

        if self.embedder.is_valid():

            self.embedder.request_close()

            return

        hwnd = self.embedder.find_window(
            title=VIEWER_WINDOW_NAME,
            process_id=self.viewer_process.pid,
        )

        if hwnd is not None:

            win32gui.PostMessage(
                hwnd,
                win32con.WM_CLOSE,
                0,
                0,
            )

        else:

            self.viewer_process.process.terminate()

    # =========================================================
    # Window embedding
    # =========================================================

    def _find_and_embed_window(self) -> None:

        if (
            not self.viewer_process.is_running
            or self.viewer_process.is_stopping
            or self.closing
        ):

            self.window_search_timer.stop()

            return

        self.window_search_attempts += 1

        hwnd = self.embedder.find_window(
            title=VIEWER_WINDOW_NAME,
            process_id=self.viewer_process.pid,
        )

        if hwnd is None:

            if self.window_search_attempts >= 50:

                self.window_search_timer.stop()

                self._set_status(
                    self.viewer_status_label,
                    "Running - not embedded",
                )

                self._log(
                    "[APP] Window discovery timed out."
                )

            return

        self.window_search_timer.stop()

        self._log(
            f"[APP] OpenCV HWND: {hwnd}"
        )

        try:

            container = self.embedder.embed(
                hwnd,
                self.viewer_frame,
            )

            self.placeholder.hide()

            self.viewer_layout.addWidget(
                container
            )

            self.viewer_focus_button.setEnabled(True)

            self._set_status(
                self.viewer_status_label,
                "Running - embedded",
            )

            self._log(
                "[APP] OpenCV window embedded."
            )

        except Exception as error:

            self.embedder.release()

            self.placeholder.show()

            self._set_status(
                self.viewer_status_label,
                "Embedding failed",
            )

            self._log(
                f"[APP] Embedding failed: {error}"
            )

    # =========================================================
    # Process events
    # =========================================================

    def _on_process_started(
        self,
        process_id: str,
        pid: int,
    ) -> None:

        if process_id == VIEWER_PROCESS_ID:

            self.window_search_timer.start()

    def _on_process_state_changed(
        self,
        process_id: str,
        state: str,
    ) -> None:

        can_start = (
            state in ("Stopped", "Error")
            and not self.closing
        )

        can_stop = (
            state in ("Starting", "Running")
            and not self.closing
        )

        if process_id == HOST_PROCESS_ID:

            display_state = state

            if state == "Running":

                display_state = (
                    "Ready"
                    if self._host_ready
                    else "Starting host..."
                )

            self._set_status(
                self.host_status_label,
                display_state,
            )

            self.host_start_button.setEnabled(
                can_start
            )

            self.host_stop_button.setEnabled(
                can_stop
            )

        elif process_id == VIEWER_PROCESS_ID:

            display_state = state

            if state == "Running":

                display_state = "Waiting for viewer..."

            self._set_status(
                self.viewer_status_label,
                display_state,
            )

            self.viewer_start_button.setEnabled(
                can_start
            )

            self.viewer_stop_button.setEnabled(
                can_stop
            )

            if state != "Running":

                self.viewer_focus_button.setEnabled(
                    False
                )

    def _on_process_finished(
        self,
        process_id: str,
        exit_code: int,
    ) -> None:

        if process_id == HOST_PROCESS_ID:

            self._host_ready = False
            self._host_output_buffer = ""

        elif process_id == VIEWER_PROCESS_ID:

            self.window_search_timer.stop()

            self.embedder.release()

            self.placeholder.show()

            self.viewer_focus_button.setEnabled(False)

    # =========================================================
    # Process output
    # =========================================================

    def _on_process_output(
        self,
        process_id: str,
        output: str,
    ) -> None:

        prefix = {
            HOST_PROCESS_ID: "HOST",
            VIEWER_PROCESS_ID: "VIEWER",
        }.get(
            process_id,
            process_id.upper(),
        )

        for line in output.splitlines():

            if line.strip():

                self._log(
                    f"[{prefix}] {line}"
                )

        # Detect actual host startup using the existing
        # success message from the host entrypoint.
        if process_id == HOST_PROCESS_ID:

            self._host_output_buffer += output

            ready_message = (
                "[eWoodX] Stream host started successfully."
            )

            if (
                ready_message in self._host_output_buffer
                and self.host_process.is_running
                and not self.host_process.is_stopping
            ):

                if not self._host_ready:

                    self._host_ready = True

                    self._set_status(
                        self.host_status_label,
                        "Ready",
                    )

            # Retain only a small amount of recent output.
            self._host_output_buffer = (
                self._host_output_buffer[-4096:]
            )

    # =========================================================
    # Status and logs
    # =========================================================

    def _set_status(
        self,
        label: QLabel,
        status: str,
    ) -> None:

        label.setText(status)

        if (
            status == "Ready"
            or status == "Running - embedded"
        ):

            color = "#26965c"

        elif status in (
            "Error",
            "Embedding failed",
        ):

            color = "#d9534f"

        elif status == "Stopped":

            color = "#888888"

        else:

            color = "#c18b25"

        label.setStyleSheet(
            f"color: {color};"
            "font-weight: bold;"
        )

    def _log(self, message: str) -> None:

        self.log_view.appendPlainText(
            message
        )

    # =========================================================
    # Application shutdown
    # =========================================================

    def _on_all_processes_stopped(self) -> None:

        if self.closing:

            QTimer.singleShot(
                0,
                self.close,
            )

    def closeEvent(self, event) -> None:

        if self.process_manager.has_active_processes:

            event.ignore()

            if not self.closing:

                self.closing = True

                self.host_start_button.setEnabled(False)
                self.host_stop_button.setEnabled(False)

                self.viewer_start_button.setEnabled(False)
                self.viewer_stop_button.setEnabled(False)
                self.viewer_focus_button.setEnabled(False)

                self.window_search_timer.stop()

                self.process_manager.stop_all()

            return

        self.window_search_timer.stop()

        self.embedder.release()

        event.accept()

        # Preserve the previously tested explicit
        # termination of the Qt event loop.
        QTimer.singleShot(
            0,
            QApplication.instance().quit,
        )