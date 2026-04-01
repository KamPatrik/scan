"""
Utility functions for SkennerOpt.
"""

import os
import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_app_data_dir() -> str:
    """Get application data directory, creating it if needed."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")

    app_dir = os.path.join(base, "SkennerOpt")
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def get_default_output_dir() -> str:
    """Get default output directory for scans."""
    pictures = os.path.join(os.path.expanduser("~"), "Pictures", "SkennerOpt")
    os.makedirs(pictures, exist_ok=True)
    return pictures


def format_file_size(size_bytes: int) -> str:
    """Format bytes as human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def estimate_scan_size(width_inches: float, height_inches: float,
                       dpi: int, bit_depth: int = 24) -> int:
    """Estimate scan file size in bytes."""
    pixels_w = int(width_inches * dpi)
    pixels_h = int(height_inches * dpi)
    bytes_per_pixel = bit_depth // 8
    return pixels_w * pixels_h * bytes_per_pixel


def estimate_scan_time(width_inches: float, height_inches: float,
                       dpi: int) -> float:
    """Rough estimate of scan time in seconds for Epson V370."""
    # Very rough estimates based on typical V370 performance
    megapixels = (width_inches * dpi * height_inches * dpi) / 1_000_000

    if dpi <= 300:
        return max(5, megapixels * 0.5)
    elif dpi <= 600:
        return max(10, megapixels * 1.0)
    elif dpi <= 1200:
        return max(20, megapixels * 2.0)
    elif dpi <= 2400:
        return max(45, megapixels * 3.0)
    else:
        return max(90, megapixels * 5.0)
