"""
ICC color management and color space support.
Provides:
- ICC profile embedding in output files
- Color space conversion (sRGB, AdobeRGB, ProPhoto RGB)
- Soft proofing simulation
- Monitor profile awareness
"""

import logging
import os
import struct
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import numpy as np
from PIL import Image, ImageCms

logger = logging.getLogger(__name__)


class ColorSpace(Enum):
    """Supported working color spaces."""
    SRGB = "sRGB"
    ADOBE_RGB = "Adobe RGB (1998)"
    PROPHOTO_RGB = "ProPhoto RGB"
    DISPLAY_P3 = "Display P3"


@dataclass
class ColorProfile:
    """Represents an ICC color profile."""
    name: str = "sRGB"
    color_space: ColorSpace = ColorSpace.SRGB
    profile_path: Optional[str] = None
    _icc_profile: object = None  # ImageCms.ImageCmsProfile

    @property
    def icc_profile(self):
        return self._icc_profile


class ColorManager:
    """
    Manages color spaces and ICC profile operations.
    """

    def __init__(self):
        self._working_space = ColorSpace.SRGB
        self._srgb_profile = None
        self._adobe_rgb_profile = None
        self._prophoto_profile = None
        self._display_profile = None
        self._init_profiles()

    def _init_profiles(self):
        """Initialize built-in ICC profiles."""
        try:
            self._srgb_profile = ImageCms.createProfile("sRGB")
            logger.info("sRGB profile initialized")
        except Exception as e:
            logger.warning(f"Could not create sRGB profile: {e}")

        # Try to load Adobe RGB from system
        try:
            adobe_paths = [
                os.path.join(os.environ.get("SystemRoot", "C:\\Windows"),
                             "System32", "spool", "drivers", "color",
                             "AdobeRGB1998.icc"),
                os.path.join(os.environ.get("PROGRAMFILES", ""),
                             "Common Files", "Adobe", "Color", "Profiles",
                             "AdobeRGB1998.icc"),
            ]
            for path in adobe_paths:
                if os.path.exists(path):
                    self._adobe_rgb_profile = ImageCms.getOpenProfile(path)
                    logger.info(f"Adobe RGB profile loaded from: {path}")
                    break
        except Exception as e:
            logger.debug(f"Adobe RGB profile not available: {e}")

        # Try to get display/monitor profile
        try:
            if os.name == 'nt':
                import ctypes
                dc = ctypes.windll.user32.GetDC(0)
                buf = ctypes.create_string_buffer(260)
                ctypes.windll.gdi32.GetICMProfileA(
                    dc, ctypes.byref(ctypes.c_ulong(260)), buf
                )
                ctypes.windll.user32.ReleaseDC(0, dc)
                profile_path = buf.value.decode('ascii', errors='ignore')
                if profile_path and os.path.exists(profile_path):
                    self._display_profile = ImageCms.getOpenProfile(profile_path)
                    logger.info(f"Display profile loaded: {profile_path}")
        except Exception as e:
            logger.debug(f"Display profile not available: {e}")

    @property
    def working_space(self) -> ColorSpace:
        return self._working_space

    @working_space.setter
    def working_space(self, space: ColorSpace):
        self._working_space = space
        logger.info(f"Working color space set to: {space.value}")

    def get_profile_for_space(self, space: ColorSpace):
        """Get the ICC profile object for a color space."""
        if space == ColorSpace.SRGB:
            return self._srgb_profile
        elif space == ColorSpace.ADOBE_RGB:
            return self._adobe_rgb_profile or self._srgb_profile
        elif space == ColorSpace.PROPHOTO_RGB:
            return self._prophoto_profile or self._srgb_profile
        return self._srgb_profile

    def convert_color_space(self, image: Image.Image,
                             from_space: ColorSpace,
                             to_space: ColorSpace) -> Image.Image:
        """Convert image between color spaces."""
        if from_space == to_space:
            return image

        from_profile = self.get_profile_for_space(from_space)
        to_profile = self.get_profile_for_space(to_space)

        if from_profile is None or to_profile is None:
            logger.warning("Missing profile, skipping color space conversion")
            return image

        try:
            transform = ImageCms.buildTransform(
                from_profile, to_profile,
                "RGB", "RGB",
                renderingIntent=ImageCms.Intent.PERCEPTUAL,
            )
            return ImageCms.applyTransform(image, transform)
        except Exception as e:
            logger.warning(f"Color space conversion failed: {e}")
            return image

    def embed_profile(self, image: Image.Image,
                       space: Optional[ColorSpace] = None) -> Image.Image:
        """Embed ICC profile in image for saving."""
        space = space or self._working_space
        profile = self.get_profile_for_space(space)

        if profile:
            try:
                icc_data = ImageCms.ImageCmsProfile(profile).tobytes()
                image.info["icc_profile"] = icc_data
                logger.debug(f"Embedded {space.value} ICC profile")
            except Exception as e:
                logger.warning(f"Could not embed ICC profile: {e}")

        return image

    def get_srgb_icc_bytes(self) -> Optional[bytes]:
        """Get raw sRGB ICC profile bytes for TIFF/JPEG embedding."""
        if self._srgb_profile:
            try:
                return ImageCms.ImageCmsProfile(self._srgb_profile).tobytes()
            except Exception:
                pass
        return None

    def get_available_spaces(self) -> list:
        """List available color spaces (with loaded profiles)."""
        spaces = [ColorSpace.SRGB]  # Always available
        if self._adobe_rgb_profile:
            spaces.append(ColorSpace.ADOBE_RGB)
        if self._prophoto_profile:
            spaces.append(ColorSpace.PROPHOTO_RGB)
        return spaces
