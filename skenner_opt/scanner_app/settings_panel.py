"""
Settings panel UI providing controls for all scan and processing parameters.
Organized in collapsible sections similar to VueScan's interface.
"""

import logging
from typing import Optional
from functools import partial

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QSlider, QSpinBox, QDoubleSpinBox, QComboBox,
    QCheckBox, QPushButton, QScrollArea, QFrame, QSizePolicy,
    QToolButton, QFileDialog, QLineEdit, QGraphicsOpacityEffect,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QIcon, QFont

from .scanner import ScanSettings, ScanArea, ScanSource, ColorMode
from .image_processor import ProcessingSettings, LevelsAdjustment, ColorBalance
from .film_profiles import (
    get_all_profiles, get_all_categories, get_profiles_by_category,
    get_profile, FilmProfile,
)
from . import theme as T

logger = logging.getLogger(__name__)


class CollapsibleSection(QWidget):
    """A collapsible section with header button and animated content area."""

    def __init__(self, title: str, parent=None, collapsed=False, icon: str = ""):
        super().__init__(parent)
        self._collapsed = collapsed
        self._icon = icon

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header button
        self._header = QToolButton(self)
        self._update_header_text(not collapsed)
        self._header.setCheckable(True)
        self._header.setChecked(not collapsed)
        self._header.setStyleSheet(T.collapsible_header_style())
        self._header.setSizePolicy(QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Fixed)
        self._header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._header.toggled.connect(self._on_toggle)
        layout.addWidget(self._header)

        # Content frame
        self._content = QFrame(self)
        self._content.setStyleSheet(T.collapsible_body_style())
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(10, 8, 10, 8)
        self._content_layout.setSpacing(5)
        self._content.setVisible(not collapsed)
        layout.addWidget(self._content)

        self._title = title

    def _update_header_text(self, expanded: bool):
        arrow = T.ICON_EXPAND if expanded else T.ICON_COLLAPSE
        icon_part = f"{self._icon}  " if self._icon else ""
        self._header.setText(f"  {arrow}   {icon_part}{self._title}")

    @property
    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def add_widget(self, widget: QWidget):
        self._content_layout.addWidget(widget)

    def _on_toggle(self, checked: bool):
        self._collapsed = not checked
        self._content.setVisible(checked)
        self._update_header_text(checked)


class LabeledSlider(QWidget):
    """Slider with label and value display."""

    value_changed = pyqtSignal(float)

    def __init__(self, label: str, min_val: float, max_val: float,
                 default: float = 0, step: float = 1,
                 suffix: str = "", parent=None):
        super().__init__(parent)
        self._scale = 1.0 / step if step < 1 else 1
        self._suffix = suffix

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        lbl = QLabel(label)
        lbl.setFixedWidth(86)
        lbl.setStyleSheet(T.label_style_secondary())
        layout.addWidget(lbl)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(int(min_val * self._scale))
        self._slider.setMaximum(int(max_val * self._scale))
        self._slider.setValue(int(default * self._scale))
        self._slider.setStyleSheet(T.slider_style())
        self._slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self._slider, 1)

        self._value_label = QLabel(f"{default}{suffix}")
        self._value_label.setFixedWidth(52)
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._value_label.setStyleSheet(T.value_label_style())
        layout.addWidget(self._value_label)

    def _on_slider_changed(self, value: int):
        real_val = value / self._scale
        self._value_label.setText(f"{real_val:.1f}{self._suffix}" if self._scale > 1
                                  else f"{int(real_val)}{self._suffix}")
        self.value_changed.emit(real_val)

    def get_value(self) -> float:
        return self._slider.value() / self._scale

    def set_value(self, val: float):
        self._slider.blockSignals(True)
        self._slider.setValue(int(val * self._scale))
        self._value_label.setText(f"{val:.1f}{self._suffix}" if self._scale > 1
                                  else f"{int(val)}{self._suffix}")
        self._slider.blockSignals(False)

    def reset(self):
        default = (self._slider.minimum() + self._slider.maximum()) // 2
        self._slider.setValue(0 if self._slider.minimum() <= 0 <= self._slider.maximum() else default)


class SettingsPanel(QWidget):
    """
    Complete settings panel with all scan and processing controls.
    Emits signals when any setting changes.
    """

    settings_changed = pyqtSignal()
    scan_requested = pyqtSignal()
    preview_requested = pyqtSignal()
    save_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(360)
        self._setup_ui()

    def _setup_ui(self):
        # Main scroll area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(T.scroll_area_style())

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # ── Action Buttons ──────────────────────────────────────────────
        btn_frame = QFrame()
        btn_frame.setStyleSheet(f"background: {T.BG_SURFACE}; border-bottom: 1px solid {T.BORDER_SUBTLE};")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(10, 10, 10, 10)
        btn_layout.setSpacing(8)

        self._btn_preview = QPushButton(f"{T.ICON_PREVIEW}  Preview")
        self._btn_preview.setStyleSheet(T.preview_button_style())
        self._btn_preview.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_preview.clicked.connect(self.preview_requested.emit)
        btn_layout.addWidget(self._btn_preview)

        self._btn_scan = QPushButton(f"{T.ICON_SCAN}  Scan")
        self._btn_scan.setStyleSheet(T.primary_button_style())
        self._btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_scan.clicked.connect(self.scan_requested.emit)
        btn_layout.addWidget(self._btn_scan)

        self._btn_save = QPushButton(f"{T.ICON_SAVE}  Save")
        self._btn_save.setStyleSheet(T.success_button_style())
        self._btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save.clicked.connect(self.save_requested.emit)
        btn_layout.addWidget(self._btn_save)

        container_layout.addWidget(btn_frame)

        # ── Scanner Section ─────────────────────────────────────────────
        scanner_section = CollapsibleSection("Scanner Settings", icon=T.ICON_SETTINGS)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        # Source
        self._combo_source = QComboBox()
        self._combo_source.addItems(["Transparency (Film)", "Flatbed"])
        self._combo_source.setStyleSheet(T.combo_style())
        self._combo_source.currentIndexChanged.connect(self._on_source_changed)
        form.addRow(self._styled_label("Source:"), self._combo_source)

        # Resolution
        self._combo_resolution = QComboBox()
        self._combo_resolution.addItems([
            "150 dpi (Preview)", "300 dpi (Draft)", "600 dpi (Good)",
            "1200 dpi (Fine)", "2400 dpi (High)", "3200 dpi (Very High)",
            "4800 dpi (Maximum)"
        ])
        self._combo_resolution.setCurrentIndex(4)  # Default 2400
        self._combo_resolution.setStyleSheet(T.combo_style())
        self._combo_resolution.currentIndexChanged.connect(
            lambda: self.settings_changed.emit()
        )
        form.addRow(self._styled_label("Resolution:"), self._combo_resolution)

        # Color mode
        self._combo_color = QComboBox()
        self._combo_color.addItems(["Color (RGB)", "Grayscale", "Black & White"])
        self._combo_color.setStyleSheet(T.combo_style())
        self._combo_color.currentIndexChanged.connect(
            lambda: self.settings_changed.emit()
        )
        form.addRow(self._styled_label("Color Mode:"), self._combo_color)

        # Bit depth
        self._combo_depth = QComboBox()
        self._combo_depth.addItems(["24-bit (8 per ch)", "48-bit (16 per ch)"])
        self._combo_depth.setCurrentIndex(1)
        self._combo_depth.setStyleSheet(T.combo_style())
        form.addRow(self._styled_label("Bit Depth:"), self._combo_depth)

        fw = QWidget()
        fw.setLayout(form)
        scanner_section.add_widget(fw)
        container_layout.addWidget(scanner_section)

        # ── Scan Area Section ───────────────────────────────────────────
        area_section = CollapsibleSection("Scan Area")

        self._combo_area_preset = QComboBox()
        self._combo_area_preset.addItems([
            "Full Transparency Unit", "35mm Film Strip",
            "35mm Slide", "120 Medium Format",
            "Full Flatbed", "Custom"
        ])
        self._combo_area_preset.setCurrentIndex(1)
        self._combo_area_preset.setStyleSheet(T.combo_style())
        self._combo_area_preset.currentIndexChanged.connect(self._on_area_preset_changed)
        area_section.add_widget(self._combo_area_preset)

        area_form = QFormLayout()
        area_form.setSpacing(4)

        self._spin_left = self._create_area_spin(0, 0, 8.5)
        self._spin_top = self._create_area_spin(0, 0, 11.7)
        self._spin_width = self._create_area_spin(6.0, 0.1, 8.5)
        self._spin_height = self._create_area_spin(1.5, 0.1, 11.7)

        area_form.addRow(self._styled_label("Left (in):"), self._spin_left)
        area_form.addRow(self._styled_label("Top (in):"), self._spin_top)
        area_form.addRow(self._styled_label("Width (in):"), self._spin_width)
        area_form.addRow(self._styled_label("Height (in):"), self._spin_height)

        aw = QWidget()
        aw.setLayout(area_form)
        area_section.add_widget(aw)
        container_layout.addWidget(area_section)

        # ── Film Profile Section ────────────────────────────────────────
        film_section = CollapsibleSection("Film Profile", icon=T.ICON_FILM)

        self._combo_film_category = QComboBox()
        self._combo_film_category.addItems(get_all_categories())
        self._combo_film_category.setCurrentText("Color Negative")
        self._combo_film_category.setStyleSheet(T.combo_style())
        self._combo_film_category.currentTextChanged.connect(self._on_film_category_changed)
        film_section.add_widget(self._combo_film_category)

        self._combo_film = QComboBox()
        self._combo_film.setStyleSheet(T.combo_style())
        self._combo_film.currentTextChanged.connect(self._on_film_changed)
        film_section.add_widget(self._combo_film)

        self._lbl_film_desc = QLabel("")
        self._lbl_film_desc.setWordWrap(True)
        self._lbl_film_desc.setStyleSheet(T.label_style_caption())
        film_section.add_widget(self._lbl_film_desc)

        # Populate film list
        self._on_film_category_changed("Color Negative")

        container_layout.addWidget(film_section)

        # ── Negative Inversion ──────────────────────────────────────────
        neg_section = CollapsibleSection("Negative Inversion", icon=T.ICON_NEGATIVE)

        self._chk_invert = QCheckBox("Invert Negative")
        self._chk_invert.setChecked(True)
        self._chk_invert.setStyleSheet(T.checkbox_style())
        self._chk_invert.stateChanged.connect(lambda: self.settings_changed.emit())
        neg_section.add_widget(self._chk_invert)

        self._chk_orange_mask = QCheckBox("Remove Orange Mask (C-41)")
        self._chk_orange_mask.setChecked(True)
        self._chk_orange_mask.setStyleSheet(T.checkbox_style())
        self._chk_orange_mask.stateChanged.connect(lambda: self.settings_changed.emit())
        neg_section.add_widget(self._chk_orange_mask)

        container_layout.addWidget(neg_section)

        # ── Exposure & Tone ───────────────────────────────────────────
        tone_section = CollapsibleSection("Exposure & Tone", icon=T.ICON_EXPOSURE)

        self._slider_exposure = LabeledSlider("Exposure", -5.0, 5.0, 0, 0.1, " EV")
        self._slider_exposure.value_changed.connect(lambda: self.settings_changed.emit())
        tone_section.add_widget(self._slider_exposure)

        self._slider_brightness = LabeledSlider("Brightness", -100, 100, 0)
        self._slider_brightness.value_changed.connect(lambda: self.settings_changed.emit())
        tone_section.add_widget(self._slider_brightness)

        self._slider_contrast = LabeledSlider("Contrast", -100, 100, 0)
        self._slider_contrast.value_changed.connect(lambda: self.settings_changed.emit())
        tone_section.add_widget(self._slider_contrast)

        self._slider_highlights = LabeledSlider("Highlights", -100, 100, 0)
        self._slider_highlights.value_changed.connect(lambda: self.settings_changed.emit())
        tone_section.add_widget(self._slider_highlights)

        self._slider_shadows = LabeledSlider("Shadows", -100, 100, 0)
        self._slider_shadows.value_changed.connect(lambda: self.settings_changed.emit())
        tone_section.add_widget(self._slider_shadows)

        container_layout.addWidget(tone_section)

        # ── Color Adjustments ───────────────────────────────────────────
        color_section = CollapsibleSection("Color", collapsed=True, icon=T.ICON_COLOR)

        self._slider_saturation = LabeledSlider("Saturation", 0, 3.0, 1.0, 0.05)
        self._slider_saturation.value_changed.connect(lambda: self.settings_changed.emit())
        color_section.add_widget(self._slider_saturation)

        self._slider_vibrance = LabeledSlider("Vibrance", -100, 100, 0)
        self._slider_vibrance.value_changed.connect(lambda: self.settings_changed.emit())
        color_section.add_widget(self._slider_vibrance)

        self._slider_temperature = LabeledSlider("Temperature", -100, 100, 0)
        self._slider_temperature.value_changed.connect(lambda: self.settings_changed.emit())
        color_section.add_widget(self._slider_temperature)

        self._slider_red = LabeledSlider("Red", -100, 100, 0)
        self._slider_red.value_changed.connect(lambda: self.settings_changed.emit())
        color_section.add_widget(self._slider_red)

        self._slider_green = LabeledSlider("Green", -100, 100, 0)
        self._slider_green.value_changed.connect(lambda: self.settings_changed.emit())
        color_section.add_widget(self._slider_green)

        self._slider_blue = LabeledSlider("Blue", -100, 100, 0)
        self._slider_blue.value_changed.connect(lambda: self.settings_changed.emit())
        color_section.add_widget(self._slider_blue)

        btn_auto_wb = QPushButton(f"{T.ICON_COLOR}  Auto White Balance")
        btn_auto_wb.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_auto_wb.setStyleSheet(T.secondary_button_style())
        btn_auto_wb.clicked.connect(self._on_auto_wb)
        color_section.add_widget(btn_auto_wb)

        container_layout.addWidget(color_section)

        # ── Levels ──────────────────────────────────────────────────────
        levels_section = CollapsibleSection("Levels", collapsed=True, icon=T.ICON_LEVELS)

        self._slider_black_point = LabeledSlider("Black Point", 0, 255, 0)
        self._slider_black_point.value_changed.connect(lambda: self.settings_changed.emit())
        levels_section.add_widget(self._slider_black_point)

        self._slider_white_point = LabeledSlider("White Point", 0, 255, 255)
        self._slider_white_point.value_changed.connect(lambda: self.settings_changed.emit())
        levels_section.add_widget(self._slider_white_point)

        self._slider_midtone = LabeledSlider("Midtone (γ)", 0.1, 4.0, 1.0, 0.05)
        self._slider_midtone.value_changed.connect(lambda: self.settings_changed.emit())
        levels_section.add_widget(self._slider_midtone)

        btn_auto_levels = QPushButton(f"{T.ICON_LEVELS}  Auto Levels")
        btn_auto_levels.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_auto_levels.setStyleSheet(T.secondary_button_style())
        btn_auto_levels.clicked.connect(self._on_auto_levels)
        levels_section.add_widget(btn_auto_levels)

        container_layout.addWidget(levels_section)

        # ── Sharpening & Noise ──────────────────────────────────────────
        detail_section = CollapsibleSection("Detail", collapsed=True, icon=T.ICON_DETAIL)

        self._slider_sharpness = LabeledSlider("Sharpness", 0, 500, 0)
        self._slider_sharpness.value_changed.connect(lambda: self.settings_changed.emit())
        detail_section.add_widget(self._slider_sharpness)

        self._slider_sharpen_radius = LabeledSlider("Sharp Radius", 0.1, 10.0, 1.0, 0.1)
        self._slider_sharpen_radius.value_changed.connect(lambda: self.settings_changed.emit())
        detail_section.add_widget(self._slider_sharpen_radius)

        self._slider_noise = LabeledSlider("Noise Reduc.", 0, 100, 0)
        self._slider_noise.value_changed.connect(lambda: self.settings_changed.emit())
        detail_section.add_widget(self._slider_noise)

        self._slider_grain = LabeledSlider("Grain Reduc.", 0, 100, 0)
        self._slider_grain.value_changed.connect(lambda: self.settings_changed.emit())
        detail_section.add_widget(self._slider_grain)

        self._chk_dust = QCheckBox("Dust Removal")
        self._chk_dust.setStyleSheet(T.checkbox_style())
        self._chk_dust.stateChanged.connect(lambda: self.settings_changed.emit())
        detail_section.add_widget(self._chk_dust)

        self._chk_scratch = QCheckBox("Scratch Removal")
        self._chk_scratch.setStyleSheet(T.checkbox_style())
        self._chk_scratch.stateChanged.connect(lambda: self.settings_changed.emit())
        detail_section.add_widget(self._chk_scratch)

        container_layout.addWidget(detail_section)

        # ── Rotation & Flip ─────────────────────────────────────────────
        transform_section = CollapsibleSection("Transform", collapsed=True, icon=T.ICON_TRANSFORM)

        rot_layout = QHBoxLayout()
        self._combo_rotation = QComboBox()
        self._combo_rotation.addItems(["0°", "90° CW", "180°", "90° CCW"])
        self._combo_rotation.setStyleSheet(T.combo_style())
        self._combo_rotation.currentIndexChanged.connect(
            lambda: self.settings_changed.emit()
        )
        rot_lbl = QLabel("Rotation:")
        rot_lbl.setStyleSheet(T.label_style_secondary())
        rot_layout.addWidget(rot_lbl)
        rot_layout.addWidget(self._combo_rotation, 1)
        rw = QWidget()
        rw.setLayout(rot_layout)
        transform_section.add_widget(rw)

        self._chk_flip_h = QCheckBox("Flip Horizontal")
        self._chk_flip_h.setStyleSheet(T.checkbox_style())
        self._chk_flip_h.stateChanged.connect(lambda: self.settings_changed.emit())
        transform_section.add_widget(self._chk_flip_h)

        self._chk_flip_v = QCheckBox("Flip Vertical")
        self._chk_flip_v.setStyleSheet(T.checkbox_style())
        self._chk_flip_v.stateChanged.connect(lambda: self.settings_changed.emit())
        transform_section.add_widget(self._chk_flip_v)

        container_layout.addWidget(transform_section)

        # ── Output Section ──────────────────────────────────────────────
        output_section = CollapsibleSection("Output", icon=T.ICON_SAVE)

        out_form = QFormLayout()
        out_form.setSpacing(8)

        self._combo_format = QComboBox()
        self._combo_format.addItems(["TIFF (Lossless)", "PNG (Lossless)",
                                      "JPEG (95%)", "BMP"])
        self._combo_format.setStyleSheet(T.combo_style())
        fmt_lbl = QLabel("Format:")
        fmt_lbl.setStyleSheet(T.label_style_secondary())
        out_form.addRow(fmt_lbl, self._combo_format)

        out_path_layout = QHBoxLayout()
        self._txt_output_dir = QLineEdit()
        self._txt_output_dir.setPlaceholderText("Select output directory...")
        self._txt_output_dir.setStyleSheet(T.input_style())
        out_path_layout.addWidget(self._txt_output_dir, 1)

        btn_browse = QPushButton(T.ICON_FOLDER)
        btn_browse.setFixedWidth(34)
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.setStyleSheet(T.secondary_button_style())
        btn_browse.clicked.connect(self._on_browse_output)
        out_path_layout.addWidget(btn_browse)

        out_path_w = QWidget()
        out_path_w.setLayout(out_path_layout)
        dir_lbl = QLabel("Directory:")
        dir_lbl.setStyleSheet(T.label_style_secondary())
        out_form.addRow(dir_lbl, out_path_w)

        self._txt_filename = QLineEdit("scan_{n:04d}")
        self._txt_filename.setStyleSheet(T.input_style())
        fn_lbl = QLabel("Filename:")
        fn_lbl.setStyleSheet(T.label_style_secondary())
        out_form.addRow(fn_lbl, self._txt_filename)

        ow = QWidget()
        ow.setLayout(out_form)
        output_section.add_widget(ow)
        container_layout.addWidget(output_section)

        # ── Reset Button ────────────────────────────────────────────────
        btn_reset = QPushButton(f"{T.ICON_RESET}  Reset All Settings")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.setStyleSheet(T.danger_button_style())
        btn_reset.clicked.connect(self._reset_all)
        container_layout.addWidget(btn_reset)

        # Spacer
        container_layout.addStretch()

        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    # ── Getters ─────────────────────────────────────────────────────────────

    def get_scan_settings(self) -> ScanSettings:
        """Build ScanSettings from current UI state."""
        resolution_map = {0: 150, 1: 300, 2: 600, 3: 1200, 4: 2400, 5: 3200, 6: 4800}
        res = resolution_map.get(self._combo_resolution.currentIndex(), 2400)

        color_map = {0: ColorMode.COLOR, 1: ColorMode.GRAYSCALE, 2: ColorMode.BLACK_WHITE}
        color = color_map.get(self._combo_color.currentIndex(), ColorMode.COLOR)

        source = (ScanSource.TRANSPARENCY if self._combo_source.currentIndex() == 0
                  else ScanSource.FLATBED)

        area = ScanArea(
            left=self._spin_left.value(),
            top=self._spin_top.value(),
            width=self._spin_width.value(),
            height=self._spin_height.value(),
        )

        bit_depth = 48 if self._combo_depth.currentIndex() == 1 else 24

        return ScanSettings(
            resolution=res,
            color_mode=color,
            source=source,
            scan_area=area,
            bit_depth=bit_depth,
        )

    def get_processing_settings(self) -> ProcessingSettings:
        """Build ProcessingSettings from current UI state."""
        rotation_map = {0: 0, 1: 90, 2: 180, 3: 270}

        settings = ProcessingSettings(
            invert_negative=self._chk_invert.isChecked(),
            orange_mask_removal=self._chk_orange_mask.isChecked(),
            # Levels
            levels_master=LevelsAdjustment(
                black_point=int(self._slider_black_point.get_value()),
                white_point=int(self._slider_white_point.get_value()),
                midtone=self._slider_midtone.get_value(),
            ),
            # Color
            color_balance=ColorBalance(
                red_shift=self._slider_red.get_value(),
                green_shift=self._slider_green.get_value(),
                blue_shift=self._slider_blue.get_value(),
                temperature=self._slider_temperature.get_value(),
            ),
            saturation=self._slider_saturation.get_value(),
            vibrance=self._slider_vibrance.get_value(),
            # Tone
            exposure=self._slider_exposure.get_value(),
            brightness=self._slider_brightness.get_value(),
            contrast=self._slider_contrast.get_value(),
            highlights=self._slider_highlights.get_value(),
            shadows=self._slider_shadows.get_value(),
            # Detail
            sharpness=self._slider_sharpness.get_value(),
            sharpen_radius=self._slider_sharpen_radius.get_value(),
            noise_reduction=self._slider_noise.get_value(),
            grain_reduction=self._slider_grain.get_value(),
            dust_removal=self._chk_dust.isChecked(),
            scratch_removal=self._chk_scratch.isChecked(),
            # Transform
            rotation=rotation_map.get(self._combo_rotation.currentIndex(), 0),
            flip_horizontal=self._chk_flip_h.isChecked(),
            flip_vertical=self._chk_flip_v.isChecked(),
        )

        return settings

    def get_output_format(self) -> str:
        fmt_map = {0: "tiff", 1: "png", 2: "jpeg", 3: "bmp"}
        return fmt_map.get(self._combo_format.currentIndex(), "tiff")

    def get_output_directory(self) -> str:
        return self._txt_output_dir.text()

    def get_filename_pattern(self) -> str:
        return self._txt_filename.text()

    # ── Setters ─────────────────────────────────────────────────────────────

    def apply_film_profile(self, profile: FilmProfile):
        """Apply a film profile's settings to the UI controls."""
        proc = profile.processing

        self._chk_invert.setChecked(proc.invert_negative)
        self._chk_orange_mask.setChecked(proc.orange_mask_removal)

        self._slider_saturation.set_value(proc.saturation)
        self._slider_contrast.set_value(proc.contrast)
        self._slider_brightness.set_value(proc.brightness)

        if proc.color_balance:
            self._slider_red.set_value(proc.color_balance.red_shift)
            self._slider_green.set_value(proc.color_balance.green_shift)
            self._slider_blue.set_value(proc.color_balance.blue_shift)
            self._slider_temperature.set_value(proc.color_balance.temperature)

        if proc.vibrance != 0:
            self._slider_vibrance.set_value(proc.vibrance)

        self.settings_changed.emit()

    def set_output_directory(self, path: str):
        self._txt_output_dir.setText(path)

    # ── Event Handlers ──────────────────────────────────────────────────────

    def _on_source_changed(self, index: int):
        if index == 0:  # Transparency
            self._combo_area_preset.setCurrentIndex(1)  # 35mm film strip
        else:
            self._combo_area_preset.setCurrentIndex(4)  # Full flatbed
        self.settings_changed.emit()

    def _on_area_preset_changed(self, index: int):
        area_map = {
            0: ScanArea.full_transparency(),
            1: ScanArea.film_35mm(),
            2: ScanArea.film_35mm_slide(),
            3: ScanArea.film_120(),
            4: ScanArea.full_flatbed(),
        }
        area = area_map.get(index)
        if area:
            self._spin_left.setValue(area.left)
            self._spin_top.setValue(area.top)
            self._spin_width.setValue(area.width)
            self._spin_height.setValue(area.height)
        self.settings_changed.emit()

    def _on_film_category_changed(self, category: str):
        self._combo_film.blockSignals(True)
        self._combo_film.clear()
        profiles = get_profiles_by_category(category)
        for p in profiles:
            self._combo_film.addItem(p.name)
        self._combo_film.blockSignals(False)
        if profiles:
            self._on_film_changed(profiles[0].name)

    def _on_film_changed(self, name: str):
        profile = get_profile(name)
        if profile:
            self._lbl_film_desc.setText(
                f"{profile.description}\n"
                f"ISO {profile.iso} | {profile.manufacturer}"
            )
            self.apply_film_profile(profile)

    def _on_auto_wb(self):
        """Request auto white balance from main window."""
        # Will be connected externally
        pass

    def _on_auto_levels(self):
        """Request auto levels from main window."""
        # Will be connected externally
        pass

    def _on_browse_output(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory"
        )
        if directory:
            self._txt_output_dir.setText(directory)

    def _reset_all(self):
        """Reset all settings to defaults."""
        self._slider_exposure.set_value(0)
        self._slider_brightness.set_value(0)
        self._slider_contrast.set_value(0)
        self._slider_highlights.set_value(0)
        self._slider_shadows.set_value(0)
        self._slider_saturation.set_value(1.0)
        self._slider_vibrance.set_value(0)
        self._slider_temperature.set_value(0)
        self._slider_red.set_value(0)
        self._slider_green.set_value(0)
        self._slider_blue.set_value(0)
        self._slider_black_point.set_value(0)
        self._slider_white_point.set_value(255)
        self._slider_midtone.set_value(1.0)
        self._slider_sharpness.set_value(0)
        self._slider_sharpen_radius.set_value(1.0)
        self._slider_noise.set_value(0)
        self._slider_grain.set_value(0)
        self._chk_dust.setChecked(False)
        self._chk_scratch.setChecked(False)
        self._combo_rotation.setCurrentIndex(0)
        self._chk_flip_h.setChecked(False)
        self._chk_flip_v.setChecked(False)
        self._chk_invert.setChecked(True)
        self._chk_orange_mask.setChecked(True)
        self.settings_changed.emit()

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _styled_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(T.label_style_secondary())
        return lbl

    def _combo_style(self) -> str:
        return T.combo_style()

    def _checkbox_style(self) -> str:
        return T.checkbox_style()

    def _create_area_spin(self, default: float, min_val: float,
                          max_val: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setSingleStep(0.1)
        spin.setDecimals(2)
        spin.setSuffix(" in")
        spin.setStyleSheet(T.input_style())
        spin.valueChanged.connect(lambda: self.settings_changed.emit())
        return spin
