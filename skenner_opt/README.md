# SkennerOpt — Film Scanning Software for Epson V370

Professional-grade film scanning software designed for the **Epson Perfection V370** flatbed scanner with transparency unit. A VueScan alternative built in Python.

---

## Features

### Scanner Control
- **WIA (Windows Image Acquisition)** interface for direct scanner communication
- Supports Epson V370's **transparency unit** for scanning film negatives and slides
- **Backlight / TPU control** with multiple detection methods
- Resolution support from 150 DPI (preview) up to **4800 DPI** (maximum)
- Pre-configured scan areas for **35mm film strips**, **35mm slides**, **120 medium format**, and custom regions
- **Film holder templates** for Epson V370 strip holder, slide holder, and 120 holder
- **Preview scan** at low resolution for framing and adjustment
- **Batch scanning** mode for processing multiple film frames

### Film Processing
- **Negative inversion** with automatic **orange mask (C-41) removal**
- **30+ built-in film profiles** including:
  - Kodak: Portra 160/400/800, Ektar 100, Gold 200, Ultramax 400, Tri-X 400, T-Max
  - Fujifilm: Superia 400, Velvia 50/100, Provia 100F, Astia 100F
  - Ilford: HP5 Plus, FP4 Plus, Delta 100/3200
  - Fomapan: 100, 400
  - Harman Phoenix 200
  - And more...
- Support for **color negatives (C-41)**, **color slides (E-6)**, and **B&W negatives**
- **Automatic frame detection** on film strip scans (finds individual frames)
- **Auto-crop** to image content with border removal
- **Auto-deskew** (rotation correction via Hough line detection)
- **Film base color sampling** for accurate mask calibration

### Image Processing
- **16-bit processing pipeline** — float32 internal math for maximum precision
- **Exposure** adjustment (±5 EV)
- **Brightness & Contrast** controls
- **Highlights & Shadows** recovery
- **Color Balance** with RGB channel adjustment and color temperature
- **Saturation & Vibrance** controls
- **Levels** with black point, white point, and midtone gamma
- **Auto Levels** and **Auto White Balance**
- **Unsharp Mask sharpening** with adjustable radius
- **Noise reduction** and **film grain reduction** (OpenCV-powered)
- **Dust removal** and **scratch removal** via morphological detection + inpainting
- **Rotation** (0°/90°/180°/270°) and **flip** (horizontal/vertical)
- **ICC color management** — sRGB, Adobe RGB (system), Display P3
- **Color space selection** with ICC profile embedding on save

### User Interface
- Professional **dark theme** UI built with PyQt6
- **Real-time preview** with zoom (scroll wheel) and pan (right-click drag)
- **Before / After split comparison** view with draggable split line
- **Visual crop selection** — draw crop rectangle directly on preview
- **RGB histogram** with per-channel display
- **Pixel inspector** showing coordinates and RGB values under cursor
- **Collapsible settings panels** for organized workflow
- **Undo / Redo** (Ctrl+Z / Ctrl+Y) with full history stack (100 levels)
- **Save / Load presets** — export, import, and share processing settings
- **5 built-in presets**: Clean Scan, High Contrast B&W, Vintage Warm, Slide Accurate, Grain Tamer
- **Session persistence** — remembers all settings between launches
- **Bug reporting** with log viewer, system info, and exportable reports
- Status bar with scan progress and scanner info

### Output
- Save as **TIFF** (lossless, LZW compressed), **PNG**, **JPEG** (95% quality), or **BMP**
- **EXIF metadata** embedded automatically — scanner info, film profile, DPI, processing notes
- **ICC profile** embedded in output files
- Configurable output directory and filename patterns
- Save raw (unprocessed) scans separately

---

## Installation

### Prerequisites
- **Python 3.9+** (3.11 recommended)
- **Epson V370 drivers** installed (or use Demo Mode without hardware)
- Windows 10/11 (WIA support)

### Setup

```bash
# Navigate to project directory
cd skenner_opt

# (Recommended) Create a virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Dependencies
| Package | Purpose |
|---------|---------|
| PyQt6 | GUI framework |
| Pillow | Image loading/saving |
| numpy | Image processing math |
| opencv-python | Advanced noise reduction, dust/scratch removal |
| pywin32 | Windows COM automation |
| comtypes | WIA scanner interface |

---

## Usage

### Launch
```bash
python main.py
```

### Quick Start — Scanning a Film Negative
1. **Connect** your Epson V370 (or use Scanner > Demo Mode for testing)
2. Place your film in the **transparency unit holder** on the scanner
3. Set **Source** to "Transparency (Film)"
4. Choose a **Film Profile** (e.g., "Kodak Portra 400" for color negatives)
5. Select the appropriate **Scan Area** preset (e.g., "35mm Film Strip")
6. Click **Preview** to see a low-resolution preview
7. Adjust **Exposure, Color, Levels** as needed
8. Set **Resolution** to 2400 DPI or higher for the final scan
9. Click **Scan** for full-resolution capture
10. Click **Save** to export

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| Ctrl+O | Open existing image |
| Ctrl+S | Save processed image |
| Ctrl+P | Preview scan |
| Ctrl+Enter | Full scan |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl+D | Detect frames |
| Ctrl+B | Before/After compare |
| Ctrl+L | Auto Levels |
| Ctrl+W | Auto White Balance |
| Ctrl+0 | Fit in view |
| Ctrl+1 | Zoom 100% |
| F1 | Bug report / logs |
| Ctrl+Q | Quit |

### Demo Mode
If no scanner hardware is connected, the app automatically enters **Demo Mode**, generating synthetic film-like test images so you can explore all the processing features.

---

## Architecture

```
skenner_opt/
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── README.md                  # This file
└── scanner_app/
    ├── __init__.py            # Package metadata (v2.0.0)
    ├── app.py                 # Main window & application orchestration
    ├── scanner.py             # WIA scanner interface + demo simulator
    ├── image_processor.py     # Full image processing pipeline (16-bit)
    ├── film_profiles.py       # 30+ film stock color profiles
    ├── preview_widget.py      # Preview + histogram + before/after + crop
    ├── settings_panel.py      # Settings UI with collapsible sections
    ├── frame_detection.py     # Auto frame detection, crop, deskew
    ├── color_management.py    # ICC profiles & color space conversion
    ├── metadata.py            # EXIF metadata embedding
    ├── history.py             # Undo/redo history manager
    ├── presets.py             # Preset save/load/export + session persistence
    ├── bug_logger.py          # Logging, crash handler, bug reports
    └── utils.py               # Utility functions
```

---

## Tips for Best Film Scans

- **Resolution**: Use 2400–4800 DPI for 35mm. Higher resolution = more detail but larger files and slower scans
- **Bit depth**: Use 48-bit for maximum editing flexibility, especially with negatives
- **Orange mask**: Keep "Remove Orange Mask" enabled for C-41 color negatives
- **Dust removal**: Enable for old/dusty negatives — uses morphological detection
- **Grain reduction**: Apply moderately (20-40) to reduce visible grain without losing detail
- **Sharpening**: Apply 50-150 amount with 1.0-2.0 radius as the final step
- **Film profiles**: Start with the matching film stock profile, then fine-tune
- **Save raw**: Always save the raw scan as TIFF before processing — you can reprocess later

---

## License

MIT License — Free for personal and commercial use.
