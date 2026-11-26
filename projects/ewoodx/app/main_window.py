"""
eWoodX operator application window.

Responsibilities:
    - Display system process controls
    - Select sensing startup parameters
    - Launch existing eWoodX entrypoints
    - Display process output
    - Embed existing native OpenCV windows
    - Coordinate application shutdown

Workspace, domain, entry and entity management
remain within the existing framework.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QTimer,
)

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QLabel,
    QPlainTextEdit,
    QFrame,
    QApplication,
    QGroupBox,
    QComboBox,
    QLineEdit,
    QCheckBox,
    QInputDialog,
    QFileDialog,
    QMessageBox,
)

from framework.workspace import (
    list_workspaces,
    load_workspace,
    DomainManager,
    EntryManager,
)

from projects.ewoodx.config import (
    EWOODX_REPOSITORY_ROOT,
    SENSING_DOMAIN,
    TIMBER_THICKNESS_MM,
)

from projects.ewoodx.operations.entry_allocator import (
    EWoodXEntryAllocator,
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

SENSING_PROCESS_ID = "sensing"

SENSING_MODULE = (
    "projects.ewoodx.entrypoints."
    "sensing_entrypoint_stream"
)

SENSING_WINDOW_NAME = (
    "eWoodX Sensing Composer"
)


# =============================================================
# Main window
# =============================================================

class EWoodXMainWindow(QMainWindow):

    def __init__(self) -> None:

        super().__init__()

        self.setWindowTitle(
            "eWoodX - Operator Application"
        )

        self.resize(1200, 950)

        self.embedder = NativeWindowEmbedder()

        self.process_manager = ProcessManager(self)

        self.closing = False

        # Host state

        self._host_state = "Stopped"
        self._host_ready = False
        self._host_output_buffer = ""

        # Sensing state

        self._sensing_state = "Stopped"
        self._sensing_ready = False
        self._sensing_output_buffer = ""

        # Active sensing configuration

        self._active_streaming = False
        self._active_preview = False

        # Workspace and entry information

        self._workspace_available = False
        self._entry_available = False
        self._latest_entry_name = None

        # Viewer discovery

        self.window_search_attempts = 0

        # Operational values

        self._thickness_mm = float(
            TIMBER_THICKNESS_MM
        )

        # Initialization

        self._build_ui()
        self._setup_processes()
        self._setup_timers()
        self._connect_ui_signals()

        self._refresh_workspaces()
        self._update_controls()

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

        layout.setSpacing(10)

        # -----------------------------------------------------
        # Header
        # -----------------------------------------------------

        title = QLabel("eWoodX")

        title.setStyleSheet(
            "font-size: 28px;"
            "font-weight: bold;"
        )

        layout.addWidget(title)

        layout.addWidget(
            QLabel("Operator Application")
        )

        # -----------------------------------------------------
        # Stream Host
        # -----------------------------------------------------

        host_group = QGroupBox(
            "System Processes"
        )

        host_layout = QHBoxLayout(
            host_group
        )

        host_title = QLabel("Stream Host")

        host_title.setMinimumWidth(140)

        self.host_start_button = QPushButton(
            "Start"
        )

        self.host_stop_button = QPushButton(
            "Stop"
        )

        self.host_status_label = QLabel(
            "Stopped"
        )

        self.host_status_label.setMinimumWidth(
            180
        )

        host_layout.addWidget(host_title)

        host_layout.addWidget(
            self.host_start_button
        )

        host_layout.addWidget(
            self.host_stop_button
        )

        host_layout.addStretch()

        host_layout.addWidget(
            self.host_status_label
        )

        layout.addWidget(host_group)

        # -----------------------------------------------------
        # Sensing configuration
        # -----------------------------------------------------

        self.sensing_config_group = QGroupBox(
            "Sensing Configuration"
        )

        config_layout = QGridLayout(
            self.sensing_config_group
        )

        # Workspace mode

        self.workspace_mode_combo = QComboBox()

        self.workspace_mode_combo.addItem(
            "Last workspace",
            "last",
        )

        self.workspace_mode_combo.addItem(
            "Existing workspace",
            "existing",
        )

        self.workspace_mode_combo.addItem(
            "New workspace",
            "new",
        )

        # Existing workspace selection

        self.workspace_combo = QComboBox()

        self.workspace_combo.setMinimumWidth(
            220
        )

        # New workspace name

        self.new_workspace_edit = QLineEdit()

        self.new_workspace_edit.setPlaceholderText(
            "New workspace name"
        )

        self.refresh_button = QPushButton(
            "Refresh"
        )

        self.workspace_info_label = QLabel()

        self.workspace_info_label.setWordWrap(
            True
        )

        config_layout.addWidget(
            QLabel("Workspace mode"),
            0, 0,
        )

        config_layout.addWidget(
            self.workspace_mode_combo,
            0, 1,
        )

        config_layout.addWidget(
            QLabel("Workspace"),
            0, 2,
        )

        config_layout.addWidget(
            self.workspace_combo,
            0, 3,
        )

        config_layout.addWidget(
            self.refresh_button,
            0, 4,
        )

        config_layout.addWidget(
            QLabel("New workspace"),
            1, 0,
        )

        config_layout.addWidget(
            self.new_workspace_edit,
            1, 1, 1, 4,
        )

        config_layout.addWidget(
            self.workspace_info_label,
            2, 0, 1, 5,
        )

        # Entry mode

        self.entry_mode_combo = QComboBox()

        self.entry_mode_combo.addItem(
            "Latest entry",
            "latest",
        )

        self.entry_mode_combo.addItem(
            "Existing entry",
            "existing",
        )

        self.entry_mode_combo.addItem(
            "New entry",
            "new",
        )

        self.entry_combo = QComboBox()

        self.entry_combo.setMinimumWidth(
            220
        )

        self.entry_info_label = QLabel()

        self.entry_info_label.setWordWrap(
            True
        )

        config_layout.addWidget(
            QLabel("Entry mode"),
            3, 0,
        )

        config_layout.addWidget(
            self.entry_mode_combo,
            3, 1,
        )

        config_layout.addWidget(
            QLabel("Entry"),
            3, 2,
        )

        config_layout.addWidget(
            self.entry_combo,
            3, 3, 1, 2,
        )

        config_layout.addWidget(
            self.entry_info_label,
            4, 0, 1, 5,
        )

        # Equipment

        self.equipment_combo = QComboBox()

        self.equipment_combo.addItem(
            "Arducam",
            "arducam",
        )

        self.equipment_combo.addItem(
            "Webcam",
            "webcam",
        )

        self.equipment_combo.setCurrentIndex(
            self.equipment_combo.findData(
                "webcam"
            )
        )

        # Segmentation mode

        self.segmentation_combo = QComboBox()

        self.segmentation_combo.addItem(
            "Single timber",
            "single",
        )

        self.segmentation_combo.addItem(
            "Multiple timbers",
            "multi",
        )

        config_layout.addWidget(
            QLabel("Equipment"),
            5, 0,
        )

        config_layout.addWidget(
            self.equipment_combo,
            5, 1,
        )

        config_layout.addWidget(
            QLabel("Segmentation"),
            5, 2,
        )

        config_layout.addWidget(
            self.segmentation_combo,
            5, 3, 1, 2,
        )

        # Runtime configuration

        self.handdraw_checkbox = QCheckBox(
            "Enable hand-draw detection"
        )

        self.streaming_checkbox = QCheckBox(
            "Enable streaming"
        )

        self.synchronization_checkbox = QCheckBox(
            "Enable synchronization"
        )

        self.preview_checkbox = QCheckBox(
            "Enable preview"
        )

        self.handdraw_checkbox.setChecked(False)

        self.streaming_checkbox.setChecked(True)

        self.synchronization_checkbox.setChecked(
            False
        )

        self.preview_checkbox.setChecked(True)

        config_layout.addWidget(
            self.handdraw_checkbox,
            6, 0, 1, 2,
        )

        config_layout.addWidget(
            self.streaming_checkbox,
            6, 2, 1, 3,
        )

        config_layout.addWidget(
            self.synchronization_checkbox,
            7, 0, 1, 2,
        )

        config_layout.addWidget(
            self.preview_checkbox,
            7, 2, 1, 3,
        )

        # Optional intrinsic calibration

        self.intrinsic_edit = QLineEdit()

        self.intrinsic_edit.setPlaceholderText(
            "Use equipment default"
        )

        self.intrinsic_browse_button = QPushButton(
            "Browse"
        )

        config_layout.addWidget(
            QLabel("Intrinsic calibration"),
            8, 0,
        )

        config_layout.addWidget(
            self.intrinsic_edit,
            8, 1, 1, 3,
        )

        config_layout.addWidget(
            self.intrinsic_browse_button,
            8, 4,
        )

        config_layout.setColumnStretch(1, 1)
        config_layout.setColumnStretch(3, 1)

        layout.addWidget(
            self.sensing_config_group
        )

        # -----------------------------------------------------
        # Sensing process controls
        # -----------------------------------------------------

        sensing_group = QGroupBox(
            "Sensing Process"
        )

        sensing_layout = QHBoxLayout(
            sensing_group
        )

        self.sensing_start_button = QPushButton(
            "Start Sensing"
        )

        self.sensing_stop_button = QPushButton(
            "Stop Sensing"
        )

        self.sensing_focus_button = QPushButton(
            "Focus Viewer"
        )

        self.sensing_status_label = QLabel(
            "Stopped"
        )

        sensing_layout.addWidget(
            self.sensing_start_button
        )

        sensing_layout.addWidget(
            self.sensing_stop_button
        )

        sensing_layout.addWidget(
            self.sensing_focus_button
        )

        sensing_layout.addStretch()

        sensing_layout.addWidget(
            self.sensing_status_label
        )

        layout.addWidget(sensing_group)

        # -----------------------------------------------------
        # Sensing viewer
        # -----------------------------------------------------

        self.viewer_frame = QFrame()

        self.viewer_frame.setMinimumHeight(
            220
        )

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
            "Sensing viewer not running"
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
        # Sensing operations
        # -----------------------------------------------------

        operation_group = QGroupBox(
            "Sensing Operations"
        )

        operation_layout = QHBoxLayout(
            operation_group
        )

        self.save_button = QPushButton(
            "Save"
        )

        self.pause_button = QPushButton(
            "Pause / Resume"
        )

        self.thickness_button = QPushButton(
            "Set Thickness"
        )

        operation_layout.addWidget(
            self.save_button
        )

        operation_layout.addWidget(
            self.pause_button
        )

        operation_layout.addWidget(
            self.thickness_button
        )

        layout.addWidget(operation_group)

        # -----------------------------------------------------
        # Process output
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

        self.log_view.setMaximumHeight(160)

        self.log_view.document().setMaximumBlockCount(
            2000
        )

        layout.addWidget(self.log_view)

    # =========================================================
    # UI signals
    # =========================================================

    def _connect_ui_signals(self) -> None:

        self.host_start_button.clicked.connect(
            self.start_host
        )

        self.host_stop_button.clicked.connect(
            self.stop_host
        )

        self.sensing_start_button.clicked.connect(
            self.start_sensing
        )

        self.sensing_stop_button.clicked.connect(
            self.stop_sensing
        )

        self.sensing_focus_button.clicked.connect(
            self.embedder.focus
        )

        self.workspace_mode_combo.currentIndexChanged.connect(
            self._refresh_entries
        )

        self.workspace_combo.currentIndexChanged.connect(
            self._refresh_entries
        )

        self.entry_mode_combo.currentIndexChanged.connect(
            self._update_entry_selection
        )

        self.entry_combo.currentIndexChanged.connect(
            self._update_controls
        )

        self.new_workspace_edit.textChanged.connect(
            self._update_controls
        )

        self.refresh_button.clicked.connect(
            self._refresh_workspaces
        )

        self.streaming_checkbox.toggled.connect(
            self._update_streaming_options
        )

        self.intrinsic_browse_button.clicked.connect(
            self._browse_intrinsic
        )

        self.save_button.clicked.connect(
            self.save_sensing
        )

        self.pause_button.clicked.connect(
            self.toggle_sensing_pause
        )

        self.thickness_button.clicked.connect(
            self.set_sensing_thickness
        )

        self.clear_log_button.clicked.connect(
            self.log_view.clear
        )

    # =========================================================
    # Process registration
    # =========================================================

    def _setup_processes(self) -> None:

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

        self.sensing_process = (
            self.process_manager.register(
                process_id=SENSING_PROCESS_ID,
                module=SENSING_MODULE,
                shutdown_timeout_ms=15000,
            )
        )

        self.sensing_process.set_shutdown_callback(
            self._request_sensing_shutdown
        )

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

        self.window_search_timer.setInterval(
            200
        )

        self.window_search_timer.timeout.connect(
            self._find_and_embed_window
        )

    # =========================================================
    # Workspace selection
    # =========================================================

    def _refresh_workspaces(self, *_args) -> None:

        if self.closing:
            return

        previous_workspace = (
            self.workspace_combo.currentData()
        )

        self.workspace_combo.blockSignals(True)

        try:

            self.workspace_combo.clear()

            # Existing generic framework utility.

            workspaces = list_workspaces(
                project_root=EWOODX_REPOSITORY_ROOT,
            )

            for name in workspaces:

                self.workspace_combo.addItem(
                    name,
                    name,
                )

            index = (
                self.workspace_combo.findData(
                    previous_workspace
                )
            )

            if index >= 0:

                self.workspace_combo.setCurrentIndex(
                    index
                )

        except Exception as error:

            self._log(
                f"[APP] Workspace listing failed: "
                f"{error}"
            )

        finally:

            self.workspace_combo.blockSignals(
                False
            )

        self._refresh_entries()

    def _load_selected_workspace(self):

        mode = (
            self.workspace_mode_combo.currentData()
        )

        if mode == "new":

            return None

        if mode == "last":

            # Original framework API.
            # Existing directory initialization
            # behavior is preserved.

            return load_workspace(
                project_root=EWOODX_REPOSITORY_ROOT,
            )

        workspace_name = (
            self.workspace_combo.currentData()
        )

        if not workspace_name:

            raise FileNotFoundError(
                "No existing workspace selected."
            )

        return load_workspace(
            project_root=EWOODX_REPOSITORY_ROOT,
            workspace_name=workspace_name,
        )

    # =========================================================
    # Entry selection
    # =========================================================

    def _refresh_entries(self, *_args) -> None:

        workspace_mode = (
            self.workspace_mode_combo.currentData()
        )

        previous_entry = (
            self.entry_combo.currentData()
        )

        previous_entry_mode = (
            self.entry_mode_combo.currentData()
        )

        self._workspace_available = False
        self._entry_available = False
        self._latest_entry_name = None

        self.entry_combo.blockSignals(True)

        self.entry_mode_combo.blockSignals(True)

        try:

            self.entry_combo.clear()

            # ---------------------------------------------
            # New workspace
            # ---------------------------------------------

            if workspace_mode == "new":

                self.workspace_info_label.setText(
                    "Workspace will be created "
                    "when sensing starts."
                )

                self._workspace_available = True

                self.entry_mode_combo.setCurrentIndex(
                    self.entry_mode_combo.findData(
                        "new"
                    )
                )

                return

            # ---------------------------------------------
            # Existing or last workspace
            # ---------------------------------------------

            workspace = (
                self._load_selected_workspace()
            )

            self._workspace_available = True

            self.workspace_info_label.setText(
                f"Workspace: "
                f"{workspace.workspace_name}"
            )

            # ---------------------------------------------
            # Existing sensing domain
            # ---------------------------------------------

            domain_manager = DomainManager(
                workspace=workspace,
            )

            # Do not initialize a new managed domain
            # while selecting configuration.

            if not domain_manager.exists(
                SENSING_DOMAIN
            ):

                self.entry_mode_combo.setCurrentIndex(
                    self.entry_mode_combo.findData(
                        "new"
                    )
                )

                return

            sensing_domain = (
                domain_manager.load_domain(
                    SENSING_DOMAIN
                )
            )

            entry_manager = EntryManager(
                domain=sensing_domain,
            )

            entry_allocator = EWoodXEntryAllocator(
                entry_manager=entry_manager,
            )

            # ---------------------------------------------
            # Existing entries
            # ---------------------------------------------

            entries = (
                entry_manager.list_entries()
            )

            latest_entry = (
                entry_allocator.latest_entry()
            )

            if latest_entry is not None:

                self._latest_entry_name = (
                    latest_entry.entry_name
                )

            for entry in entries:

                self.entry_combo.addItem(
                    entry.entry_name,
                    entry.entry_name,
                )

            self._entry_available = bool(
                entries
            )

            index = (
                self.entry_combo.findData(
                    previous_entry
                )
            )

            if index >= 0:

                self.entry_combo.setCurrentIndex(
                    index
                )

            # ---------------------------------------------
            # Resolve available entry mode
            # ---------------------------------------------

            if not entries:

                target_mode = "new"

            elif (
                previous_entry_mode == "latest"
                and self._latest_entry_name is None
            ):

                target_mode = "existing"

            else:

                target_mode = (
                    previous_entry_mode
                    or "latest"
                )

            self.entry_mode_combo.setCurrentIndex(
                self.entry_mode_combo.findData(
                    target_mode
                )
            )

        except Exception as error:

            self._workspace_available = False
            self._entry_available = False
            self._latest_entry_name = None

            self.workspace_info_label.setText(
                f"Workspace unavailable: {error}"
            )

        finally:

            self.entry_combo.blockSignals(
                False
            )

            self.entry_mode_combo.blockSignals(
                False
            )

            self._update_entry_selection()

    def _update_entry_selection(
        self,
        *_args,
    ) -> None:

        workspace_mode = (
            self.workspace_mode_combo.currentData()
        )

        entry_mode = (
            self.entry_mode_combo.currentData()
        )

        if workspace_mode == "new":

            self.entry_mode_combo.blockSignals(
                True
            )

            self.entry_mode_combo.setCurrentIndex(
                self.entry_mode_combo.findData(
                    "new"
                )
            )

            self.entry_mode_combo.blockSignals(
                False
            )

            entry_mode = "new"

        # Disable unavailable entry modes.

        latest_index = (
            self.entry_mode_combo.findData(
                "latest"
            )
        )

        existing_index = (
            self.entry_mode_combo.findData(
                "existing"
            )
        )

        latest_item = (
            self.entry_mode_combo.model().item(
                latest_index
            )
        )

        existing_item = (
            self.entry_mode_combo.model().item(
                existing_index
            )
        )

        latest_item.setEnabled(
            workspace_mode != "new"
            and self._latest_entry_name is not None
        )

        existing_item.setEnabled(
            workspace_mode != "new"
            and self._entry_available
        )

        if not self._workspace_available:

            self.entry_info_label.setText(
                "No workspace available."
            )

        elif entry_mode == "new":

            self.entry_info_label.setText(
                "A new entry will be allocated "
                "when sensing starts."
            )

        elif entry_mode == "latest":

            self.entry_info_label.setText(
                f"Latest entry: "
                f"{self._latest_entry_name or 'Unavailable'}"
            )

            index = (
                self.entry_combo.findData(
                    self._latest_entry_name
                )
            )

            if index >= 0:

                self.entry_combo.setCurrentIndex(
                    index
                )

        else:

            self.entry_info_label.setText(
                "Select an existing sensing entry."
            )

        self._update_controls()

    # =========================================================
    # Runtime configuration
    # =========================================================

    def _update_streaming_options(
        self,
        *_args,
    ) -> None:

        if not self.streaming_checkbox.isChecked():

            self.synchronization_checkbox.setChecked(
                False
            )

        self._update_controls()

    def _browse_intrinsic(self) -> None:

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select intrinsic calibration",
            str(EWOODX_REPOSITORY_ROOT),
            "All files (*)",
        )

        if filename:

            self.intrinsic_edit.setText(
                filename
            )

    def _configuration_available(self) -> bool:

        workspace_mode = (
            self.workspace_mode_combo.currentData()
        )

        entry_mode = (
            self.entry_mode_combo.currentData()
        )

        if not self._workspace_available:

            return False

        if workspace_mode == "new":

            if not self.new_workspace_edit.text().strip():

                return False

            if entry_mode != "new":

                return False

        if entry_mode == "latest":

            if self._latest_entry_name is None:

                return False

        elif entry_mode == "existing":

            if not self.entry_combo.currentData():

                return False

        return True

    def _build_sensing_arguments(
        self,
    ) -> list[str]:

        workspace_mode = (
            self.workspace_mode_combo.currentData()
        )

        entry_mode = (
            self.entry_mode_combo.currentData()
        )

        arguments = [
            "--workspace-mode",
            workspace_mode,
        ]

        # ---------------------------------------------
        # Workspace
        # ---------------------------------------------

        if workspace_mode == "existing":

            workspace_name = (
                self.workspace_combo.currentData()
            )

            if not workspace_name:

                raise ValueError(
                    "Select an existing workspace."
                )

            arguments.extend([
                "--workspace-name",
                workspace_name,
            ])

        elif workspace_mode == "new":

            workspace_name = (
                self.new_workspace_edit.text().strip()
            )

            if not workspace_name:

                raise ValueError(
                    "Enter a workspace name."
                )

            arguments.extend([
                "--workspace-name",
                workspace_name,
            ])

        # ---------------------------------------------
        # Entry
        # ---------------------------------------------

        arguments.extend([
            "--entry-mode",
            entry_mode,
        ])

        if entry_mode == "existing":

            entry_name = (
                self.entry_combo.currentData()
            )

            if not entry_name:

                raise ValueError(
                    "Select an existing entry."
                )

            arguments.extend([
                "--entry-name",
                entry_name,
            ])

        # ---------------------------------------------
        # Equipment and segmentation
        # ---------------------------------------------

        arguments.extend([
            "--equipment",
            self.equipment_combo.currentData(),

            "--segmentation-mode",
            self.segmentation_combo.currentData(),
        ])

        # ---------------------------------------------
        # Runtime flags
        # ---------------------------------------------

        runtime_flags = [
            (
                "handdraw",
                self.handdraw_checkbox.isChecked(),
            ),
            (
                "streaming",
                self.streaming_checkbox.isChecked(),
            ),
            (
                "preview",
                self.preview_checkbox.isChecked(),
            ),
            (
                "synchronization",
                self.synchronization_checkbox.isChecked(),
            ),
        ]

        for name, enabled in runtime_flags:

            prefix = (
                "enable"
                if enabled
                else "disable"
            )

            arguments.append(
                f"--{prefix}-{name}"
            )

        # ---------------------------------------------
        # Optional intrinsic calibration
        # ---------------------------------------------

        intrinsic_file = (
            self.intrinsic_edit.text().strip()
        )

        if intrinsic_file:

            path = Path(
                intrinsic_file
            ).expanduser()

            if not path.is_absolute():

                path = (
                    EWOODX_REPOSITORY_ROOT
                    / path
                )

            path = path.resolve()

            if not path.is_file():

                raise FileNotFoundError(
                    f"Intrinsic file not found: "
                    f"{path}"
                )

            arguments.extend([
                "--intrinsic-file",
                str(path),
            ])

        return arguments

    # =========================================================
    # Stream Host
    # =========================================================

    def start_host(self) -> None:

        if (
            self.closing
            or self.host_process.is_active
        ):

            return

        self._host_ready = False
        self._host_output_buffer = ""

        self.process_manager.start(
            HOST_PROCESS_ID,
            arguments=["--app-mode"],
        )

        self._update_controls()

    def stop_host(self) -> None:

        if (
            self.sensing_process.is_active
            and self._active_streaming
        ):

            self._log(
                "[APP] Stop streaming sensing "
                "before stopping the host."
            )

            return

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

    # =========================================================
    # Sensing process
    # =========================================================

    def start_sensing(self) -> None:

        if (
            self.closing
            or self.sensing_process.is_active
        ):

            return

        if not self._configuration_available():

            QMessageBox.warning(
                self,
                "Sensing configuration",
                "Select a valid workspace and entry.",
            )

            return

        streaming = (
            self.streaming_checkbox.isChecked()
        )

        if streaming and not self._host_ready:

            QMessageBox.warning(
                self,
                "Stream Host",
                "Start the Stream Host before "
                "starting sensing with streaming enabled.",
            )

            return

        try:

            arguments = (
                self._build_sensing_arguments()
            )

        except Exception as error:

            QMessageBox.warning(
                self,
                "Sensing configuration",
                str(error),
            )

            return

        self._sensing_ready = False
        self._sensing_output_buffer = ""

        self._active_streaming = streaming

        self._active_preview = (
            self.preview_checkbox.isChecked()
        )

        self._thickness_mm = float(
            TIMBER_THICKNESS_MM
        )

        self.window_search_attempts = 0

        if self._active_preview:

            self.placeholder.setText(
                "Waiting for sensing viewer..."
            )

        else:

            self.placeholder.setText(
                "Sensing preview disabled"
            )

        self._log(
            f"[APP] Sensing arguments: {arguments}"
        )

        self.process_manager.start(
            SENSING_PROCESS_ID,
            arguments=arguments,
        )

        self._update_controls()

    def stop_sensing(self) -> None:

        self.window_search_timer.stop()

        self.process_manager.stop(
            SENSING_PROCESS_ID
        )

    def _request_sensing_shutdown(self) -> None:

        self.window_search_timer.stop()

        # Use the existing terminal input command.

        sent = (
            self.sensing_process.send_input(
                "q"
            )
        )

        if sent:

            self._log(
                "[APP] Sensing shutdown command sent."
            )

        else:

            self._log(
                "[APP] Failed to send sensing "
                "shutdown command."
            )

    # =========================================================
    # Sensing operations
    # =========================================================

    def _send_sensing_command(
        self,
        command: str,
        description: str,
    ) -> bool:

        if (
            not self._sensing_ready
            or not self.sensing_process.is_running
            or self.sensing_process.is_stopping
            or self.closing
        ):

            return False

        sent = (
            self.sensing_process.send_input(
                command
            )
        )

        if sent:

            self._log(
                f"[APP] {description} command sent."
            )

        else:

            self._log(
                f"[APP] Failed to send "
                f"{description} command."
            )

        return sent

    def save_sensing(self) -> None:

        self._send_sensing_command(
            "s",
            "Save",
        )

    def toggle_sensing_pause(self) -> None:

        self._send_sensing_command(
            "p",
            "Pause / resume",
        )

    def set_sensing_thickness(self) -> None:

        value, accepted = QInputDialog.getDouble(
            self,
            "Timber Thickness",
            "Thickness (mm):",
            self._thickness_mm,
            0.01,
            10000.0,
            2,
        )

        if not accepted:

            return

        # Existing terminal input expects:
        #
        # t
        # thickness_value
        #
        # Send both lines together.

        command = f"t\n{value}"

        sent = self._send_sensing_command(
            command,
            f"Set thickness to {value:.2f} mm",
        )

        if sent:

            self._thickness_mm = value

    # =========================================================
    # Native OpenCV window embedding
    # =========================================================

    def _find_and_embed_window(self) -> None:

        if (
            not self.sensing_process.is_running
            or self.sensing_process.is_stopping
            or not self._active_preview
            or self.closing
        ):

            self.window_search_timer.stop()

            return

        self.window_search_attempts += 1

        hwnd = self.embedder.find_window(
            title=SENSING_WINDOW_NAME,
            process_id=self.sensing_process.pid,
        )

        if hwnd is None:

            # 150 attempts x 200 ms = 30 seconds.

            if self.window_search_attempts >= 150:

                self.window_search_timer.stop()

                self.placeholder.setText(
                    "Sensing running - "
                    "viewer not embedded"
                )

                self._set_status(
                    self.sensing_status_label,
                    "Running - not embedded",
                )

                self._log(
                    "[APP] Sensing window "
                    "discovery timed out."
                )

            return

        self.window_search_timer.stop()

        self._log(
            f"[APP] Sensing OpenCV HWND: {hwnd}"
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

            self._set_status(
                self.sensing_status_label,
                "Running - embedded",
            )

            self._log(
                "[APP] Sensing window embedded."
            )

        except Exception as error:

            self.embedder.release()

            self.placeholder.setText(
                "Sensing window embedding failed"
            )

            self.placeholder.show()

            self._set_status(
                self.sensing_status_label,
                "Embedding failed",
            )

            self._log(
                f"[APP] Embedding failed: {error}"
            )

        self._update_controls()

    # =========================================================
    # Process events
    # =========================================================

    def _on_process_started(
        self,
        process_id: str,
        pid: int,
    ) -> None:

        if process_id == SENSING_PROCESS_ID:

            self._log(
                f"[APP] Sensing process PID: {pid}"
            )

        self._update_controls()

    def _on_process_state_changed(
        self,
        process_id: str,
        state: str,
    ) -> None:

        if process_id == HOST_PROCESS_ID:

            self._host_state = state

            display_state = state

            if state == "Running":

                display_state = (
                    "Ready"
                    if self._host_ready
                    else "Starting host..."
                )

            elif state in (
                "Stopping",
                "Stopped",
                "Error",
            ):

                self._host_ready = False

            self._set_status(
                self.host_status_label,
                display_state,
            )

        elif process_id == SENSING_PROCESS_ID:

            self._sensing_state = state

            display_state = state

            if state == "Running":

                display_state = (
                    "Initializing sensing..."
                )

            elif state in (
                "Stopping",
                "Stopped",
                "Error",
            ):

                self._sensing_ready = False

                self.window_search_timer.stop()

            self._set_status(
                self.sensing_status_label,
                display_state,
            )

        self._update_controls()

    def _on_process_finished(
        self,
        process_id: str,
        exit_code: int,
    ) -> None:

        if process_id == HOST_PROCESS_ID:

            self._host_ready = False
            self._host_output_buffer = ""

            if (
                self.sensing_process.is_active
                and self._active_streaming
                and not self.closing
            ):

                self._log(
                    "[APP] Warning: Stream Host "
                    "stopped while streaming sensing "
                    "is active."
                )

        elif process_id == SENSING_PROCESS_ID:

            self._sensing_ready = False
            self._sensing_output_buffer = ""

            self._active_streaming = False
            self._active_preview = False

            self.window_search_timer.stop()

            self.embedder.release()

            self.placeholder.setText(
                "Sensing viewer not running"
            )

            self.placeholder.show()

            if not self.closing:

                # Refresh available workspaces and
                # entries after sensing has stopped.

                self._refresh_workspaces()

        self._update_controls()

        if self.closing:

            self._continue_shutdown()

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
            SENSING_PROCESS_ID: "SENSING",
        }.get(
            process_id,
            process_id.upper(),
        )

        for line in output.splitlines():

            if line.strip():

                self._log(
                    f"[{prefix}] {line}"
                )

        # -----------------------------------------------------
        # Host readiness
        # -----------------------------------------------------

        if process_id == HOST_PROCESS_ID:

            self._host_output_buffer += output

            ready_message = (
                "[eWoodX] Stream host started successfully."
            )

            if (
                ready_message in self._host_output_buffer
                and self.host_process.is_running
                and not self.host_process.is_stopping
                and not self._host_ready
            ):

                self._host_ready = True

                self._set_status(
                    self.host_status_label,
                    "Ready",
                )

                self._update_controls()

            self._host_output_buffer = (
                self._host_output_buffer[-4096:]
            )

        # -----------------------------------------------------
        # Sensing readiness
        # -----------------------------------------------------

        elif process_id == SENSING_PROCESS_ID:

            self._sensing_output_buffer += output

            ready_message = (
                "[eWoodX] Sensing composer started."
            )

            if (
                ready_message in self._sensing_output_buffer
                and self.sensing_process.is_running
                and not self.sensing_process.is_stopping
                and not self._sensing_ready
            ):

                self._sensing_ready = True

                if self._active_preview:

                    self._set_status(
                        self.sensing_status_label,
                        "Waiting for viewer...",
                    )

                    self.window_search_attempts = 0

                    self.window_search_timer.start()

                else:

                    self._set_status(
                        self.sensing_status_label,
                        "Running - no preview",
                    )

                self._update_controls()

            self._sensing_output_buffer = (
                self._sensing_output_buffer[-4096:]
            )

    # =========================================================
    # UI state
    # =========================================================

    def _update_controls(self, *_args) -> None:

        host_active = (
            self.host_process.is_active
            or self._host_state in (
                "Starting",
                "Running",
                "Stopping",
            )
        )

        sensing_active = (
            self.sensing_process.is_active
            or self._sensing_state in (
                "Starting",
                "Running",
                "Stopping",
            )
        )

        config_enabled = (
            not sensing_active
            and not self.closing
        )

        workspace_mode = (
            self.workspace_mode_combo.currentData()
        )

        entry_mode = (
            self.entry_mode_combo.currentData()
        )

        # ---------------------------------------------
        # Host controls
        # ---------------------------------------------

        self.host_start_button.setEnabled(
            not host_active
            and not self.closing
        )

        self.host_stop_button.setEnabled(
            host_active
            and self._host_state != "Stopping"
            and not self.closing
            and not (
                sensing_active
                and self._active_streaming
            )
        )

        # ---------------------------------------------
        # Sensing configuration
        # ---------------------------------------------

        self.sensing_config_group.setEnabled(
            config_enabled
        )

        self.workspace_combo.setEnabled(
            config_enabled
            and workspace_mode == "existing"
        )

        self.new_workspace_edit.setEnabled(
            config_enabled
            and workspace_mode == "new"
        )

        self.entry_mode_combo.setEnabled(
            config_enabled
            and workspace_mode != "new"
            and self._workspace_available
        )

        self.entry_combo.setEnabled(
            config_enabled
            and entry_mode == "existing"
            and self._entry_available
        )

        self.synchronization_checkbox.setEnabled(
            config_enabled
            and self.streaming_checkbox.isChecked()
        )

        # ---------------------------------------------
        # Sensing process controls
        # ---------------------------------------------

        streaming_allowed = (
            not self.streaming_checkbox.isChecked()
            or self._host_ready
        )

        self.sensing_start_button.setEnabled(
            config_enabled
            and streaming_allowed
            and self._configuration_available()
        )

        self.sensing_stop_button.setEnabled(
            sensing_active
            and self._sensing_state != "Stopping"
            and not self.closing
        )

        # ---------------------------------------------
        # Operational controls
        # ---------------------------------------------

        operational = (
            self._sensing_ready
            and self.sensing_process.is_running
            and not self.sensing_process.is_stopping
            and not self.closing
        )

        self.save_button.setEnabled(
            operational
        )

        self.pause_button.setEnabled(
            operational
        )

        self.thickness_button.setEnabled(
            operational
        )

        self.sensing_focus_button.setEnabled(
            operational
            and self.embedder.is_valid()
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

        if status in (
            "Ready",
            "Running - embedded",
            "Running - no preview",
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

    def _continue_shutdown(self) -> None:

        if not self.closing:

            return

        # Stop sensing first.

        if self.sensing_process.is_active:

            if not self.sensing_process.is_stopping:

                self.process_manager.stop(
                    SENSING_PROCESS_ID
                )

            return

        # Stop host after sensing has exited.

        if self.host_process.is_active:

            if not self.host_process.is_stopping:

                self.process_manager.stop(
                    HOST_PROCESS_ID
                )

            return

        QTimer.singleShot(
            0,
            self.close,
        )

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

                self.window_search_timer.stop()

                self._update_controls()

                self._continue_shutdown()

            return

        self.closing = True

        self.window_search_timer.stop()

        self.embedder.release()

        event.accept()

        QTimer.singleShot(
            0,
            QApplication.instance().quit,
        )