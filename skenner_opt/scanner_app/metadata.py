"""
EXIF metadata embedding for scanned images.
Writes scanner info, processing settings, and film profile data
into TIFF/JPEG EXIF tags.
"""

import logging
import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

from PIL import Image
from PIL.ExifTags import Base as ExifBase

logger = logging.getLogger(__name__)


@dataclass
class ScanMetadata:
    """Metadata to embed in scanned images."""
    # Scanner info
    scanner_name: str = ""
    scanner_manufacturer: str = "Epson"
    scanner_model: str = "Perfection V370"

    # Scan parameters
    resolution_dpi: int = 0
    bit_depth: int = 0
    scan_source: str = ""  # "Transparency" or "Flatbed"
    color_mode: str = ""

    # Film info
    film_profile: str = ""
    film_manufacturer: str = ""
    film_iso: int = 0
    film_type: str = ""  # "Color Negative", "Slide", etc.

    # Processing
    invert_negative: bool = False
    orange_mask_removal: bool = False
    exposure_ev: float = 0.0
    white_balance: str = ""

    # Scan context
    scan_date: str = ""
    software_version: str = "1.0.0"
    frame_number: int = 0
    batch_id: str = ""

    # User notes
    notes: str = ""
    tags: str = ""


def build_exif_dict(metadata: ScanMetadata) -> Dict[int, Any]:
    """
    Build a dictionary of EXIF tag ID → value pairs.
    Uses standard EXIF tags where applicable.
    """
    exif = {}

    # Standard EXIF tags
    if metadata.scan_date:
        exif[ExifBase.DateTime] = metadata.scan_date
        exif[ExifBase.DateTimeOriginal] = metadata.scan_date
        exif[ExifBase.DateTimeDigitized] = metadata.scan_date
    else:
        now = datetime.datetime.now().strftime("%Y:%m:%d %H:%M:%S")
        exif[ExifBase.DateTime] = now
        exif[ExifBase.DateTimeOriginal] = now

    # Software
    exif[ExifBase.Software] = f"SkennerOpt {metadata.software_version}"

    # Make / Model (we use scanner info)
    if metadata.scanner_manufacturer:
        exif[ExifBase.Make] = metadata.scanner_manufacturer
    if metadata.scanner_model:
        exif[ExifBase.Model] = metadata.scanner_model

    # Resolution
    if metadata.resolution_dpi > 0:
        exif[ExifBase.XResolution] = (metadata.resolution_dpi, 1)
        exif[ExifBase.YResolution] = (metadata.resolution_dpi, 1)
        exif[ExifBase.ResolutionUnit] = 2  # inches

    # ISO (use film ISO if available)
    if metadata.film_iso > 0:
        exif[ExifBase.ISOSpeedRatings] = metadata.film_iso

    # Exposure compensation
    if metadata.exposure_ev != 0:
        # Store as rational
        ev_num = int(metadata.exposure_ev * 100)
        exif[ExifBase.ExposureBiasValue] = (ev_num, 100)

    # UserComment - store all extra info here
    comment_parts = []
    if metadata.film_profile:
        comment_parts.append(f"Film: {metadata.film_profile}")
    if metadata.film_manufacturer:
        comment_parts.append(f"Film Mfr: {metadata.film_manufacturer}")
    if metadata.film_type:
        comment_parts.append(f"Type: {metadata.film_type}")
    if metadata.scan_source:
        comment_parts.append(f"Source: {metadata.scan_source}")
    if metadata.bit_depth:
        comment_parts.append(f"Bit Depth: {metadata.bit_depth}")
    if metadata.invert_negative:
        comment_parts.append("Inverted: Yes")
    if metadata.orange_mask_removal:
        comment_parts.append("Orange Mask: Removed")
    if metadata.notes:
        comment_parts.append(f"Notes: {metadata.notes}")
    if metadata.tags:
        comment_parts.append(f"Tags: {metadata.tags}")
    if metadata.frame_number:
        comment_parts.append(f"Frame: {metadata.frame_number}")

    if comment_parts:
        exif[ExifBase.UserComment] = " | ".join(comment_parts)

    # ImageDescription
    desc_parts = []
    if metadata.film_profile:
        desc_parts.append(metadata.film_profile)
    if metadata.scan_source:
        desc_parts.append(f"Scanned from {metadata.scan_source}")
    if metadata.resolution_dpi:
        desc_parts.append(f"{metadata.resolution_dpi} DPI")
    if desc_parts:
        exif[ExifBase.ImageDescription] = " — ".join(desc_parts)

    return exif


def apply_exif_to_image(image: Image.Image,
                         metadata: ScanMetadata) -> Image.Image:
    """
    Apply EXIF metadata to a PIL Image.
    The metadata will be saved when the image is written to file.
    """
    exif_dict = build_exif_dict(metadata)

    try:
        exif = image.getexif()
        for tag_id, value in exif_dict.items():
            try:
                exif[tag_id] = value
            except Exception as e:
                logger.debug(f"Could not set EXIF tag {tag_id}: {e}")

        image.info["exif"] = exif.tobytes()
        logger.info(f"Applied {len(exif_dict)} EXIF tags")

    except Exception as e:
        logger.warning(f"EXIF embedding failed: {e}")

    return image


def read_exif_from_image(image: Image.Image) -> Dict[str, str]:
    """Read EXIF metadata from an image, return as human-readable dict."""
    result = {}
    try:
        exif = image.getexif()
        tag_names = {v: k for k, v in ExifBase.__dict__.items()
                     if isinstance(v, int)}

        for tag_id, value in exif.items():
            name = tag_names.get(tag_id, f"Tag_{tag_id}")
            result[name] = str(value)

    except Exception as e:
        logger.debug(f"Could not read EXIF: {e}")

    return result
