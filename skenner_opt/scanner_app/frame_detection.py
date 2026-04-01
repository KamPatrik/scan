"""
Frame detection and auto-crop for film scanning.
Provides:
- Automatic frame detection on film strip scans
- Auto-crop to image content
- Auto-deskew (rotation correction)
- Film holder templates with pre-defined frame positions
- Film base color sampling for accurate mask removal
"""

import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class DetectedFrame:
    """A single detected film frame with its bounding box."""
    index: int = 0
    left: float = 0.0    # Normalized 0-1
    top: float = 0.0
    right: float = 1.0
    bottom: float = 1.0
    rotation: float = 0.0  # Deskew angle in degrees
    confidence: float = 0.0  # Detection confidence 0-1

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    def to_pixel_box(self, img_w: int, img_h: int) -> Tuple[int, int, int, int]:
        """Convert normalized coords to pixel bounding box (left, top, right, bottom)."""
        return (
            int(self.left * img_w),
            int(self.top * img_h),
            int(self.right * img_w),
            int(self.bottom * img_h),
        )


@dataclass
class FilmHolderTemplate:
    """Pre-defined frame positions for a film holder/carrier."""
    name: str = ""
    description: str = ""
    # List of (left, top, right, bottom) normalized within the holder scan area
    frames: List[Tuple[float, float, float, float]] = None

    def __post_init__(self):
        if self.frames is None:
            self.frames = []


# ── Film Holder Templates ──────────────────────────────────────────────────

# Epson V370 35mm film strip holder: holds 2 strips of 6 frames
HOLDER_V370_35MM_STRIP = FilmHolderTemplate(
    name="Epson V370 — 35mm Strip (6 frames)",
    description="Standard Epson V370 film strip holder, 6 frames per strip",
    frames=[
        # Approximate normalized positions for 6 frames in a strip
        # These assume the full transparency scan area
        (0.020, 0.08, 0.155, 0.92),
        (0.170, 0.08, 0.305, 0.92),
        (0.320, 0.08, 0.455, 0.92),
        (0.470, 0.08, 0.605, 0.92),
        (0.620, 0.08, 0.755, 0.92),
        (0.770, 0.08, 0.905, 0.92),
    ]
)

HOLDER_V370_SLIDE = FilmHolderTemplate(
    name="Epson V370 — 35mm Slides (4 mounts)",
    description="Epson V370 slide mount holder, 4 mounted slides",
    frames=[
        (0.030, 0.05, 0.235, 0.48),
        (0.270, 0.05, 0.475, 0.48),
        (0.030, 0.52, 0.235, 0.95),
        (0.270, 0.52, 0.475, 0.95),
    ]
)

HOLDER_V370_120 = FilmHolderTemplate(
    name="Epson V370 — 120 Medium Format",
    description="Epson V370 medium format holder, single strip",
    frames=[
        # 120 6x6 frames (approximate for 3 frames on a strip)
        (0.05, 0.05, 0.35, 0.95),
        (0.37, 0.05, 0.67, 0.95),
        (0.69, 0.05, 0.95, 0.95),
    ]
)

ALL_HOLDERS = [HOLDER_V370_35MM_STRIP, HOLDER_V370_SLIDE, HOLDER_V370_120]


# ── Frame Detection ────────────────────────────────────────────────────────

class FrameDetector:
    """
    Automatically detect individual film frames on a scanned film strip.
    Uses edge/gap detection on the dark inter-frame areas.
    """

    def __init__(self):
        self._min_frame_ratio = 0.03  # Min frame width as ratio of image width
        self._gap_threshold = 0.6     # How dark a gap must be (0=black, 1=white)

    def detect_frames(self, image: Image.Image,
                      orientation: str = "horizontal") -> List[DetectedFrame]:
        """
        Detect film frames in a scanned image.

        Args:
            image: PIL Image of the scanned film strip
            orientation: "horizontal" (frames side by side) or "vertical"

        Returns:
            List of DetectedFrame objects sorted left-to-right (or top-to-bottom)
        """
        arr = np.array(image.convert("L"), dtype=np.float32) / 255.0
        h, w = arr.shape

        if orientation == "horizontal":
            return self._detect_horizontal(arr, w, h)
        else:
            return self._detect_vertical(arr, w, h)

    def _detect_horizontal(self, arr: np.ndarray,
                            w: int, h: int) -> List[DetectedFrame]:
        """Detect frames arranged horizontally (standard 35mm strip layout)."""
        # Compute column-wise mean brightness
        # Exclude top/bottom borders (sprocket hole area for 35mm)
        border_skip = max(1, int(h * 0.1))
        col_means = np.mean(arr[border_skip:h - border_skip, :], axis=0)

        # Smooth the profile to reduce noise
        kernel_size = max(3, w // 200)
        if kernel_size % 2 == 0:
            kernel_size += 1
        col_smooth = np.convolve(
            col_means, np.ones(kernel_size) / kernel_size, mode='same'
        )

        # Find the threshold for "dark gap" between frames
        # Film base (unexposed) is typically dark on a negative, bright on inverted
        # We look for the darkest valleys as frame separators
        p10 = np.percentile(col_smooth, 10)
        p90 = np.percentile(col_smooth, 90)
        threshold = p10 + (p90 - p10) * 0.35

        # Find dark regions (below threshold) = inter-frame gaps
        is_dark = col_smooth < threshold
        frames = self._find_segments(is_dark, w, h, axis="x")
        return frames

    def _detect_vertical(self, arr: np.ndarray,
                          w: int, h: int) -> List[DetectedFrame]:
        """Detect frames arranged vertically."""
        border_skip = max(1, int(w * 0.1))
        row_means = np.mean(arr[:, border_skip:w - border_skip], axis=1)

        kernel_size = max(3, h // 200)
        if kernel_size % 2 == 0:
            kernel_size += 1
        row_smooth = np.convolve(
            row_means, np.ones(kernel_size) / kernel_size, mode='same'
        )

        p10 = np.percentile(row_smooth, 10)
        p90 = np.percentile(row_smooth, 90)
        threshold = p10 + (p90 - p10) * 0.35

        is_dark = row_smooth < threshold
        frames = self._find_segments(is_dark, w, h, axis="y")
        return frames

    def _find_segments(self, is_dark: np.ndarray, img_w: int, img_h: int,
                        axis: str) -> List[DetectedFrame]:
        """Find bright segments (frames) separated by dark gaps."""
        length = len(is_dark)
        min_frame_size = int(length * self._min_frame_ratio)

        # Find transitions
        segments = []
        in_frame = False
        frame_start = 0

        for i in range(length):
            if not is_dark[i] and not in_frame:
                in_frame = True
                frame_start = i
            elif is_dark[i] and in_frame:
                in_frame = False
                frame_end = i
                if (frame_end - frame_start) >= min_frame_size:
                    segments.append((frame_start, frame_end))

        # Handle last segment
        if in_frame and (length - frame_start) >= min_frame_size:
            segments.append((frame_start, length))

        # Convert to DetectedFrame objects
        frames = []
        for idx, (start, end) in enumerate(segments):
            # Add small margin
            margin = int((end - start) * 0.01)
            start = max(0, start - margin)
            end = min(length, end + margin)

            if axis == "x":
                frame = DetectedFrame(
                    index=idx,
                    left=start / img_w,
                    top=0.0,
                    right=end / img_w,
                    bottom=1.0,
                    confidence=0.8,
                )
            else:
                frame = DetectedFrame(
                    index=idx,
                    left=0.0,
                    top=start / img_h,
                    right=1.0,
                    bottom=end / img_h,
                    confidence=0.8,
                )
            frames.append(frame)

        logger.info(f"Frame detection: found {len(frames)} frames")
        return frames

    def detect_with_opencv(self, image: Image.Image,
                            orientation: str = "horizontal") -> List[DetectedFrame]:
        """
        Advanced frame detection using OpenCV contour analysis.
        More accurate but requires OpenCV.
        """
        try:
            import cv2
        except ImportError:
            logger.warning("OpenCV not available, falling back to basic detection")
            return self.detect_frames(image, orientation)

        arr = np.array(image.convert("L"))
        h, w = arr.shape

        # Adaptive threshold to find frame content
        blur = cv2.GaussianBlur(arr, (5, 5), 0)
        _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=3)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Filter contours by size (must be large enough to be a frame)
        min_area = h * w * 0.02  # At least 2% of total image area
        frame_contours = [c for c in contours if cv2.contourArea(c) > min_area]

        # Sort by position
        if orientation == "horizontal":
            frame_contours.sort(key=lambda c: cv2.boundingRect(c)[0])
        else:
            frame_contours.sort(key=lambda c: cv2.boundingRect(c)[1])

        frames = []
        for idx, contour in enumerate(frame_contours):
            x, y, cw, ch = cv2.boundingRect(contour)

            # Compute deskew angle using minAreaRect
            rect = cv2.minAreaRect(contour)
            angle = rect[2]
            if angle < -45:
                angle += 90

            frame = DetectedFrame(
                index=idx,
                left=x / w,
                top=y / h,
                right=(x + cw) / w,
                bottom=(y + ch) / h,
                rotation=angle,
                confidence=min(1.0, cv2.contourArea(contour) / (cw * ch)),
            )
            frames.append(frame)

        logger.info(f"OpenCV frame detection: found {len(frames)} frames")
        return frames


# ── Auto-Crop & Deskew ─────────────────────────────────────────────────────

def auto_crop(image: Image.Image, border_percent: float = 1.0) -> Image.Image:
    """
    Automatically crop an image to its content, removing dark borders.

    Args:
        image: PIL Image
        border_percent: Additional border to keep (percent of content size)
    """
    arr = np.array(image.convert("L"), dtype=np.float32)
    h, w = arr.shape

    # Threshold to find content
    threshold = np.percentile(arr, 15)  # Bottom 15% is "border"

    # Find bounding box of content
    mask = arr > threshold
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)

    if not np.any(rows) or not np.any(cols):
        return image  # Nothing to crop

    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    # Add margin
    margin_h = int((rmax - rmin) * border_percent / 100)
    margin_w = int((cmax - cmin) * border_percent / 100)

    rmin = max(0, rmin - margin_h)
    rmax = min(h, rmax + margin_h + 1)
    cmin = max(0, cmin - margin_w)
    cmax = min(w, cmax + margin_w + 1)

    return image.crop((cmin, rmin, cmax, rmax))


def auto_deskew(image: Image.Image) -> Tuple[Image.Image, float]:
    """
    Automatically straighten a slightly rotated image.
    Returns (corrected_image, rotation_angle_degrees).
    """
    try:
        import cv2
    except ImportError:
        return image, 0.0

    arr = np.array(image.convert("L"))

    # Edge detection
    edges = cv2.Canny(arr, 50, 150, apertureSize=3)

    # Hough line detection
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=100,
        minLineLength=arr.shape[1] // 4, maxLineGap=20
    )

    if lines is None or len(lines) == 0:
        return image, 0.0

    # Compute angles of detected lines
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 - x1 == 0:
            continue
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))

        # Only consider near-horizontal or near-vertical lines
        if abs(angle) < 15:
            angles.append(angle)
        elif abs(angle - 90) < 15 or abs(angle + 90) < 15:
            angles.append(angle - 90 if angle > 0 else angle + 90)

    if not angles:
        return image, 0.0

    # Use median angle for robustness
    median_angle = np.median(angles)

    if abs(median_angle) < 0.1:
        return image, 0.0  # Already straight

    # Rotate to correct
    corrected = image.rotate(
        -median_angle, resample=Image.Resampling.BICUBIC,
        expand=True, fillcolor=(0, 0, 0)
    )

    logger.info(f"Auto-deskew: corrected by {median_angle:.2f}°")
    return corrected, median_angle


def sample_film_base(image: Image.Image,
                      region: Tuple[float, float, float, float] = None
                      ) -> Tuple[int, int, int]:
    """
    Sample the film base color from an unexposed region.

    Args:
        image: PIL Image of the raw scan
        region: (left, top, right, bottom) normalized. If None, auto-detect.

    Returns:
        (R, G, B) tuple of the film base color.
    """
    arr = np.array(image.convert("RGB"), dtype=np.float32)
    h, w = arr.shape[:2]

    if region:
        x1 = int(region[0] * w)
        y1 = int(region[1] * h)
        x2 = int(region[2] * w)
        y2 = int(region[3] * h)
        sample = arr[y1:y2, x1:x2]
    else:
        # Auto: sample corners and pick the brightest (most likely film base)
        cs = max(5, min(50, h // 10, w // 10))
        corners = [
            arr[:cs, :cs],
            arr[:cs, -cs:],
            arr[-cs:, :cs],
            arr[-cs:, -cs:],
        ]
        means = [np.mean(c) for c in corners]
        sample = corners[np.argmax(means)]

    base_color = np.mean(sample, axis=(0, 1))
    r, g, b = int(base_color[0]), int(base_color[1]), int(base_color[2])

    logger.info(f"Film base color sampled: R={r} G={g} B={b}")
    return (r, g, b)


def extract_frame(image: Image.Image, frame: DetectedFrame,
                   deskew: bool = True) -> Image.Image:
    """
    Extract a single frame from a film strip scan.

    Args:
        image: Full film strip scan
        frame: DetectedFrame with bounding box
        deskew: Whether to correct rotation
    """
    w, h = image.size
    box = frame.to_pixel_box(w, h)
    cropped = image.crop(box)

    if deskew and abs(frame.rotation) > 0.2:
        cropped = cropped.rotate(
            -frame.rotation, resample=Image.Resampling.BICUBIC,
            expand=True, fillcolor=(0, 0, 0)
        )
        # Re-crop to remove fill
        cropped = auto_crop(cropped, border_percent=0.5)

    return cropped
