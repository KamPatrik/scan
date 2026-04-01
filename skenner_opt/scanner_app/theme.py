"""
SkennerOpt Theme Engine — Centralized modern dark theme.

Design language:
- Layered depth via background luminance tiers
- Accent color (blue) for interactive elements
- Consistent 8px corner radius
- Segoe UI Variable / Inter / system font at proper sizes
- Subtle borders instead of box-shadows (Qt limitation)
- Unicode icons for buttons (no external icon files needed)
"""

# ── Color Palette ───────────────────────────────────────────────────────────

# Background layers (darkest → lightest)
BG_BASE       = "#111214"   # App background, canvas
BG_SURFACE    = "#1a1c1f"   # Panels, sidebars
BG_CARD       = "#22252a"   # Cards, collapsible section bodies
BG_ELEVATED   = "#2a2d33"   # Headers, toolbars, elevated elements
BG_INPUT      = "#2e3139"   # Text inputs, combo boxes, slider grooves
BG_HOVER      = "#353940"   # Hover states
BG_ACTIVE     = "#3e434b"   # Active/pressed states

# Foreground / text
FG_PRIMARY    = "#e8eaed"   # Primary text
FG_SECONDARY  = "#9aa0a6"   # Secondary / muted text
FG_TERTIARY   = "#6b7280"   # Disabled, hints, captions
FG_INVERSE    = "#111214"   # Text on bright backgrounds

# Accent
ACCENT        = "#4c8bf5"   # Primary blue accent
ACCENT_HOVER  = "#6ea1ff"   # Hover blue
ACCENT_MUTED  = "#2d4a7a"   # Muted / background tint
ACCENT_DIM    = "#1e3555"   # Very subtle accent tint

# Semantic colors
GREEN         = "#34a853"   # Success, positive
GREEN_HOVER   = "#46b866"
RED           = "#ea4335"   # Danger, destructive
RED_HOVER     = "#f05545"
RED_DIM       = "#3d1f1f"
YELLOW        = "#fbbc04"   # Warning
ORANGE        = "#ff8c00"   # Progress

# Borders
BORDER        = "#3a3e47"   # Subtle border
BORDER_FOCUS  = "#4c8bf5"   # Focused element
BORDER_SUBTLE = "#2e3139"   # Very subtle separator

# Histogram colors
HIST_RED      = "#ff5252"
HIST_GREEN    = "#69f0ae"
HIST_BLUE     = "#448aff"
HIST_LUM      = "#e0e0e0"

# ── Typography ──────────────────────────────────────────────────────────────

FONT_FAMILY   = "'Segoe UI Variable', 'Segoe UI', 'Inter', 'SF Pro Display', system-ui, sans-serif"
FONT_SIZE_XS  = "10px"
FONT_SIZE_SM  = "11px"
FONT_SIZE_MD  = "12px"
FONT_SIZE_LG  = "13px"
FONT_SIZE_XL  = "15px"
FONT_SIZE_XXL = "20px"

# ── Geometry ────────────────────────────────────────────────────────────────

RADIUS_SM     = "4px"
RADIUS_MD     = "6px"
RADIUS_LG     = "8px"
RADIUS_XL     = "12px"
RADIUS_FULL   = "100px"

# ── Unicode Icons ───────────────────────────────────────────────────────────
# Zero-dependency "icon" system using Unicode symbols.

ICON_PREVIEW  = "\u25B7"   # ▷  Play / Preview
ICON_SCAN     = "\u23CF"   # ⏏  Scan
ICON_SAVE     = "\u2913"   # ⤓  Save / Download
ICON_FOLDER   = "\u2302"   # ⌂  Folder
ICON_UNDO     = "\u21B6"   # ↶  Undo
ICON_REDO     = "\u21B7"   # ↷  Redo
ICON_FIT      = "\u2922"   # ⤢  Fit
ICON_ZOOM_IN  = "\u2295"   # ⊕  Zoom in
ICON_ZOOM_OUT = "\u2296"   # ⊖  Zoom out
ICON_CROP     = "\u2702"   # ✂  Crop
ICON_COMPARE  = "\u21C6"   # ⇆  Before/After
ICON_RESET    = "\u27F3"   # ⟳  Reset
ICON_SETTINGS = "\u2699"   # ⚙  Settings
ICON_EXPAND   = "\u25BC"   # ▼  Expanded
ICON_COLLAPSE = "\u25B6"   # ▶  Collapsed
ICON_CHECK    = "\u2713"   # ✓  Checkmark
ICON_DOT      = "\u25CF"   # ●  Dot
ICON_FILM     = "\u2707"   # ✇  Film
ICON_STAR     = "\u2605"   # ★  Star
ICON_INFO     = "\u24D8"   # ⓘ  Info
ICON_BUG      = "\U0001F41B"  # 🐛 Bug
ICON_COLOR    = "\u25C9"   # ◉  Color
ICON_EXPOSURE = "\u2600"   # ☀  Sun / Exposure
ICON_NEGATIVE = "\u29C4"   # ⧄  Negative / Invert
ICON_LEVELS   = "\u2261"   # ≡  Levels
ICON_DETAIL   = "\u25A3"   # ▣  Detail / Sharpness
ICON_TRANSFORM = "\u21BB"  # ↻  Transform / Rotate
ICON_HISTOGRAM = "\u2581\u2583\u2585\u2587"  # ▁▃▅▇ Histogram


# ── Stylesheet Generators ───────────────────────────────────────────────────

def app_stylesheet() -> str:
    """Master application-wide stylesheet."""
    return f"""
        /* ── Global ─────────────────────────────────────────── */
        * {{
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_MD};
            outline: none;
        }}

        QMainWindow {{
            background: {BG_BASE};
        }}

        QWidget {{
            color: {FG_PRIMARY};
        }}

        /* ── Menu Bar ───────────────────────────────────────── */
        QMenuBar {{
            background: {BG_ELEVATED};
            color: {FG_PRIMARY};
            border-bottom: 1px solid {BORDER_SUBTLE};
            padding: 2px 4px;
            font-size: {FONT_SIZE_MD};
            spacing: 2px;
        }}
        QMenuBar::item {{
            background: transparent;
            padding: 5px 10px;
            border-radius: {RADIUS_SM};
        }}
        QMenuBar::item:selected {{
            background: {BG_HOVER};
        }}
        QMenuBar::item:pressed {{
            background: {ACCENT_MUTED};
        }}

        /* ── Menus ──────────────────────────────────────────── */
        QMenu {{
            background: {BG_ELEVATED};
            color: {FG_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_MD};
            padding: 4px 0;
        }}
        QMenu::item {{
            padding: 6px 28px 6px 12px;
            border-radius: {RADIUS_SM};
            margin: 1px 4px;
        }}
        QMenu::item:selected {{
            background: {ACCENT_MUTED};
            color: {FG_PRIMARY};
        }}
        QMenu::item:disabled {{
            color: {FG_TERTIARY};
        }}
        QMenu::separator {{
            height: 1px;
            background: {BORDER_SUBTLE};
            margin: 4px 8px;
        }}
        QMenu::icon {{
            padding-left: 8px;
        }}

        /* ── Status Bar ─────────────────────────────────────── */
        QStatusBar {{
            background: {BG_SURFACE};
            color: {FG_SECONDARY};
            border-top: 1px solid {BORDER_SUBTLE};
            font-size: {FONT_SIZE_SM};
            min-height: 26px;
        }}
        QStatusBar::item {{
            border: none;
        }}

        /* ── Splitter ───────────────────────────────────────── */
        QSplitter::handle {{
            background: {BORDER};
            width: 1px;
        }}
        QSplitter::handle:hover {{
            background: {ACCENT};
        }}

        /* ── Tooltips ───────────────────────────────────────── */
        QToolTip {{
            background: {BG_ELEVATED};
            color: {FG_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_SM};
            padding: 5px 8px;
            font-size: {FONT_SIZE_SM};
        }}

        /* ── Scroll Bars ────────────────────────────────────── */
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {BG_HOVER};
            border-radius: 4px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {FG_TERTIARY};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 8px;
        }}
        QScrollBar::handle:horizontal {{
            background: {BG_HOVER};
            border-radius: 4px;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {FG_TERTIARY};
        }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {{
            background: transparent;
        }}

        /* ── Progress Bar ───────────────────────────────────── */
        QProgressBar {{
            background: {BG_INPUT};
            border: none;
            border-radius: {RADIUS_SM};
            text-align: center;
            color: {FG_PRIMARY};
            font-size: {FONT_SIZE_XS};
            min-height: 14px;
            max-height: 14px;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {ACCENT}, stop:1 {ACCENT_HOVER});
            border-radius: {RADIUS_SM};
        }}

        /* ── Tab Widget ─────────────────────────────────────── */
        QTabWidget::pane {{
            border: 1px solid {BORDER};
            background: {BG_CARD};
            border-radius: {RADIUS_MD};
        }}
        QTabBar::tab {{
            background: {BG_ELEVATED};
            color: {FG_SECONDARY};
            padding: 8px 18px;
            border: 1px solid {BORDER};
            border-bottom: none;
            border-top-left-radius: {RADIUS_MD};
            border-top-right-radius: {RADIUS_MD};
            margin-right: 2px;
            font-size: {FONT_SIZE_MD};
        }}
        QTabBar::tab:selected {{
            background: {BG_CARD};
            color: {FG_PRIMARY};
            border-bottom: 2px solid {ACCENT};
        }}
        QTabBar::tab:hover:!selected {{
            background: {BG_HOVER};
        }}

        /* ── Dialog ─────────────────────────────────────────── */
        QDialog {{
            background: {BG_SURFACE};
            color: {FG_PRIMARY};
        }}

        /* ── Message Box ────────────────────────────────────── */
        QMessageBox {{
            background: {BG_SURFACE};
        }}
        QMessageBox QLabel {{
            color: {FG_PRIMARY};
            font-size: {FONT_SIZE_MD};
        }}
    """


def collapsible_header_style() -> str:
    return f"""
        QToolButton {{
            background: {BG_ELEVATED};
            border: none;
            border-bottom: 1px solid {BORDER_SUBTLE};
            border-left: 3px solid transparent;
            padding: 8px 10px;
            color: {FG_PRIMARY};
            font-weight: 600;
            font-size: {FONT_SIZE_MD};
            text-align: left;
        }}
        QToolButton:hover {{
            background: {BG_HOVER};
            border-left: 3px solid {ACCENT_MUTED};
        }}
        QToolButton:checked {{
            border-left: 3px solid {ACCENT};
        }}
    """


def collapsible_body_style() -> str:
    return f"""
        QFrame {{
            background: {BG_CARD};
            border: none;
            border-left: 1px solid {BORDER_SUBTLE};
            margin-left: 2px;
        }}
    """


def slider_style() -> str:
    return f"""
        QSlider::groove:horizontal {{
            background: {BG_INPUT};
            height: 4px;
            border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {ACCENT_MUTED}, stop:1 {ACCENT});
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {ACCENT};
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 7px;
            border: 2px solid {BG_CARD};
        }}
        QSlider::handle:horizontal:hover {{
            background: {ACCENT_HOVER};
            border: 2px solid {ACCENT_DIM};
        }}
        QSlider::handle:horizontal:pressed {{
            background: {FG_PRIMARY};
        }}
    """


def combo_style() -> str:
    return f"""
        QComboBox {{
            background: {BG_INPUT};
            color: {FG_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_MD};
            padding: 5px 10px;
            font-size: {FONT_SIZE_MD};
            min-height: 20px;
        }}
        QComboBox:hover {{
            border-color: {FG_TERTIARY};
        }}
        QComboBox:focus {{
            border-color: {ACCENT};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
            subcontrol-origin: padding;
            subcontrol-position: center right;
        }}
        QComboBox::down-arrow {{
            image: none;
            border: none;
        }}
        QComboBox QAbstractItemView {{
            background: {BG_ELEVATED};
            color: {FG_PRIMARY};
            selection-background-color: {ACCENT_MUTED};
            selection-color: {FG_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_MD};
            padding: 4px;
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{
            padding: 5px 8px;
            border-radius: {RADIUS_SM};
            min-height: 22px;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background: {BG_HOVER};
        }}
    """


def checkbox_style() -> str:
    return f"""
        QCheckBox {{
            color: {FG_PRIMARY};
            font-size: {FONT_SIZE_MD};
            spacing: 8px;
            padding: 4px 2px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {FG_TERTIARY};
            border-radius: {RADIUS_SM};
            background: {BG_INPUT};
        }}
        QCheckBox::indicator:hover {{
            border-color: {ACCENT};
            background: {ACCENT_DIM};
        }}
        QCheckBox::indicator:checked {{
            background: {ACCENT};
            border-color: {ACCENT};
        }}
        QCheckBox::indicator:checked:hover {{
            background: {ACCENT_HOVER};
            border-color: {ACCENT_HOVER};
        }}
    """


def input_style() -> str:
    return f"""
        QLineEdit, QSpinBox, QDoubleSpinBox {{
            background: {BG_INPUT};
            color: {FG_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_MD};
            padding: 5px 8px;
            font-size: {FONT_SIZE_MD};
            selection-background-color: {ACCENT_MUTED};
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {ACCENT};
        }}
        QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
            border-color: {FG_TERTIARY};
        }}
    """


def primary_button_style() -> str:
    """Blue accent button."""
    return f"""
        QPushButton {{
            background: {ACCENT};
            color: {FG_PRIMARY};
            border: none;
            border-radius: {RADIUS_MD};
            padding: 8px 18px;
            font-weight: 600;
            font-size: {FONT_SIZE_MD};
            min-height: 18px;
        }}
        QPushButton:hover {{
            background: {ACCENT_HOVER};
        }}
        QPushButton:pressed {{
            background: {ACCENT_MUTED};
        }}
        QPushButton:disabled {{
            background: {BG_HOVER};
            color: {FG_TERTIARY};
        }}
    """


def secondary_button_style() -> str:
    """Subtle / secondary button."""
    return f"""
        QPushButton {{
            background: {BG_INPUT};
            color: {FG_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_MD};
            padding: 6px 14px;
            font-size: {FONT_SIZE_SM};
            min-height: 16px;
        }}
        QPushButton:hover {{
            background: {BG_HOVER};
            border-color: {FG_TERTIARY};
        }}
        QPushButton:pressed {{
            background: {BG_ACTIVE};
        }}
    """


def success_button_style() -> str:
    """Green action button."""
    return f"""
        QPushButton {{
            background: {GREEN};
            color: {FG_PRIMARY};
            border: none;
            border-radius: {RADIUS_MD};
            padding: 8px 18px;
            font-weight: 600;
            font-size: {FONT_SIZE_MD};
            min-height: 18px;
        }}
        QPushButton:hover {{
            background: {GREEN_HOVER};
        }}
        QPushButton:pressed {{
            background: #2a8a44;
        }}
    """


def danger_button_style() -> str:
    """Red destructive button."""
    return f"""
        QPushButton {{
            background: {RED_DIM};
            color: {RED};
            border: 1px solid {RED_DIM};
            border-radius: {RADIUS_MD};
            padding: 7px 16px;
            font-weight: 600;
            font-size: {FONT_SIZE_SM};
        }}
        QPushButton:hover {{
            background: {RED};
            color: {FG_PRIMARY};
            border-color: {RED};
        }}
    """


def toolbar_style() -> str:
    return f"""
        QToolBar {{
            background: {BG_SURFACE};
            border: none;
            border-bottom: 1px solid {BORDER_SUBTLE};
            padding: 3px 6px;
            spacing: 3px;
        }}
        QToolButton {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: {RADIUS_MD};
            padding: 5px 10px;
            color: {FG_SECONDARY};
            font-size: {FONT_SIZE_MD};
            font-weight: 500;
        }}
        QToolButton:hover {{
            background: {BG_HOVER};
            color: {FG_PRIMARY};
            border-color: {BORDER};
        }}
        QToolButton:pressed {{
            background: {BG_ACTIVE};
        }}
        QToolButton:checked {{
            background: {ACCENT_MUTED};
            color: {ACCENT_HOVER};
            border-color: {ACCENT};
        }}
    """


def scroll_area_style() -> str:
    return f"""
        QScrollArea {{
            background: {BG_SURFACE};
            border: none;
        }}
    """


def pixel_label_style() -> str:
    """Bottom pixel info strip."""
    return f"""
        color: {FG_SECONDARY};
        font-size: {FONT_SIZE_XS};
        font-family: 'Consolas', 'Cascadia Code', 'JetBrains Mono', monospace;
        padding: 3px 8px;
        background: {BG_BASE};
        border-top: 1px solid {BORDER_SUBTLE};
    """


def preview_button_style() -> str:
    """Muted outline button for Preview."""
    return f"""
        QPushButton {{
            background: transparent;
            color: {ACCENT};
            border: 1.5px solid {ACCENT};
            border-radius: {RADIUS_MD};
            padding: 8px 18px;
            font-weight: 600;
            font-size: {FONT_SIZE_MD};
            min-height: 18px;
        }}
        QPushButton:hover {{
            background: {ACCENT_DIM};
        }}
        QPushButton:pressed {{
            background: {ACCENT_MUTED};
        }}
    """


def label_style_primary() -> str:
    return f"color: {FG_PRIMARY}; font-size: {FONT_SIZE_MD};"


def label_style_secondary() -> str:
    return f"color: {FG_SECONDARY}; font-size: {FONT_SIZE_SM};"


def label_style_caption() -> str:
    return f"color: {FG_TERTIARY}; font-size: {FONT_SIZE_XS}; font-style: italic;"


def value_label_style() -> str:
    return f"""
        color: {FG_SECONDARY};
        font-size: {FONT_SIZE_SM};
        font-family: 'Consolas', 'Cascadia Code', monospace;
    """


def progress_bar_style() -> str:
    return f"""
        QProgressBar {{
            background: {BG_INPUT};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_SM};
            text-align: center;
            color: {FG_PRIMARY};
            font-size: {FONT_SIZE_XS};
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {ACCENT}, stop:1 {ACCENT_HOVER});
            border-radius: {RADIUS_SM};
        }}
    """


def tab_widget_style() -> str:
    return f"""
        QTabWidget::pane {{
            border: 1px solid {BORDER};
            background: {BG_BASE};
            border-radius: {RADIUS};
        }}
        QTabBar::tab {{
            background: {BG_LAYER1};
            color: {FG_SECONDARY};
            padding: 8px 18px;
            border: 1px solid {BORDER};
            border-bottom: none;
            border-top-left-radius: {RADIUS};
            border-top-right-radius: {RADIUS};
            margin-right: 2px;
            font-size: {FONT_SIZE_SM};
        }}
        QTabBar::tab:selected {{
            background: {BG_BASE};
            color: {FG_PRIMARY};
            border-bottom: 2px solid {ACCENT};
        }}
        QTabBar::tab:hover:!selected {{
            background: {BG_LAYER2};
            color: {FG_PRIMARY};
        }}
    """


def dialog_style() -> str:
    return f"""
        QDialog {{
            background: {BG_BASE};
            color: {FG_PRIMARY};
        }}
    """


def log_viewer_style() -> str:
    return f"""
        QPlainTextEdit {{
            background: {BG_BASE};
            color: #b0d0b0;
            border: 1px solid {BORDER};
            border-radius: {RADIUS};
            font-family: 'Consolas', 'Cascadia Code', 'Courier New', monospace;
            font-size: {FONT_SIZE_XS};
            padding: 6px;
        }}
    """
