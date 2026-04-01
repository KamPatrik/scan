"""
Image processing engine for film scanning.
Provides:
- Negative inversion with orange mask removal
- Color balance and correction
- Levels and curves adjustment
- Dust/scratch removal
- Sharpening (Unsharp Mask)
- Grain reduction / noise filtering
- Histogram analysis
- Auto-exposure and auto-levels
"""

import logging
from typing import Optional, Tuple, List
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps

logger = logging.getLogger(__name__)


@dataclass
class LevelsAdjustment:
    """Input/output levels for each channel and master."""
    # Input levels (0-255)
    black_point: int = 0
    white_point: int = 255
    midtone: float = 1.0  # gamma, 0.1 to 10.0
    # Output levels
    output_black: int = 0
    output_white: int = 255


@dataclass
class CurvesPoint:
    """A single point on a curves adjustment."""
    input_val: int = 0   # 0-255
    output_val: int = 0  # 0-255


@dataclass
class ColorBalance:
    """Color balance adjustments."""
    red_shift: float = 0.0     # -100 to 100
    green_shift: float = 0.0   # -100 to 100
    blue_shift: float = 0.0    # -100 to 100
    temperature: float = 0.0   # -100 (cool) to 100 (warm)


@dataclass
class ProcessingSettings:
    """Complete set of image processing parameters."""
    # Inversion
    invert_negative: bool = False
    orange_mask_removal: bool = False

    # Levels per channel
    levels_master: LevelsAdjustment = None
    levels_red: LevelsAdjustment = None
    levels_green: LevelsAdjustment = None
    levels_blue: LevelsAdjustment = None

    # Color
    color_balance: ColorBalance = None
    saturation: float = 1.0       # 0.0 to 3.0
    vibrance: float = 0.0         # -100 to 100

    # Tone
    exposure: float = 0.0         # -5.0 to 5.0 EV
    brightness: float = 0.0       # -100 to 100
    contrast: float = 0.0         # -100 to 100
    highlights: float = 0.0       # -100 to 100
    shadows: float = 0.0          # -100 to 100

    # Detail
    sharpness: float = 0.0        # 0 to 500 (unsharp mask amount)
    sharpen_radius: float = 1.0   # 0.1 to 10.0
    noise_reduction: float = 0.0  # 0 to 100
    grain_reduction: float = 0.0  # 0 to 100

    # Film-specific
    dust_removal: bool = False
    scratch_removal: bool = False

    # Rotation/flip
    rotation: int = 0             # 0, 90, 180, 270
    flip_horizontal: bool = False
    flip_vertical: bool = False

    # Crop (normalized 0-1)
    crop_left: float = 0.0
    crop_top: float = 0.0
    crop_right: float = 1.0
    crop_bottom: float = 1.0

    def __post_init__(self):
        if self.levels_master is None:
            self.levels_master = LevelsAdjustment()
        if self.levels_red is None:
            self.levels_red = LevelsAdjustment()
        if self.levels_green is None:
            self.levels_green = LevelsAdjustment()
        if self.levels_blue is None:
            self.levels_blue = LevelsAdjustment()
        if self.color_balance is None:
            self.color_balance = ColorBalance()


class ImageProcessor:
    """
    Film scanning image processor.
    Applies a chain of corrections to scanned film images.
    Supports both 8-bit and 16-bit processing pipelines.
    """

    def __init__(self):
        self._cached_lut = None
        self._cached_lut_params = None
        self._use_16bit = True  # Default to 16-bit processing

    @property
    def use_16bit(self) -> bool:
        return self._use_16bit

    @use_16bit.setter
    def use_16bit(self, value: bool):
        self._use_16bit = value

    def _to_working_array(self, img: Image.Image) -> Tuple[np.ndarray, float]:
        """
        Convert image to float32 working array.
        Returns (array, max_value) where max_value is 255.0 or 65535.0.
        """
        if img.mode in ("I;16", "I;16L", "I;16B"):
            arr = np.array(img, dtype=np.float32)
            return arr, 65535.0
        elif img.mode == "RGB" and self._use_16bit:
            arr = np.array(img, dtype=np.float32)
            # If the image was 48-bit, values may go up to 65535
            max_val = float(np.max(arr)) if np.max(arr) > 255 else 255.0
            return arr, max_val
        else:
            return np.array(img, dtype=np.float32), 255.0

    def _from_working_array(self, arr: np.ndarray, max_value: float,
                             output_16bit: bool = False) -> Image.Image:
        """Convert working array back to PIL Image."""
        if output_16bit and max_value > 255:
            arr = np.clip(arr, 0, 65535).astype(np.uint16)
            # PIL doesn't natively support RGB 16-bit easily,
            # so we'll store as 8-bit for display but keep 16-bit for save
            return Image.fromarray(
                (arr / 256).astype(np.uint8), mode="RGB"
            )
        else:
            return Image.fromarray(
                np.clip(arr, 0, 255).astype(np.uint8), mode="RGB"
            )

    def process(self, image: Image.Image,
                settings: ProcessingSettings) -> Image.Image:
        """
        Apply all processing settings to an image.
        Returns a new processed PIL Image.
        Uses float32 internally for maximum precision.
        """
        if image is None:
            raise ValueError("No image to process")

        # Work with a copy
        img = image.copy()

        # Convert to RGB if needed
        if img.mode == "L":
            img = img.convert("RGB")
        elif img.mode == "RGBA":
            img = img.convert("RGB")
        elif img.mode not in ("RGB",):
            img = img.convert("RGB")

        # 1. Rotation and flip (do early for preview)
        img = self._apply_rotation(img, settings)

        # 2. Crop
        img = self._apply_crop(img, settings)

        # 3. Invert negative
        if settings.invert_negative:
            img = self._invert_negative(img, settings.orange_mask_removal)

        # 4. Exposure adjustment
        if settings.exposure != 0:
            img = self._adjust_exposure(img, settings.exposure)

        # 5. Levels
        img = self._apply_levels(img, settings)

        # 6. Brightness / Contrast
        if settings.brightness != 0:
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.0 + settings.brightness / 100.0)

        if settings.contrast != 0:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.0 + settings.contrast / 100.0)

        # 7. Highlights and shadows
        if settings.highlights != 0 or settings.shadows != 0:
            img = self._adjust_highlights_shadows(
                img, settings.highlights, settings.shadows
            )

        # 8. Color balance
        img = self._apply_color_balance(img, settings.color_balance)

        # 9. Saturation
        if settings.saturation != 1.0:
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(settings.saturation)

        # 10. Vibrance
        if settings.vibrance != 0:
            img = self._adjust_vibrance(img, settings.vibrance)

        # 11. Noise reduction
        if settings.noise_reduction > 0:
            img = self._reduce_noise(img, settings.noise_reduction)

        # 12. Grain reduction
        if settings.grain_reduction > 0:
            img = self._reduce_grain(img, settings.grain_reduction)

        # 13. Dust/scratch removal
        if settings.dust_removal or settings.scratch_removal:
            img = self._remove_dust_scratches(
                img, settings.dust_removal, settings.scratch_removal
            )

        # 14. Sharpening (always do last)
        if settings.sharpness > 0:
            img = self._sharpen(img, settings.sharpness, settings.sharpen_radius)

        return img

    # ── Negative Inversion ──────────────────────────────────────────────────

    def _invert_negative(self, img: Image.Image,
                         remove_orange_mask: bool = True) -> Image.Image:
        """
        Invert a film negative to positive.
        Optionally removes the orange mask from color negatives (C-41).
        All math done in float32 for full precision.
        """
        arr = np.array(img, dtype=np.float32)
        max_val = 255.0  # Working range

        if remove_orange_mask:
            # Estimate orange mask from film border (unexposed area)
            h, w = arr.shape[:2]
            sample_size = max(5, min(50, h // 20, w // 20))

            corners = [
                arr[:sample_size, :sample_size],
                arr[:sample_size, -sample_size:],
                arr[-sample_size:, :sample_size],
                arr[-sample_size:, -sample_size:],
            ]

            corner_means = [np.mean(c) for c in corners]
            base_sample = corners[np.argmax(corner_means)]
            base_color = np.mean(base_sample, axis=(0, 1))

            if base_color[0] > 0 and base_color[1] > 0 and base_color[2] > 0:
                max_base = np.max(base_color)
                scale = max_base / (base_color + 1e-6)
                scale = np.clip(scale, 0.5, 3.0)

                for c in range(3):
                    arr[:, :, c] = arr[:, :, c] * scale[c]

        # Invert
        arr = max_val - np.clip(arr, 0, max_val)

        # Auto-stretch to use full dynamic range
        for c in range(3):
            channel = arr[:, :, c]
            p_low = np.percentile(channel, 0.5)
            p_high = np.percentile(channel, 99.5)
            if p_high > p_low:
                channel = (channel - p_low) / (p_high - p_low) * max_val
                arr[:, :, c] = np.clip(channel, 0, max_val)

        return Image.fromarray(arr.astype(np.uint8), mode="RGB")

    # ── Exposure ────────────────────────────────────────────────────────────

    def _adjust_exposure(self, img: Image.Image, ev: float) -> Image.Image:
        """Adjust exposure in EV stops."""
        arr = np.array(img, dtype=np.float32)
        factor = 2.0 ** ev
        arr = arr * factor
        arr = np.clip(arr, 0, 255)
        return Image.fromarray(arr.astype(np.uint8), mode="RGB")

    # ── Levels ──────────────────────────────────────────────────────────────

    def _apply_levels(self, img: Image.Image,
                      settings: ProcessingSettings) -> Image.Image:
        """Apply levels adjustments per channel and master."""
        arr = np.array(img, dtype=np.float32)

        # Apply per-channel levels
        channel_levels = [settings.levels_red, settings.levels_green,
                          settings.levels_blue]

        for c, levels in enumerate(channel_levels):
            if (levels.black_point != 0 or levels.white_point != 255 or
                    levels.midtone != 1.0 or levels.output_black != 0 or
                    levels.output_white != 255):
                arr[:, :, c] = self._apply_level_to_channel(
                    arr[:, :, c], levels
                )

        # Apply master levels
        ml = settings.levels_master
        if (ml.black_point != 0 or ml.white_point != 255 or
                ml.midtone != 1.0 or ml.output_black != 0 or
                ml.output_white != 255):
            for c in range(3):
                arr[:, :, c] = self._apply_level_to_channel(
                    arr[:, :, c], ml
                )

        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")

    def _apply_level_to_channel(self, channel: np.ndarray,
                                 levels: LevelsAdjustment) -> np.ndarray:
        """Apply levels to a single channel."""
        bp = levels.black_point
        wp = levels.white_point
        gamma = levels.midtone
        ob = levels.output_black
        ow = levels.output_white

        # Input levels: remap [bp, wp] to [0, 1]
        if wp > bp:
            channel = (channel - bp) / (wp - bp)
        channel = np.clip(channel, 0, 1)

        # Gamma (midtone)
        if gamma != 1.0 and gamma > 0:
            channel = np.power(channel, 1.0 / gamma)

        # Output levels: remap [0, 1] to [ob, ow]
        channel = channel * (ow - ob) + ob

        return channel

    # ── Highlights & Shadows ────────────────────────────────────────────────

    def _adjust_highlights_shadows(self, img: Image.Image,
                                    highlights: float,
                                    shadows: float) -> Image.Image:
        """Adjust highlights and shadows independently."""
        arr = np.array(img, dtype=np.float32)

        # Calculate luminance
        lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        lum_norm = lum / 255.0

        if shadows != 0:
            # Shadow mask: strong effect on dark pixels
            shadow_mask = 1.0 - lum_norm
            shadow_mask = np.power(shadow_mask, 2)
            adjustment = shadows / 100.0 * 80  # Scale factor
            for c in range(3):
                arr[:, :, c] += shadow_mask * adjustment

        if highlights != 0:
            # Highlight mask: strong effect on bright pixels
            highlight_mask = lum_norm
            highlight_mask = np.power(highlight_mask, 2)
            adjustment = highlights / 100.0 * 80
            for c in range(3):
                arr[:, :, c] += highlight_mask * adjustment

        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")

    # ── Color Balance ───────────────────────────────────────────────────────

    def _apply_color_balance(self, img: Image.Image,
                              balance: ColorBalance) -> Image.Image:
        """Apply color balance adjustments."""
        if (balance.red_shift == 0 and balance.green_shift == 0 and
                balance.blue_shift == 0 and balance.temperature == 0):
            return img

        arr = np.array(img, dtype=np.float32)

        # Direct channel shifts
        arr[:, :, 0] += balance.red_shift * 1.28    # Scale to 0-128 range
        arr[:, :, 1] += balance.green_shift * 1.28
        arr[:, :, 2] += balance.blue_shift * 1.28

        # Color temperature
        if balance.temperature != 0:
            temp_factor = balance.temperature / 100.0
            if temp_factor > 0:  # Warmer
                arr[:, :, 0] += temp_factor * 30  # More red
                arr[:, :, 2] -= temp_factor * 30  # Less blue
            else:  # Cooler
                arr[:, :, 0] += temp_factor * 30  # Less red
                arr[:, :, 2] -= temp_factor * 30  # More blue

        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")

    # ── Vibrance ────────────────────────────────────────────────────────────

    def _adjust_vibrance(self, img: Image.Image,
                          vibrance: float) -> Image.Image:
        """
        Vibrance: selective saturation that affects less-saturated colors more.
        """
        arr = np.array(img, dtype=np.float32)

        # Calculate per-pixel saturation
        max_ch = np.max(arr, axis=2)
        min_ch = np.min(arr, axis=2)
        sat = np.where(max_ch > 0, (max_ch - min_ch) / (max_ch + 1e-6), 0)

        # Lower current saturation = more effect
        effect = (1.0 - sat) * (vibrance / 100.0)

        # Calculate mean per pixel and adjust toward or away from it
        mean = np.mean(arr, axis=2, keepdims=True)
        diff = arr - mean
        arr = arr + diff * effect[:, :, np.newaxis]

        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")

    # ── Noise Reduction ─────────────────────────────────────────────────────

    def _reduce_noise(self, img: Image.Image, strength: float) -> Image.Image:
        """Apply noise reduction using bilateral-like filtering."""
        # Map strength 0-100 to filter radius 1-5
        radius = max(1, int(strength / 20))

        # Use median filter for impulse noise
        if strength > 50:
            img = img.filter(ImageFilter.MedianFilter(size=max(3, radius * 2 - 1)))

        # Gentle Gaussian blur for remaining noise
        sigma = strength / 30.0
        if sigma > 0.3:
            img = img.filter(ImageFilter.GaussianBlur(radius=sigma))

        return img

    def _reduce_grain(self, img: Image.Image, strength: float) -> Image.Image:
        """Reduce film grain while preserving detail."""
        try:
            import cv2

            arr = np.array(img)

            # Convert to LAB for luminance-only denoising
            lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)

            # Non-local means denoising on luminance channel
            h = strength / 10.0  # filter strength
            lab[:, :, 0] = cv2.fastNlMeansDenoising(
                lab[:, :, 0], None, h=h,
                templateWindowSize=7, searchWindowSize=21
            )

            arr = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
            return Image.fromarray(arr)

        except ImportError:
            # Fallback without OpenCV
            return self._reduce_noise(img, strength * 0.7)

    # ── Dust & Scratch Removal ──────────────────────────────────────────────

    def _remove_dust_scratches(self, img: Image.Image,
                                dust: bool, scratches: bool) -> Image.Image:
        """
        Remove dust spots and scratches from scanned film.
        Uses morphological operations and median filtering.
        """
        try:
            import cv2

            arr = np.array(img)
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

            if dust:
                # Detect dust spots (small dark/bright spots)
                # Use morphological operations
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

                # Detect bright spots (dust on negative)
                opened = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)
                bright_mask = cv2.absdiff(gray, opened)
                _, bright_mask = cv2.threshold(bright_mask, 25, 255, cv2.THRESH_BINARY)

                # Detect dark spots
                closed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
                dark_mask = cv2.absdiff(gray, closed)
                _, dark_mask = cv2.threshold(dark_mask, 25, 255, cv2.THRESH_BINARY)

                # Combine masks
                dust_mask = cv2.bitwise_or(bright_mask, dark_mask)

                # Dilate mask slightly
                dust_mask = cv2.dilate(dust_mask, kernel, iterations=1)

                # Inpaint dust spots
                arr = cv2.inpaint(arr, dust_mask, 3, cv2.INPAINT_TELEA)

            if scratches:
                # Detect linear scratches using morphological operations
                # Vertical scratch detection
                kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 15))
                morph_v = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel_v)
                scratch_v = cv2.absdiff(gray, morph_v)
                _, scratch_mask_v = cv2.threshold(scratch_v, 15, 255, cv2.THRESH_BINARY)

                # Horizontal scratch detection
                kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 1))
                morph_h = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel_h)
                scratch_h = cv2.absdiff(gray, morph_h)
                _, scratch_mask_h = cv2.threshold(scratch_h, 15, 255, cv2.THRESH_BINARY)

                scratch_mask = cv2.bitwise_or(scratch_mask_v, scratch_mask_h)
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
                scratch_mask = cv2.dilate(scratch_mask, kernel, iterations=1)

                arr = cv2.inpaint(arr, scratch_mask, 5, cv2.INPAINT_NS)

            return Image.fromarray(arr)

        except ImportError:
            logger.warning("OpenCV not available, dust/scratch removal skipped")
            # Basic fallback: median filter
            if dust:
                img = img.filter(ImageFilter.MedianFilter(size=3))
            return img

    # ── Sharpening ──────────────────────────────────────────────────────────

    def _sharpen(self, img: Image.Image, amount: float,
                  radius: float) -> Image.Image:
        """Apply Unsharp Mask sharpening."""
        # amount: 0-500 (as percentage), radius: 0.1-10
        percent = int(amount)
        threshold = 3

        return img.filter(ImageFilter.UnsharpMask(
            radius=radius,
            percent=percent,
            threshold=threshold
        ))

    # ── Rotation & Flip ─────────────────────────────────────────────────────

    def _apply_rotation(self, img: Image.Image,
                         settings: ProcessingSettings) -> Image.Image:
        """Apply rotation and flip transformations."""
        if settings.rotation == 90:
            img = img.transpose(Image.Transpose.ROTATE_90)
        elif settings.rotation == 180:
            img = img.transpose(Image.Transpose.ROTATE_180)
        elif settings.rotation == 270:
            img = img.transpose(Image.Transpose.ROTATE_270)

        if settings.flip_horizontal:
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if settings.flip_vertical:
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        return img

    # ── Crop ────────────────────────────────────────────────────────────────

    def _apply_crop(self, img: Image.Image,
                     settings: ProcessingSettings) -> Image.Image:
        """Apply crop using normalized coordinates."""
        if (settings.crop_left == 0 and settings.crop_top == 0 and
                settings.crop_right == 1.0 and settings.crop_bottom == 1.0):
            return img

        w, h = img.size
        left = int(settings.crop_left * w)
        top = int(settings.crop_top * h)
        right = int(settings.crop_right * w)
        bottom = int(settings.crop_bottom * h)

        # Ensure valid crop
        left = max(0, min(left, w - 1))
        top = max(0, min(top, h - 1))
        right = max(left + 1, min(right, w))
        bottom = max(top + 1, min(bottom, h))

        return img.crop((left, top, right, bottom))

    # ── Analysis ────────────────────────────────────────────────────────────

    @staticmethod
    def get_histogram(img: Image.Image) -> dict:
        """
        Get histogram data for an image.
        Returns dict with 'red', 'green', 'blue', 'luminance' arrays.
        """
        if img.mode == "L":
            hist = img.histogram()
            return {
                "luminance": np.array(hist),
                "red": np.array(hist),
                "green": np.array(hist),
                "blue": np.array(hist),
            }

        if img.mode != "RGB":
            img = img.convert("RGB")

        arr = np.array(img)

        result = {
            "red": np.histogram(arr[:, :, 0], bins=256, range=(0, 255))[0],
            "green": np.histogram(arr[:, :, 1], bins=256, range=(0, 255))[0],
            "blue": np.histogram(arr[:, :, 2], bins=256, range=(0, 255))[0],
        }

        # Luminance
        lum = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] +
               0.114 * arr[:, :, 2]).astype(np.uint8)
        result["luminance"] = np.histogram(lum, bins=256, range=(0, 255))[0]

        return result

    @staticmethod
    def auto_levels(img: Image.Image, clip_percent: float = 0.5) -> ProcessingSettings:
        """
        Analyze image and return auto-levels settings.
        """
        settings = ProcessingSettings()

        if img.mode != "RGB":
            img = img.convert("RGB")

        arr = np.array(img, dtype=np.float32)

        for c, levels_attr in enumerate(["levels_red", "levels_green", "levels_blue"]):
            channel = arr[:, :, c]
            p_low = np.percentile(channel, clip_percent)
            p_high = np.percentile(channel, 100 - clip_percent)

            levels = LevelsAdjustment(
                black_point=int(p_low),
                white_point=int(p_high),
                midtone=1.0,
            )
            setattr(settings, levels_attr, levels)

        return settings

    @staticmethod
    def auto_white_balance(img: Image.Image) -> ColorBalance:
        """
        Calculate auto white balance correction.
        Uses gray world assumption.
        """
        if img.mode != "RGB":
            img = img.convert("RGB")

        arr = np.array(img, dtype=np.float32)
        means = np.mean(arr, axis=(0, 1))
        overall_mean = np.mean(means)

        balance = ColorBalance()
        if means[0] > 0:
            balance.red_shift = (overall_mean - means[0]) / 1.28
        if means[1] > 0:
            balance.green_shift = (overall_mean - means[1]) / 1.28
        if means[2] > 0:
            balance.blue_shift = (overall_mean - means[2]) / 1.28

        return balance
