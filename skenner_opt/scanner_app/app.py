"""
Main application window for SkennerOpt film scanning software.
Orchestrates scanner communication, image processing, and UI.
"""

import os
import sys
import logging
import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QMenuBar, QMenu, QStatusBar, QMessageBox,
    QProgressBar, QLabel, QFileDialog, QDialog, QTextEdit,
    QPushButton, QDialogButtonBox, QComboBox, QLineEdit,
    QFormLayout, QPlainTextEdit, QTabWidget, QSplashScreen,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QAction, QIcon, QFont, QCloseEvent, QPixmap, QColor, QBrush

from .scanner import (
    get_scanner, ScanSettings, ScanArea, ScanSource, ColorMode,
    ScannerError, ScannerNotFoundError, DemoScanner,
)
from .image_processor import ImageProcessor, ProcessingSettings
from .preview_widget import PreviewPanel
from .settings_panel import SettingsPanel
from .film_profiles import get_profile
from .bug_logger import (
    setup_file_logging, install_crash_handler, read_recent_logs,
    read_full_log, export_bug_report, export_full_log_bundle,
    collect_system_info, get_log_file, get_log_dir,
    BugReport, clear_old_logs,
)
from .history import UndoRedoManager
from .presets import (
    Preset, save_preset, load_preset, list_presets, delete_preset,
    export_preset, import_preset, get_builtin_presets,
    save_session, load_session, get_full_session_dict, unpack_session,
    _settings_to_dict, _dict_to_settings,
)
from .color_management import ColorManager, ColorSpace
from .metadata import ScanMetadata, apply_exif_to_image
from .frame_detection import (
    FrameDetector, auto_crop, auto_deskew,
    ALL_HOLDERS, extract_frame,
)
from . import theme as T

from PIL import Image

logger = logging.getLogger(__name__)


# ── Worker thread for scanning ──────────────────────────────────────────────

class ScanWorker(QThread):
    """Background thread for scanner operations."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)  # PIL Image or None
    error = pyqtSignal(str)

    def __init__(self, scanner, settings: ScanSettings, is_preview: bool = False):
        super().__init__()
        self._scanner = scanner
        self._settings = settings
        self._is_preview = is_preview

    def run(self):
        try:
            if self._is_preview:
                img = self._scanner.preview(
                    self._settings,
                    progress_callback=self._on_progress,
                )
            else:
                img = self._scanner.scan(
                    self._settings,
                    progress_callback=self._on_progress,
                )
            self.finished.emit(img)
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, percent: int, message: str):
        self.progress.emit(percent, message)


class ProcessWorker(QThread):
    """Background thread for image processing."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)  # PIL Image
    error = pyqtSignal(str)

    def __init__(self, processor: ImageProcessor, image: Image.Image,
                 settings: ProcessingSettings):
        super().__init__()
        self._processor = processor
        self._image = image
        self._settings = settings

    def run(self):
        try:
            self.progress.emit(10, "Processing image...")
            result = self._processor.process(self._image, self._settings)
            self.progress.emit(100, "Done")
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ── About Dialog ────────────────────────────────────────────────────────────

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About SkennerOpt")
        self.setFixedSize(440, 340)
        self.setStyleSheet(T.dialog_style())

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel(f"{T.ICON_FILM}  SkennerOpt")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont(T.FONT_FAMILY, 22, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {T.ACCENT}; margin: 12px;")
        layout.addWidget(title)

        version = QLabel("Version 2.0.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet(f"color: {T.FG_SECONDARY}; font-size: 13px;")
        layout.addWidget(version)

        desc = QLabel(
            "Professional film scanning software\n"
            "for Epson Perfection V370\n\n"
            "Features:\n"
            "• Color negative inversion with orange mask removal\n"
            "• 30+ film stock profiles\n"
            "• Professional image processing with 16-bit pipeline\n"
            "• Auto frame detection, crop & deskew\n"
            "• Undo/redo, presets, session persistence\n"
            "• ICC color management & EXIF metadata\n"
            "• Before/after split comparison\n"
            "• Dust & scratch removal\n"
            "• High-resolution scanning up to 4800 DPI"
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {T.FG_SECONDARY}; font-size: {T.FONT_SIZE_SM}; margin: 10px;")
        layout.addWidget(desc)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.setStyleSheet(T.primary_button_style())
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


# ── Bug Report Dialog ───────────────────────────────────────────────────────

class BugReportDialog(QDialog):
    """Dialog for viewing logs, filing bug reports, and exporting diagnostics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{T.ICON_BUG} Bug Report — SkennerOpt")
        self.setMinimumSize(720, 560)
        self.setStyleSheet(T.dialog_style())
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        tabs = QTabWidget()
        tabs.setStyleSheet(T.tab_widget_style())

        # ── Tab 1: Submit Bug Report ────────────────────────────────────
        report_tab = QWidget()
        report_layout = QVBoxLayout(report_tab)
        report_layout.setSpacing(6)

        form = QFormLayout()
        form.setSpacing(6)

        self._txt_title = QLineEdit()
        self._txt_title.setPlaceholderText("Brief summary of the issue...")
        self._txt_title.setStyleSheet(T.input_style())
        form.addRow(self._styled_label("Title:"), self._txt_title)

        self._combo_severity = QComboBox()
        self._combo_severity.addItems(["Low", "Medium", "High", "Critical"])
        self._combo_severity.setCurrentIndex(1)
        self._combo_severity.setStyleSheet(T.combo_style())
        form.addRow(self._styled_label("Severity:"), self._combo_severity)

        self._combo_category = QComboBox()
        self._combo_category.addItems([
            "General", "Scanner / Hardware", "Image Processing",
            "User Interface", "Crash / Error", "Feature Request"
        ])
        self._combo_category.setStyleSheet(T.combo_style())
        form.addRow(self._styled_label("Category:"), self._combo_category)

        report_layout.addLayout(form)

        report_layout.addWidget(self._styled_label("Description:"))
        self._txt_description = QPlainTextEdit()
        self._txt_description.setPlaceholderText(
            "Describe the problem in detail...\n\n"
            "What were you doing when it happened?"
        )
        self._txt_description.setStyleSheet(T.input_style())
        self._txt_description.setMinimumHeight(80)
        report_layout.addWidget(self._txt_description)

        report_layout.addWidget(self._styled_label("Steps to Reproduce:"))
        self._txt_steps = QPlainTextEdit()
        self._txt_steps.setPlaceholderText(
            "1. Open the application\n"
            "2. Select 'Transparency' source\n"
            "3. Click 'Scan'\n"
            "4. ..."
        )
        self._txt_steps.setStyleSheet(T.input_style())
        self._txt_steps.setMinimumHeight(60)
        report_layout.addWidget(self._txt_steps)

        self._chk_include_logs = None  # Will use checkbox
        log_note = QLabel(
            "Note: System info and recent application logs will be "
            "included automatically to help diagnose the issue."
        )
        log_note.setWordWrap(True)
        log_note.setStyleSheet(T.label_style_caption())
        report_layout.addWidget(log_note)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_export = QPushButton(f"{T.ICON_SAVE}  Export Bug Report...")
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.setStyleSheet(T.primary_button_style())
        btn_export.clicked.connect(self._on_export_report)
        btn_row.addWidget(btn_export)

        btn_copy = QPushButton("Copy to Clipboard")
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.setStyleSheet(T.secondary_button_style())
        btn_copy.clicked.connect(self._on_copy_report)
        btn_row.addWidget(btn_copy)

        btn_row.addStretch()
        report_layout.addLayout(btn_row)

        tabs.addTab(report_tab, "Report Bug")

        # ── Tab 2: View Logs ────────────────────────────────────────────
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)

        log_header = QHBoxLayout()
        log_header.addWidget(self._styled_label(
            f"Log file: {get_log_file()}"
        ))
        log_header.addStretch()

        btn_refresh = QPushButton(f"{T.ICON_RESET}  Refresh")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet(T.secondary_button_style())
        btn_refresh.clicked.connect(self._refresh_logs)
        log_header.addWidget(btn_refresh)

        log_layout.addLayout(log_header)

        self._log_viewer = QPlainTextEdit()
        self._log_viewer.setReadOnly(True)
        self._log_viewer.setStyleSheet(T.log_viewer_style())
        self._log_viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        log_layout.addWidget(self._log_viewer)

        log_btn_row = QHBoxLayout()

        btn_export_logs = QPushButton(f"{T.ICON_SAVE}  Export All Logs...")
        btn_export_logs.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export_logs.setStyleSheet(T.secondary_button_style())
        btn_export_logs.clicked.connect(self._on_export_logs)
        log_btn_row.addWidget(btn_export_logs)

        btn_open_dir = QPushButton(f"{T.ICON_FOLDER}  Open Log Folder")
        btn_open_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_dir.setStyleSheet(T.secondary_button_style())
        btn_open_dir.clicked.connect(self._on_open_log_folder)
        log_btn_row.addWidget(btn_open_dir)

        btn_clear_old = QPushButton(f"{T.ICON_RESET}  Clear Old Logs")
        btn_clear_old.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear_old.setStyleSheet(T.danger_button_style())
        btn_clear_old.clicked.connect(self._on_clear_old_logs)
        log_btn_row.addWidget(btn_clear_old)

        log_btn_row.addStretch()
        log_layout.addLayout(log_btn_row)

        tabs.addTab(log_tab, "View Logs")

        # ── Tab 3: System Info ──────────────────────────────────────────
        sys_tab = QWidget()
        sys_layout = QVBoxLayout(sys_tab)

        self._sys_info_viewer = QPlainTextEdit()
        self._sys_info_viewer.setReadOnly(True)
        self._sys_info_viewer.setStyleSheet(T.log_viewer_style())
        sys_layout.addWidget(self._sys_info_viewer)

        tabs.addTab(sys_tab, "System Info")

        layout.addWidget(tabs)

        # Close button
        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(T.secondary_button_style())
        btn_close.clicked.connect(self.accept)
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_layout.addWidget(btn_close)
        layout.addLayout(close_layout)

        # Load initial data
        self._refresh_logs()
        self._load_system_info()

    def _styled_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(T.label_style_secondary())
        return lbl

    def _refresh_logs(self):
        self._log_viewer.setPlainText(read_recent_logs(500))
        # Scroll to bottom
        scrollbar = self._log_viewer.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _load_system_info(self):
        info = collect_system_info()
        lines = []
        for key, value in info.items():
            if isinstance(value, dict):
                lines.append(f"{key}:")
                for k2, v2 in value.items():
                    lines.append(f"  {k2}: {v2}")
            elif isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{key}: {value}")
        self._sys_info_viewer.setPlainText("\n".join(lines))

    def _build_report(self) -> BugReport:
        severity_map = {0: "low", 1: "medium", 2: "high", 3: "critical"}
        category_map = {
            0: "general", 1: "scanner", 2: "processing",
            3: "ui", 4: "crash", 5: "feature_request"
        }
        return BugReport(
            title=self._txt_title.text().strip() or "Untitled Bug Report",
            description=self._txt_description.toPlainText().strip(),
            steps_to_reproduce=self._txt_steps.toPlainText().strip(),
            severity=severity_map.get(
                self._combo_severity.currentIndex(), "medium"
            ),
            category=category_map.get(
                self._combo_category.currentIndex(), "general"
            ),
            log_excerpt=read_recent_logs(300),
        )

    def _on_export_report(self):
        report = self._build_report()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Bug Report",
            os.path.join(
                os.path.expanduser("~"), "Desktop",
                f"skenner_bug_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            ),
            "Text Files (*.txt);;All Files (*.*)"
        )
        if file_path:
            try:
                path = export_bug_report(report, file_path)
                QMessageBox.information(
                    self, "Bug Report Exported",
                    f"Bug report saved to:\n{path}\n\n"
                    f"You can share this file for troubleshooting."
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error", f"Failed to export: {e}"
                )

    def _on_copy_report(self):
        report = self._build_report()
        # Build text version
        text = (
            f"SkennerOpt Bug Report\n"
            f"{'=' * 50}\n"
            f"Title: {report.title}\n"
            f"Severity: {report.severity}\n"
            f"Category: {report.category}\n"
            f"Date: {report.timestamp}\n\n"
            f"Description:\n{report.description}\n\n"
        )
        if report.steps_to_reproduce:
            text += f"Steps to Reproduce:\n{report.steps_to_reproduce}\n\n"
        text += f"System Info:\n"
        for k, v in report.system_info.items():
            text += f"  {k}: {v}\n"
        text += f"\nRecent Logs:\n{read_recent_logs(100)}"

        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(
            self, "Copied",
            "Bug report copied to clipboard.\n"
            "You can paste it into an email or issue tracker."
        )

    def _on_export_logs(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Folder to Export Logs"
        )
        if directory:
            try:
                out_dir = os.path.join(directory, "skenner_logs")
                export_full_log_bundle(out_dir)
                QMessageBox.information(
                    self, "Logs Exported",
                    f"All logs exported to:\n{out_dir}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error", f"Failed to export logs: {e}"
                )

    def _on_open_log_folder(self):
        log_dir = get_log_dir()
        if sys.platform == "win32":
            os.startfile(log_dir)
        else:
            import subprocess
            subprocess.Popen(["xdg-open", log_dir])

    def _on_clear_old_logs(self):
        result = QMessageBox.question(
            self, "Clear Old Logs",
            "Remove log files older than 30 days?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if result == QMessageBox.StandardButton.Yes:
            clear_old_logs(30)
            self._refresh_logs()
            QMessageBox.information(
                self, "Done", "Old log files have been removed."
            )


# ── Main Window ─────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """
    Main application window.
    Layout: [Settings Panel | Preview Panel]
    """

    def __init__(self):
        super().__init__()
        self._scanner = None
        self._processor = ImageProcessor()
        self._raw_image: Optional[Image.Image] = None  # Unprocessed scan
        self._processed_image: Optional[Image.Image] = None
        self._scan_worker: Optional[ScanWorker] = None
        self._process_worker: Optional[ProcessWorker] = None
        self._scan_counter = 0
        self._demo_mode = False
        self._process_timer = QTimer()
        self._process_timer.setSingleShot(True)
        self._process_timer.setInterval(300)  # Debounce processing
        self._process_timer.timeout.connect(self._do_process)

        # New subsystems
        self._undo_manager = UndoRedoManager(max_history=100)
        self._color_manager = ColorManager()
        self._frame_detector = FrameDetector()
        self._detected_frames = []  # List of DetectedFrame
        self._current_frame_index = -1
        self._suppress_history = False  # Suppress undo recording during restore

        self._setup_window()
        self._setup_menu()
        self._setup_ui()
        self._setup_status_bar()
        self._connect_signals()
        self._init_scanner()
        self._restore_session()

    def _setup_window(self):
        self.setWindowTitle(f"{T.ICON_FILM} SkennerOpt — Film Scanner")
        self.setMinimumSize(1100, 700)
        self.resize(1400, 900)
        # Main window chrome is handled by the global app stylesheet

    def _setup_menu(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        self._act_open = QAction("Open Image...", self)
        self._act_open.setShortcut("Ctrl+O")
        self._act_open.triggered.connect(self._on_open_image)
        file_menu.addAction(self._act_open)

        self._act_save = QAction("Save As...", self)
        self._act_save.setShortcut("Ctrl+S")
        self._act_save.triggered.connect(self._on_save)
        file_menu.addAction(self._act_save)

        self._act_save_raw = QAction("Save Raw Scan...", self)
        self._act_save_raw.triggered.connect(self._on_save_raw)
        file_menu.addAction(self._act_save_raw)

        file_menu.addSeparator()

        self._act_batch = QAction("Batch Scan...", self)
        self._act_batch.triggered.connect(self._on_batch_scan)
        file_menu.addAction(self._act_batch)

        file_menu.addSeparator()

        self._act_exit = QAction("Exit", self)
        self._act_exit.setShortcut("Ctrl+Q")
        self._act_exit.triggered.connect(self.close)
        file_menu.addAction(self._act_exit)

        # Edit menu (NEW: undo/redo + presets)
        edit_menu = menubar.addMenu("Edit")

        self._act_undo = QAction("Undo", self)
        self._act_undo.setShortcut("Ctrl+Z")
        self._act_undo.setEnabled(False)
        self._act_undo.triggered.connect(self._on_undo)
        edit_menu.addAction(self._act_undo)

        self._act_redo = QAction("Redo", self)
        self._act_redo.setShortcut("Ctrl+Y")
        self._act_redo.setEnabled(False)
        self._act_redo.triggered.connect(self._on_redo)
        edit_menu.addAction(self._act_redo)

        edit_menu.addSeparator()

        # Presets submenu
        presets_menu = edit_menu.addMenu("Presets")

        self._act_save_preset = QAction("Save Current as Preset...", self)
        self._act_save_preset.triggered.connect(self._on_save_preset)
        presets_menu.addAction(self._act_save_preset)

        self._act_load_preset = QAction("Load Preset...", self)
        self._act_load_preset.triggered.connect(self._on_load_preset)
        presets_menu.addAction(self._act_load_preset)

        self._act_import_preset = QAction("Import Preset File...", self)
        self._act_import_preset.triggered.connect(self._on_import_preset)
        presets_menu.addAction(self._act_import_preset)

        presets_menu.addSeparator()

        # Add built-in presets as actions
        for preset in get_builtin_presets():
            act = QAction(f"  {preset.name}", self)
            act.setToolTip(preset.description)
            act.triggered.connect(
                lambda checked, p=preset: self._apply_preset(p)
            )
            presets_menu.addAction(act)

        # Scanner menu
        scan_menu = menubar.addMenu("Scanner")

        self._act_connect = QAction("Connect Scanner", self)
        self._act_connect.triggered.connect(self._on_connect_scanner)
        scan_menu.addAction(self._act_connect)

        self._act_disconnect = QAction("Disconnect", self)
        self._act_disconnect.triggered.connect(self._on_disconnect_scanner)
        scan_menu.addAction(self._act_disconnect)

        scan_menu.addSeparator()

        self._act_preview = QAction("Preview Scan", self)
        self._act_preview.setShortcut("Ctrl+P")
        self._act_preview.triggered.connect(self._on_preview)
        scan_menu.addAction(self._act_preview)

        self._act_scan = QAction("Full Scan", self)
        self._act_scan.setShortcut("Ctrl+Return")
        self._act_scan.triggered.connect(self._on_scan)
        scan_menu.addAction(self._act_scan)

        scan_menu.addSeparator()

        # Frame detection
        self._act_detect_frames = QAction("Detect Frames", self)
        self._act_detect_frames.setShortcut("Ctrl+D")
        self._act_detect_frames.triggered.connect(self._on_detect_frames)
        scan_menu.addAction(self._act_detect_frames)

        self._act_auto_crop = QAction("Auto Crop", self)
        self._act_auto_crop.triggered.connect(self._on_auto_crop)
        scan_menu.addAction(self._act_auto_crop)

        self._act_auto_deskew = QAction("Auto Deskew", self)
        self._act_auto_deskew.triggered.connect(self._on_auto_deskew)
        scan_menu.addAction(self._act_auto_deskew)

        scan_menu.addSeparator()

        self._act_demo = QAction("Demo Mode", self)
        self._act_demo.setCheckable(True)
        self._act_demo.triggered.connect(self._on_toggle_demo)
        scan_menu.addAction(self._act_demo)

        # Image menu
        image_menu = menubar.addMenu("Image")

        self._act_auto_levels = QAction("Auto Levels", self)
        self._act_auto_levels.setShortcut("Ctrl+L")
        self._act_auto_levels.triggered.connect(self._on_auto_levels)
        image_menu.addAction(self._act_auto_levels)

        self._act_auto_wb = QAction("Auto White Balance", self)
        self._act_auto_wb.setShortcut("Ctrl+W")
        self._act_auto_wb.triggered.connect(self._on_auto_wb)
        image_menu.addAction(self._act_auto_wb)

        image_menu.addSeparator()

        self._act_reset_proc = QAction("Reset Processing", self)
        self._act_reset_proc.triggered.connect(self._on_reset_processing)
        image_menu.addAction(self._act_reset_proc)

        image_menu.addSeparator()

        # Color space submenu
        cs_menu = image_menu.addMenu("Color Space")
        self._cs_actions = {}
        for space in ColorSpace:
            act = QAction(space.value, self)
            act.setCheckable(True)
            if space == ColorSpace.SRGB:
                act.setChecked(True)
            act.triggered.connect(
                lambda checked, s=space: self._on_set_color_space(s)
            )
            cs_menu.addAction(act)
            self._cs_actions[space] = act

        # View menu
        view_menu = menubar.addMenu("View")

        self._act_fit = QAction("Fit in View", self)
        self._act_fit.setShortcut("Ctrl+0")
        self._act_fit.triggered.connect(
            lambda: self._preview_panel.set_image(self._processed_image)
        )
        view_menu.addAction(self._act_fit)

        self._act_zoom_100 = QAction("Zoom 100%", self)
        self._act_zoom_100.setShortcut("Ctrl+1")
        view_menu.addAction(self._act_zoom_100)

        view_menu.addSeparator()

        self._act_before_after = QAction("Before / After Compare", self)
        self._act_before_after.setShortcut("Ctrl+B")
        self._act_before_after.setCheckable(True)
        self._act_before_after.triggered.connect(self._on_toggle_before_after)
        view_menu.addAction(self._act_before_after)

        # Help menu
        help_menu = menubar.addMenu("Help")

        self._act_bug_report = QAction("Report Bug / View Logs...", self)
        self._act_bug_report.setShortcut("F1")
        self._act_bug_report.triggered.connect(self._on_bug_report)
        help_menu.addAction(self._act_bug_report)

        self._act_export_logs = QAction("Export Logs...", self)
        self._act_export_logs.triggered.connect(self._on_export_logs)
        help_menu.addAction(self._act_export_logs)

        self._act_open_log_dir = QAction("Open Log Folder", self)
        self._act_open_log_dir.triggered.connect(self._on_open_log_folder)
        help_menu.addAction(self._act_open_log_dir)

        help_menu.addSeparator()

        self._act_about = QAction("About SkennerOpt", self)
        self._act_about.triggered.connect(self._on_about)
        help_menu.addAction(self._act_about)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter: Settings | Preview
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {T.BORDER};
                width: 2px;
            }}
        """)

        # Settings panel (left)
        self._settings_panel = SettingsPanel()
        splitter.addWidget(self._settings_panel)

        # Preview panel (right)
        self._preview_panel = PreviewPanel()
        splitter.addWidget(self._preview_panel)

        # Set initial sizes (settings: 340px, preview: rest)
        splitter.setSizes([340, 1060])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

    def _setup_status_bar(self):
        self._status_bar = self.statusBar()

        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet(T.label_style_secondary())
        self._status_bar.addWidget(self._status_label, 1)

        self._scanner_label = QLabel("No scanner")
        self._scanner_label.setStyleSheet(T.label_style_secondary())
        self._status_bar.addPermanentWidget(self._scanner_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setFixedHeight(16)
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet(T.progress_bar_style())
        self._status_bar.addPermanentWidget(self._progress_bar)

    def _connect_signals(self):
        # Settings panel signals
        self._settings_panel.preview_requested.connect(self._on_preview)
        self._settings_panel.scan_requested.connect(self._on_scan)
        self._settings_panel.save_requested.connect(self._on_save)
        self._settings_panel.settings_changed.connect(self._on_settings_changed)

        # Crop signal from preview
        self._preview_panel.crop_changed.connect(self._on_crop_from_preview)
        self._preview_panel.get_view().crop_changed.connect(self._on_crop_from_preview)

        # Undo/redo state updates
        self._undo_manager.set_change_callback(self._update_undo_redo_ui)

        # Set default output directory
        default_output = os.path.join(os.path.expanduser("~"), "Pictures", "SkennerOpt")
        self._settings_panel.set_output_directory(default_output)

    def _init_scanner(self):
        """Initialize scanner on startup."""
        try:
            self._scanner = get_scanner(use_demo=False)
            if isinstance(self._scanner, DemoScanner):
                self._demo_mode = True
                self._act_demo.setChecked(True)
                self._scanner_label.setText("Demo Mode")
                self._status_label.setText(
                    "No scanner hardware detected — running in Demo Mode. "
                    "Connect your Epson V370 and restart to scan."
                )
            else:
                try:
                    info = self._scanner.connect()
                    self._scanner_label.setText(f"Connected: {info.name}")
                    self._status_label.setText(f"Scanner ready: {info.name}")
                except Exception as e:
                    self._scanner = get_scanner(use_demo=True)
                    self._demo_mode = True
                    self._act_demo.setChecked(True)
                    self._scanner_label.setText("Demo Mode")
                    self._status_label.setText(f"Could not connect to scanner: {e}")
        except Exception as e:
            self._scanner = get_scanner(use_demo=True)
            self._demo_mode = True
            self._act_demo.setChecked(True)
            self._scanner_label.setText("Demo Mode")
            self._status_label.setText(f"Scanner init failed: {e}")

    # ── Scanner Actions ─────────────────────────────────────────────────────

    def _on_connect_scanner(self):
        try:
            if self._scanner and self._scanner.is_connected:
                self._scanner.disconnect()

            self._scanner = get_scanner(use_demo=self._demo_mode)
            info = self._scanner.connect()
            self._scanner_label.setText(f"Connected: {info.name}")
            self._status_label.setText(f"Scanner ready: {info.name}")
        except ScannerNotFoundError as e:
            QMessageBox.warning(self, "Scanner Not Found", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))

    def _on_disconnect_scanner(self):
        if self._scanner:
            self._scanner.disconnect()
            self._scanner_label.setText("Disconnected")
            self._status_label.setText("Scanner disconnected")

    def _on_toggle_demo(self, checked: bool):
        self._demo_mode = checked
        if self._scanner:
            self._scanner.disconnect()
        self._scanner = get_scanner(use_demo=checked)
        if checked:
            self._scanner.connect()
            self._scanner_label.setText("Demo Mode")
            self._status_label.setText("Demo mode active — simulated scanner")
        else:
            self._scanner_label.setText("No scanner")
            self._status_label.setText("Demo mode disabled. Use Scanner > Connect.")

    def _on_preview(self):
        if not self._scanner:
            self._status_label.setText("No scanner available")
            return

        if not self._scanner.is_connected:
            try:
                self._scanner.connect()
            except Exception as e:
                QMessageBox.warning(self, "Scanner Error",
                                    f"Cannot connect to scanner: {e}")
                return

        settings = self._settings_panel.get_scan_settings()

        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setText("Preview scanning...")

        self._scan_worker = ScanWorker(self._scanner, settings, is_preview=True)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan(self):
        if not self._scanner:
            self._status_label.setText("No scanner available")
            return

        if not self._scanner.is_connected:
            try:
                self._scanner.connect()
            except Exception as e:
                QMessageBox.warning(self, "Scanner Error",
                                    f"Cannot connect to scanner: {e}")
                return

        settings = self._settings_panel.get_scan_settings()

        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setText("Scanning at full resolution...")

        self._scan_worker = ScanWorker(self._scanner, settings, is_preview=False)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan_progress(self, percent: int, message: str):
        self._progress_bar.setValue(percent)
        self._status_label.setText(message)

    def _on_scan_finished(self, image):
        self._progress_bar.setVisible(False)
        if image is None:
            self._status_label.setText("Scan returned no image")
            return

        self._raw_image = image
        self._scan_counter += 1
        self._status_label.setText(
            f"Scan complete: {image.size[0]}×{image.size[1]} pixels"
        )

        # Set as before image for comparisons
        self._preview_panel.set_before_image(image)

        # Record initial state for undo
        settings = self._settings_panel.get_processing_settings()
        self._undo_manager.push_state(settings, "Initial scan")

        # Apply processing
        self._do_process()

    def _on_scan_error(self, error_msg: str):
        self._progress_bar.setVisible(False)
        self._status_label.setText(f"Scan error: {error_msg}")
        QMessageBox.critical(self, "Scan Error", error_msg)

    # ── Image Processing ────────────────────────────────────────────────────

    def _on_settings_changed(self):
        """Debounced processing trigger + undo history."""
        if self._raw_image:
            self._process_timer.start()

        # Record undo history
        if not self._suppress_history:
            settings = self._settings_panel.get_processing_settings()
            self._undo_manager.push_state(settings, "Settings changed")

    def _do_process(self):
        """Process the raw image with current settings."""
        if not self._raw_image:
            return

        settings = self._settings_panel.get_processing_settings()

        self._status_label.setText("Processing...")
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)

        self._process_worker = ProcessWorker(
            self._processor, self._raw_image, settings
        )
        self._process_worker.progress.connect(self._on_process_progress)
        self._process_worker.finished.connect(self._on_process_finished)
        self._process_worker.error.connect(self._on_process_error)
        self._process_worker.start()

    def _on_process_progress(self, percent: int, message: str):
        self._progress_bar.setValue(percent)

    def _on_process_finished(self, image):
        self._progress_bar.setVisible(False)
        self._processed_image = image
        self._preview_panel.set_image(image)
        self._status_label.setText(
            f"Processed: {image.size[0]}×{image.size[1]} | "
            f"Mode: {image.mode}"
        )

    def _on_process_error(self, error_msg: str):
        self._progress_bar.setVisible(False)
        self._status_label.setText(f"Processing error: {error_msg}")

    # ── Auto Adjustments ────────────────────────────────────────────────────

    def _on_auto_levels(self):
        if not self._raw_image:
            self._status_label.setText("No image — scan first")
            return

        auto_settings = ImageProcessor.auto_levels(self._raw_image)
        # Apply to UI
        panel = self._settings_panel
        panel._slider_black_point.set_value(auto_settings.levels_master.black_point)
        panel._slider_white_point.set_value(auto_settings.levels_master.white_point)
        self._status_label.setText("Auto levels applied")
        self._on_settings_changed()

    def _on_auto_wb(self):
        if not self._raw_image:
            self._status_label.setText("No image — scan first")
            return

        balance = ImageProcessor.auto_white_balance(self._raw_image)
        panel = self._settings_panel
        panel._slider_red.set_value(balance.red_shift)
        panel._slider_green.set_value(balance.green_shift)
        panel._slider_blue.set_value(balance.blue_shift)
        self._status_label.setText("Auto white balance applied")
        self._on_settings_changed()

    def _on_reset_processing(self):
        self._settings_panel._reset_all()
        self._status_label.setText("Processing reset")

    # ── Undo / Redo ─────────────────────────────────────────────────────────

    def _on_undo(self):
        settings = self._undo_manager.undo()
        if settings:
            self._suppress_history = True
            self._restore_processing_settings(settings)
            self._suppress_history = False
            self._status_label.setText(
                f"Undo: {self._undo_manager.undo_description or 'previous state'}"
            )

    def _on_redo(self):
        settings = self._undo_manager.redo()
        if settings:
            self._suppress_history = True
            self._restore_processing_settings(settings)
            self._suppress_history = False
            self._status_label.setText(
                f"Redo: {self._undo_manager.redo_description or 'next state'}"
            )

    def _update_undo_redo_ui(self):
        """Update undo/redo menu item enabled state."""
        self._act_undo.setEnabled(self._undo_manager.can_undo)
        self._act_redo.setEnabled(self._undo_manager.can_redo)
        undo_desc = self._undo_manager.undo_description
        redo_desc = self._undo_manager.redo_description
        self._act_undo.setText(f"Undo {undo_desc}" if undo_desc else "Undo")
        self._act_redo.setText(f"Redo {redo_desc}" if redo_desc else "Redo")

    def _restore_processing_settings(self, settings: ProcessingSettings):
        """Restore all UI controls from a ProcessingSettings snapshot."""
        panel = self._settings_panel
        panel._chk_invert.setChecked(settings.invert_negative)
        panel._chk_orange_mask.setChecked(settings.orange_mask_removal)
        panel._slider_exposure.set_value(settings.exposure)
        panel._slider_brightness.set_value(settings.brightness)
        panel._slider_contrast.set_value(settings.contrast)
        panel._slider_highlights.set_value(settings.highlights)
        panel._slider_shadows.set_value(settings.shadows)
        panel._slider_saturation.set_value(settings.saturation)
        panel._slider_vibrance.set_value(settings.vibrance)
        if settings.color_balance:
            panel._slider_red.set_value(settings.color_balance.red_shift)
            panel._slider_green.set_value(settings.color_balance.green_shift)
            panel._slider_blue.set_value(settings.color_balance.blue_shift)
            panel._slider_temperature.set_value(settings.color_balance.temperature)
        if settings.levels_master:
            panel._slider_black_point.set_value(settings.levels_master.black_point)
            panel._slider_white_point.set_value(settings.levels_master.white_point)
            panel._slider_midtone.set_value(settings.levels_master.midtone)
        panel._slider_sharpness.set_value(settings.sharpness)
        panel._slider_sharpen_radius.set_value(settings.sharpen_radius)
        panel._slider_noise.set_value(settings.noise_reduction)
        panel._slider_grain.set_value(settings.grain_reduction)
        panel._chk_dust.setChecked(settings.dust_removal)
        panel._chk_scratch.setChecked(settings.scratch_removal)
        rotation_map = {0: 0, 90: 1, 180: 2, 270: 3}
        panel._combo_rotation.setCurrentIndex(rotation_map.get(settings.rotation, 0))
        panel._chk_flip_h.setChecked(settings.flip_horizontal)
        panel._chk_flip_v.setChecked(settings.flip_vertical)

        # Trigger processing with restored settings
        self._on_settings_changed()

    # ── Presets ──────────────────────────────────────────────────────────────

    def _on_save_preset(self):
        """Save current processing settings as a named preset."""
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "Save Preset", "Preset name:",
            text="My Preset"
        )
        if ok and name.strip():
            settings = self._settings_panel.get_processing_settings()
            preset = Preset(
                name=name.strip(),
                description="User-created preset",
                category="User",
                settings=settings,
            )
            path = save_preset(preset)
            self._status_label.setText(f"Preset saved: {name}")

    def _on_load_preset(self):
        """Show preset list and apply selection."""
        presets = get_builtin_presets() + list_presets()
        if not presets:
            QMessageBox.information(self, "Presets", "No saved presets found.")
            return

        names = [p.name for p in presets]
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getItem(
            self, "Load Preset", "Select preset:", names, 0, False
        )
        if ok and name:
            for p in presets:
                if p.name == name:
                    self._apply_preset(p)
                    break

    def _on_import_preset(self):
        """Import a preset from a JSON file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Preset",
            os.path.expanduser("~"),
            "JSON Files (*.json);;All Files (*.*)"
        )
        if path:
            preset = import_preset(path)
            if preset:
                self._status_label.setText(f"Preset imported: {preset.name}")
            else:
                QMessageBox.warning(self, "Import Failed",
                                     "Could not read preset file.")

    def _apply_preset(self, preset: Preset):
        """Apply a preset's settings to the UI."""
        if preset.settings:
            self._suppress_history = True
            self._restore_processing_settings(preset.settings)
            self._suppress_history = False
            self._undo_manager.push_state(
                preset.settings, f"Load preset: {preset.name}"
            )
            self._status_label.setText(f"Preset applied: {preset.name}")

    # ── Frame Detection ─────────────────────────────────────────────────────

    def _on_detect_frames(self):
        """Detect individual frames in a film strip scan."""
        if not self._raw_image:
            self._status_label.setText("No image — scan first")
            return

        self._status_label.setText("Detecting frames...")
        QApplication.processEvents()

        try:
            self._detected_frames = self._frame_detector.detect_with_opencv(
                self._raw_image, orientation="horizontal"
            )
        except Exception:
            self._detected_frames = self._frame_detector.detect_frames(
                self._raw_image, orientation="horizontal"
            )

        if self._detected_frames:
            n = len(self._detected_frames)
            self._current_frame_index = 0
            self._status_label.setText(
                f"Detected {n} frame(s). Use Scanner > Extract Frame to process."
            )

            # Show frame outlines on preview
            result = QMessageBox.question(
                self, "Frames Detected",
                f"Found {n} frame(s) in this scan.\n\n"
                f"Extract frame 1 of {n}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if result == QMessageBox.StandardButton.Yes:
                self._extract_current_frame()
        else:
            self._status_label.setText("No frames detected in image")

    def _extract_current_frame(self):
        """Extract the current detected frame and process it."""
        if not self._detected_frames or not self._raw_image:
            return

        frame = self._detected_frames[self._current_frame_index]
        extracted = extract_frame(self._raw_image, frame, deskew=True)
        self._raw_image = extracted
        self._do_process()
        self._status_label.setText(
            f"Frame {self._current_frame_index + 1} of "
            f"{len(self._detected_frames)} extracted"
        )

    def _on_auto_crop(self):
        """Auto-crop the current image to content."""
        if not self._raw_image:
            self._status_label.setText("No image — scan first")
            return

        self._raw_image = auto_crop(self._raw_image, border_percent=1.0)
        self._do_process()
        self._status_label.setText("Auto-crop applied")

    def _on_auto_deskew(self):
        """Auto-straighten the current image."""
        if not self._raw_image:
            self._status_label.setText("No image — scan first")
            return

        corrected, angle = auto_deskew(self._raw_image)
        if abs(angle) > 0.1:
            self._raw_image = corrected
            self._do_process()
            self._status_label.setText(f"Deskewed by {angle:.2f}°")
        else:
            self._status_label.setText("Image is already straight")

    # ── Before/After ────────────────────────────────────────────────────────

    def _on_toggle_before_after(self, checked: bool):
        """Toggle before/after split view."""
        if checked and self._raw_image:
            # Before = raw (unprocessed), After = current processed
            self._preview_panel.set_before_image(self._raw_image)
        self._preview_panel._act_before_after.setChecked(checked)
        self._preview_panel._on_toggle_before_after(checked)

    # ── Color Space ─────────────────────────────────────────────────────────

    def _on_set_color_space(self, space: ColorSpace):
        """Set the working color space."""
        self._color_manager.working_space = space
        for s, act in self._cs_actions.items():
            act.setChecked(s == space)
        self._status_label.setText(f"Color space: {space.value}")

    # ── Crop from Preview ───────────────────────────────────────────────────

    def _on_crop_from_preview(self, left: float, top: float,
                               right: float, bottom: float):
        """Handle crop selection made on the preview."""
        self._status_label.setText(
            f"Crop: ({left:.2f}, {top:.2f}) → ({right:.2f}, {bottom:.2f})"
        )

    # ── Session Persistence ─────────────────────────────────────────────────

    def _save_session(self):
        """Save current state for next launch."""
        try:
            proc = self._settings_panel.get_processing_settings()
            scan = self._settings_panel.get_scan_settings()

            session = get_full_session_dict(
                scan_settings_dict={
                    "resolution_idx": self._settings_panel._combo_resolution.currentIndex(),
                    "source_idx": self._settings_panel._combo_source.currentIndex(),
                    "color_idx": self._settings_panel._combo_color.currentIndex(),
                    "depth_idx": self._settings_panel._combo_depth.currentIndex(),
                    "area_preset_idx": self._settings_panel._combo_area_preset.currentIndex(),
                },
                processing_dict=_settings_to_dict(proc),
                ui_state={
                    "output_dir": self._settings_panel.get_output_directory(),
                    "output_format_idx": self._settings_panel._combo_format.currentIndex(),
                    "filename_pattern": self._settings_panel.get_filename_pattern(),
                    "window_width": self.width(),
                    "window_height": self.height(),
                    "demo_mode": self._demo_mode,
                    "color_space": self._color_manager.working_space.value,
                },
            )
            save_session(session)
        except Exception as e:
            logger.warning(f"Session save failed: {e}")

    def _restore_session(self):
        """Restore settings from last session."""
        data = load_session()
        if not data:
            return

        try:
            scan_dict, proc_dict, ui_dict = unpack_session(data)

            # Restore scan settings
            if scan_dict:
                panel = self._settings_panel
                if "resolution_idx" in scan_dict:
                    panel._combo_resolution.setCurrentIndex(
                        scan_dict["resolution_idx"]
                    )
                if "source_idx" in scan_dict:
                    panel._combo_source.setCurrentIndex(
                        scan_dict["source_idx"]
                    )
                if "color_idx" in scan_dict:
                    panel._combo_color.setCurrentIndex(
                        scan_dict["color_idx"]
                    )
                if "depth_idx" in scan_dict:
                    panel._combo_depth.setCurrentIndex(
                        scan_dict["depth_idx"]
                    )

            # Restore processing settings
            if proc_dict:
                settings = _dict_to_settings(proc_dict)
                self._suppress_history = True
                self._restore_processing_settings(settings)
                self._suppress_history = False

            # Restore UI state
            if ui_dict:
                if "output_dir" in ui_dict:
                    self._settings_panel.set_output_directory(ui_dict["output_dir"])
                if "output_format_idx" in ui_dict:
                    self._settings_panel._combo_format.setCurrentIndex(
                        ui_dict["output_format_idx"]
                    )
                if "filename_pattern" in ui_dict:
                    self._settings_panel._txt_filename.setText(
                        ui_dict["filename_pattern"]
                    )
                if "window_width" in ui_dict and "window_height" in ui_dict:
                    self.resize(ui_dict["window_width"], ui_dict["window_height"])
                if "color_space" in ui_dict:
                    for space in ColorSpace:
                        if space.value == ui_dict["color_space"]:
                            self._on_set_color_space(space)
                            break

            logger.info("Session restored from last run")
        except Exception as e:
            logger.warning(f"Session restore failed: {e}")

    # ── File Operations ─────────────────────────────────────────────────────

    def _on_open_image(self):
        """Open an existing image file for processing."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Image",
            os.path.expanduser("~"),
            "Images (*.tif *.tiff *.png *.jpg *.jpeg *.bmp);;All Files (*.*)"
        )
        if file_path:
            try:
                img = Image.open(file_path)
                img.load()
                self._raw_image = img
                self._preview_panel.set_before_image(img)
                self._status_label.setText(
                    f"Loaded: {os.path.basename(file_path)} "
                    f"({img.size[0]}×{img.size[1]})"
                )
                settings = self._settings_panel.get_processing_settings()
                self._undo_manager.push_state(settings, "Image loaded")
                self._do_process()
            except Exception as e:
                QMessageBox.critical(self, "Open Error",
                                      f"Failed to open image: {e}")

    def _on_save(self):
        """Save processed image."""
        if not self._processed_image:
            self._status_label.setText("No image to save")
            return

        output_dir = self._settings_panel.get_output_directory()
        fmt = self._settings_panel.get_output_format()
        pattern = self._settings_panel.get_filename_pattern()

        ext_map = {"tiff": ".tif", "png": ".png", "jpeg": ".jpg", "bmp": ".bmp"}
        ext = ext_map.get(fmt, ".tif")

        # Generate filename
        try:
            filename = pattern.format(n=self._scan_counter)
        except (KeyError, IndexError, ValueError):
            filename = f"scan_{self._scan_counter:04d}"

        # Use save dialog
        default_path = os.path.join(output_dir, filename + ext)
        filter_map = {
            "tiff": "TIFF Files (*.tif *.tiff)",
            "png": "PNG Files (*.png)",
            "jpeg": "JPEG Files (*.jpg *.jpeg)",
            "bmp": "BMP Files (*.bmp)",
        }

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Scan",
            default_path,
            f"{filter_map.get(fmt, 'All Files')};;All Files (*.*)"
        )

        if file_path:
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                save_kwargs = {}
                if fmt == "tiff":
                    save_kwargs["compression"] = "tiff_lzw"
                elif fmt == "jpeg":
                    save_kwargs["quality"] = 95

                # Embed EXIF metadata
                scan_settings = self._settings_panel.get_scan_settings()
                metadata = ScanMetadata(
                    scanner_name=self._scanner_label.text() if self._scanner else "",
                    resolution_dpi=scan_settings.resolution,
                    bit_depth=scan_settings.bit_depth,
                    scan_source="Transparency" if scan_settings.source == ScanSource.TRANSPARENCY else "Flatbed",
                    color_mode=scan_settings.color_mode.value,
                    frame_number=self._scan_counter,
                )
                # Get film profile if one is selected
                try:
                    film_name = self._settings_panel._combo_film.currentText()
                    profile = get_profile(film_name)
                    if profile:
                        metadata.film_profile = profile.name
                        metadata.film_manufacturer = profile.manufacturer
                        metadata.film_iso = profile.iso
                        metadata.film_type = profile.category
                except Exception:
                    pass

                img_to_save = apply_exif_to_image(
                    self._processed_image.copy(), metadata
                )

                # Embed ICC profile
                img_to_save = self._color_manager.embed_profile(img_to_save)

                img_to_save.save(file_path, **save_kwargs)
                self._status_label.setText(f"Saved: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save: {e}")

    def _on_save_raw(self):
        """Save raw unprocessed scan."""
        if not self._raw_image:
            self._status_label.setText("No raw image to save")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Raw Scan",
            os.path.join(os.path.expanduser("~"), "raw_scan.tif"),
            "TIFF Files (*.tif *.tiff);;PNG Files (*.png);;All Files (*.*)"
        )
        if file_path:
            try:
                self._raw_image.save(file_path, compression="tiff_lzw")
                self._status_label.setText(f"Raw saved: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save: {e}")

    def _on_batch_scan(self):
        """Simple batch scanning — scan multiple frames in sequence."""
        if not self._scanner or not self._scanner.is_connected:
            QMessageBox.information(
                self, "Batch Scan",
                "Connect to a scanner first (Scanner > Connect)"
            )
            return

        output_dir = self._settings_panel.get_output_directory()
        if not output_dir:
            output_dir = QFileDialog.getExistingDirectory(
                self, "Select Output Directory for Batch Scan"
            )
            if not output_dir:
                return
            self._settings_panel.set_output_directory(output_dir)

        os.makedirs(output_dir, exist_ok=True)

        result = QMessageBox.question(
            self, "Batch Scan",
            "Batch scanning will perform multiple scans.\n"
            "After each scan, you'll be asked to continue or stop.\n\n"
            "Position your film and click OK to start.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )

        if result == QMessageBox.StandardButton.Ok:
            self._batch_loop(output_dir)

    def _batch_loop(self, output_dir: str):
        """Execute batch scan loop."""
        scan_num = 1
        fmt = self._settings_panel.get_output_format()
        ext_map = {"tiff": ".tif", "png": ".png", "jpeg": ".jpg", "bmp": ".bmp"}
        ext = ext_map.get(fmt, ".tif")

        while True:
            # Scan
            self._status_label.setText(f"Batch scan #{scan_num}...")
            QApplication.processEvents()

            settings = self._settings_panel.get_scan_settings()

            try:
                img = self._scanner.scan(
                    settings,
                    progress_callback=lambda p, m: (
                        self._progress_bar.setValue(p),
                        self._status_label.setText(m),
                        QApplication.processEvents(),
                    )
                )
            except Exception as e:
                QMessageBox.critical(self, "Scan Error", str(e))
                break

            if img:
                self._raw_image = img
                self._scan_counter += 1
                proc_settings = self._settings_panel.get_processing_settings()
                processed = self._processor.process(img, proc_settings)

                # Save
                filename = f"batch_{scan_num:04d}{ext}"
                filepath = os.path.join(output_dir, filename)
                save_kwargs = {}
                if fmt == "tiff":
                    save_kwargs["compression"] = "tiff_lzw"
                elif fmt == "jpeg":
                    save_kwargs["quality"] = 95

                processed.save(filepath, **save_kwargs)

                self._processed_image = processed
                self._preview_panel.set_image(processed)
                self._status_label.setText(f"Saved: {filename}")

            # Ask to continue
            again = QMessageBox.question(
                self, "Batch Scan",
                f"Scan #{scan_num} complete.\n"
                f"Position next frame and click Yes to continue,\n"
                f"or No to finish batch.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if again != QMessageBox.StandardButton.Yes:
                break

            scan_num += 1

        self._status_label.setText(f"Batch complete: {scan_num} scans")
        self._progress_bar.setVisible(False)

    # ── Help ────────────────────────────────────────────────────────────────

    def _on_bug_report(self):
        """Open the Bug Report / Log Viewer dialog."""
        dialog = BugReportDialog(self)
        dialog.exec()

    def _on_export_logs(self):
        """Export all log files to a folder."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Folder to Export Logs"
        )
        if directory:
            try:
                out_dir = os.path.join(directory, "skenner_logs")
                export_full_log_bundle(out_dir)
                QMessageBox.information(
                    self, "Logs Exported",
                    f"All logs and system info exported to:\n{out_dir}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error", f"Failed to export: {e}"
                )

    def _on_open_log_folder(self):
        """Open the log directory in the file explorer."""
        log_dir = get_log_dir()
        os.makedirs(log_dir, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(log_dir)
        else:
            import subprocess
            subprocess.Popen(["xdg-open", log_dir])

    def _on_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    # ── Window Events ───────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent):
        """Clean up on close, save session."""
        # Save session state for next launch
        self._save_session()

        if self._scanner and self._scanner.is_connected:
            self._scanner.disconnect()
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.quit()
            self._scan_worker.wait(2000)
        if self._process_worker and self._process_worker.isRunning():
            self._process_worker.quit()
            self._process_worker.wait(2000)
        event.accept()


def run_app():
    """Entry point to launch the application."""
    # Setup file-based logging FIRST
    log_file = setup_file_logging(level=logging.DEBUG)

    # Install crash handler for unhandled exceptions
    install_crash_handler()

    # Clean up old logs on startup
    try:
        clear_old_logs(days=30)
    except Exception:
        pass

    # Console logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info(f"Application starting, log file: {log_file}")

    app = QApplication(sys.argv)
    app.setApplicationName("SkennerOpt")
    app.setOrganizationName("SkennerOpt")

    # Apply Fusion + dark theme
    app.setStyle("Fusion")
    app.setStyleSheet(T.app_stylesheet())

    # Show splash screen
    splash = _create_splash_screen()
    splash.show()
    app.processEvents()

    splash.showMessage("  Initializing scanner...",
                       Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                       QColor(T.FG_SECONDARY))
    app.processEvents()

    window = MainWindow()

    splash.showMessage("  Ready",
                       Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                       QColor(T.ACCENT))
    app.processEvents()

    window.show()
    splash.finish(window)

    sys.exit(app.exec())


def _create_splash_screen() -> QSplashScreen:
    """Create a branded splash screen."""
    from PyQt6.QtGui import QPainter, QFont as _QFont, QColor as _QColor, QLinearGradient

    width, height = 480, 280
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(T.BG_BASE))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Background gradient band
    grad = QLinearGradient(0, 0, width, 0)
    grad.setColorAt(0, QColor(T.ACCENT))
    grad.setColorAt(1, QColor("#2a5db0"))
    painter.fillRect(0, 0, width, 4, QBrush(grad))

    # Film icon + title
    font_title = _QFont(T.FONT_FAMILY, 28, _QFont.Weight.Bold)
    painter.setFont(font_title)
    painter.setPen(QColor(T.ACCENT))
    painter.drawText(40, 90, f"{T.ICON_FILM}  SkennerOpt")

    # Subtitle
    font_sub = _QFont(T.FONT_FAMILY, 12)
    painter.setFont(font_sub)
    painter.setPen(QColor(T.FG_SECONDARY))
    painter.drawText(44, 120, "Professional Film Scanner")

    # Version
    font_ver = _QFont(T.FONT_FAMILY, 10)
    painter.setFont(font_ver)
    painter.setPen(QColor(T.FG_MUTED))
    painter.drawText(44, 148, "Version 2.0.0")

    # Decorative film strip
    painter.setPen(QColor(T.BORDER))
    for i in range(12):
        x = 40 + i * 36
        painter.drawRect(x, 180, 28, 20)

    # Bottom gradient band
    painter.fillRect(0, height - 4, width, 4, QBrush(grad))

    painter.end()

    splash = QSplashScreen(pixmap)
    splash.setWindowFlags(
        Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint
    )
    return splash
