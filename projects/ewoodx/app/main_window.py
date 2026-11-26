"""
Initial eWoodX application window.

Tests:
    - Independent process launching
    - Process output monitoring
    - Native OpenCV window embedding
    - Process shutdown
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QProcess,
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
)

from projects.ewoodx.app.window_embedder import (
    NativeWindowEmbedder,
)


PROJECT_ROOT = (
    Path(__file__).resolve().parents[3]
)

TEST_MODULE = (
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

        self.resize(1100, 800)

        self.embedder = NativeWindowEmbedder()

        self.window_search_attempts = 0
        self.closing = False

        self._build_ui()
        self._setup_process()
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
            "Native OpenCV Window Integration Test"
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # -----------------------------------------------------
        # Controls
        # -----------------------------------------------------

        controls = QHBoxLayout()

        self.start_button = QPushButton(
            "Start Viewer"
        )

        self.stop_button = QPushButton(
            "Stop Viewer"
        )

        self.focus_button = QPushButton(
            "Focus Viewer"
        )

        self.stop_button.setEnabled(False)
        self.focus_button.setEnabled(False)

        self.status_label = QLabel("Stopped")

        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.focus_button)
        controls.addStretch()
        controls.addWidget(self.status_label)

        layout.addLayout(controls)

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

        layout.addWidget(
            QLabel("Process output")
        )

        self.log_view = QPlainTextEdit()

        self.log_view.setReadOnly(True)

        self.log_view.setMaximumHeight(150)

        self.log_view.document().setMaximumBlockCount(
            1000
        )

        layout.addWidget(self.log_view)

        # -----------------------------------------------------
        # Signals
        # -----------------------------------------------------

        self.start_button.clicked.connect(
            self.start_viewer
        )

        self.stop_button.clicked.connect(
            self.stop_viewer
        )

        self.focus_button.clicked.connect(
            self.embedder.focus
        )

    # =========================================================
    # Process
    # =========================================================

    def _setup_process(self) -> None:

        self.process = QProcess(self)

        self.process.setWorkingDirectory(
            str(PROJECT_ROOT)
        )

        self.process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )

        self.process.started.connect(
            self._on_process_started
        )

        self.process.finished.connect(
            self._on_process_finished
        )

        self.process.errorOccurred.connect(
            self._on_process_error
        )

        self.process.readyReadStandardOutput.connect(
            self._read_process_output
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

        self.shutdown_timer = QTimer(self)

        self.shutdown_timer.setSingleShot(True)

        self.shutdown_timer.timeout.connect(
            self._force_stop
        )

    # =========================================================
    # Start
    # =========================================================

    def start_viewer(self) -> None:

        if (
            self.process.state()
            != QProcess.ProcessState.NotRunning
        ):
            return

        self.window_search_attempts = 0

        self.start_button.setEnabled(False)

        self.status_label.setText("Starting...")

        self._log("[APP] Starting OpenCV process.")

        self.process.start(
            sys.executable,
            [
                "-u",
                "-m",
                TEST_MODULE,
            ],
        )

    def _on_process_started(self) -> None:

        self._log(
            f"[APP] Process ID: "
            f"{self.process.processId()}"
        )

        self.status_label.setText(
            "Waiting for viewer..."
        )

        self.stop_button.setEnabled(True)

        self.window_search_timer.start()

    # =========================================================
    # Window embedding
    # =========================================================

    def _find_and_embed_window(self) -> None:

        self.window_search_attempts += 1

        hwnd = self.embedder.find_window(
            title=VIEWER_WINDOW_NAME,
            process_id=int(
                self.process.processId()
            ),
        )

        if hwnd is None:

            if self.window_search_attempts >= 50:

                self.window_search_timer.stop()

                self.status_label.setText(
                    "Running - not embedded"
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

            self.focus_button.setEnabled(True)

            self.status_label.setText(
                "Running - embedded"
            )

            self._log(
                "[APP] OpenCV window embedded."
            )

        except Exception as error:

            self.embedder.release()

            self.status_label.setText(
                "Running - embedding failed"
            )

            self._log(
                f"[APP] Embedding failed: {error}"
            )

    # =========================================================
    # Stop
    # =========================================================

    def stop_viewer(self) -> None:

        self.window_search_timer.stop()

        self.stop_button.setEnabled(False)

        self.focus_button.setEnabled(False)

        if (
            self.process.state()
            == QProcess.ProcessState.NotRunning
        ):
            return

        self.status_label.setText("Stopping...")

        self._log("[APP] Stopping viewer.")

        # Prefer closing the native viewer window.
        if self.embedder.is_valid():

            self.embedder.request_close()

        else:

            hwnd = self.embedder.find_window(
                title=VIEWER_WINDOW_NAME,
                process_id=int(
                    self.process.processId()
                ),
            )

            if hwnd is not None:

                import win32gui
                import win32con

                win32gui.PostMessage(
                    hwnd,
                    win32con.WM_CLOSE,
                    0,
                    0,
                )

            else:

                self.process.terminate()

        # Force termination only if the process
        # does not exit within three seconds.
        self.shutdown_timer.start(3000)

    def _force_stop(self) -> None:

        if (
            self.process.state()
            != QProcess.ProcessState.NotRunning
        ):

            self._log(
                "[APP] Graceful shutdown timed out. "
                "Forcing process termination."
            )

            self.embedder.release()

            self.process.kill()

    # =========================================================
    # Process events
    # =========================================================

    def _on_process_finished(
        self,
        exit_code,
        exit_status,
    ) -> None:

        self.window_search_timer.stop()
        self.shutdown_timer.stop()

        self._read_process_output()

        self.embedder.release()

        self.placeholder.show()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.focus_button.setEnabled(False)

        self.status_label.setText("Stopped")

        self._log(
            f"[APP] Process finished. "
            f"Exit code: {exit_code}"
        )

        if self.closing:

            QTimer.singleShot(
                0,
                self.close,
            )

    def _on_process_error(self, error) -> None:

        self._log(
            f"[APP] Process error: "
            f"{self.process.errorString()}"
        )

        if (
            self.process.state()
            == QProcess.ProcessState.NotRunning
        ):

            self.start_button.setEnabled(True)

            self.stop_button.setEnabled(False)

            self.status_label.setText("Error")

    # =========================================================
    # Logs
    # =========================================================

    def _read_process_output(self) -> None:

        data = bytes(
            self.process.readAllStandardOutput()
        )

        output = data.decode(
            "utf-8",
            errors="replace",
        )

        if output:

            self._log(output.rstrip())

    def _log(self, message: str) -> None:

        self.log_view.appendPlainText(message)

    # =========================================================
    # Application shutdown
    # =========================================================

    def closeEvent(self, event) -> None:

        if (
            self.process.state()
            != QProcess.ProcessState.NotRunning
        ):

            event.ignore()

            if not self.closing:

                self.closing = True

                self.stop_viewer()

            return

        self.window_search_timer.stop()
        self.shutdown_timer.stop()

        self.embedder.release()

        event.accept()

        # Explicitly terminate the Qt event loop.
        QTimer.singleShot(
            0,
            QApplication.instance().quit,
        )