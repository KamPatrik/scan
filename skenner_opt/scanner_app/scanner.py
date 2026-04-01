"""
Scanner communication layer using Windows Image Acquisition (WIA) API.
Provides direct control of the Epson V370 scanner including:
- Device discovery and connection
- Resolution, color mode, and scan area control
- Preview and full-resolution scanning
- Transparency unit (film scanning) support
"""

import os
import sys
import logging
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Callable
from PIL import Image
import io
import numpy as np

logger = logging.getLogger(__name__)


# ── WIA Constants ──────────────────────────────────────────────────────────────

class WiaProperty(IntEnum):
    """WIA property IDs for scanner control."""
    DEVICE_ID = 2
    DEVICE_NAME = 7
    ITEM_NAME = 4098
    FULL_ITEM_NAME = 4099
    # Scan settings
    HORIZONTAL_RESOLUTION = 6147
    VERTICAL_RESOLUTION = 6148
    HORIZONTAL_START = 6149
    VERTICAL_START = 6150
    HORIZONTAL_EXTENT = 6151
    VERTICAL_EXTENT = 6152
    BRIGHTNESS = 6154
    CONTRAST = 6155
    DATA_TYPE = 4103  # Color mode
    BITS_PER_PIXEL = 4104
    CURRENT_INTENT = 6146
    # Document handling
    DOCUMENT_HANDLING_SELECT = 3088
    PAGES = 3096
    # Light source / backlight control
    LAMP = 6158                       # Lamp on/off
    LAMP_WARMUP_TIME = 6161           # Lamp warmup time in ms
    # Epson-specific and extended WIA properties for transparency unit
    FILM_SCAN_MODE = 6159             # Film scan mode selector
    DOCUMENT_HANDLING_STATUS = 3087   # Document handling status
    DOCUMENT_HANDLING_CAPABILITIES = 3086  # Capabilities bitfield


class WiaDocumentHandling(IntEnum):
    """WIA Document Handling Select flags for scan source."""
    FLATBED = 0x01
    FEEDER = 0x02
    DUPLEX = 0x04
    # Transparency / backlight (Transparency Processing Unit)
    TRANSPARENCY_ADAPTER = 0x04  # Some scanners use bit 2
    FILM_TPU = 0x10              # Epson TPU (backlight) flag
    FRONT_ONLY = 0x08


class WiaLightSource(IntEnum):
    """Light source modes for Epson scanners."""
    REFLECTIVE = 0   # Normal flatbed (top light)
    TRANSPARENCY = 1  # Backlight ON (transparency unit / film)
    NEGATIVE = 2      # Backlight ON + negative mode
    POSITIVE = 3      # Backlight ON + positive/slide mode


class WiaDataType(IntEnum):
    """WIA color mode constants."""
    COLOR = 3
    GRAYSCALE = 2
    BW = 0


class WiaIntent(IntEnum):
    """WIA scanning intent."""
    COLOR = 1
    GRAYSCALE = 2
    TEXT = 4


class WiaImageFormat:
    """WIA image format GUIDs."""
    BMP = "{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}"
    PNG = "{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}"
    JPEG = "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}"
    TIFF = "{B96B3CB1-0728-11D3-9D7B-0000F81EF32E}"
    RAW = "{B96B3CA9-0728-11D3-9D7B-0000F81EF32E}"


class ScanSource(Enum):
    """Scan source selection."""
    FLATBED = "flatbed"
    TRANSPARENCY = "transparency"  # For film scanning


class ColorMode(Enum):
    """Color mode selection."""
    COLOR = "color"
    GRAYSCALE = "grayscale"
    BLACK_WHITE = "bw"


@dataclass
class ScanArea:
    """Scan area in inches from top-left corner."""
    left: float = 0.0
    top: float = 0.0
    width: float = 8.5
    height: float = 11.7

    # Epson V370 transparency unit area (approximate)
    @staticmethod
    def film_35mm() -> 'ScanArea':
        """Standard 35mm film strip area on Epson V370 transparency unit."""
        return ScanArea(left=0.5, top=0.5, width=6.0, height=1.5)

    @staticmethod
    def film_35mm_slide() -> 'ScanArea':
        """Single 35mm slide mount area."""
        return ScanArea(left=0.5, top=0.5, width=1.5, height=1.1)

    @staticmethod
    def film_120() -> 'ScanArea':
        """Medium format 120 film area."""
        return ScanArea(left=0.5, top=0.5, width=2.5, height=3.5)

    @staticmethod
    def full_flatbed() -> 'ScanArea':
        """Full A4 flatbed area."""
        return ScanArea(left=0.0, top=0.0, width=8.5, height=11.7)

    @staticmethod
    def full_transparency() -> 'ScanArea':
        """Full transparency unit area on Epson V370."""
        return ScanArea(left=0.2, top=0.2, width=3.9, height=6.9)


@dataclass
class ScanSettings:
    """Complete scan configuration."""
    resolution: int = 2400       # DPI - high for film
    color_mode: ColorMode = ColorMode.COLOR
    source: ScanSource = ScanSource.TRANSPARENCY
    scan_area: ScanArea = field(default_factory=ScanArea.film_35mm)
    brightness: int = 0          # -1000 to 1000
    contrast: int = 0            # -1000 to 1000
    bit_depth: int = 48          # 24 or 48 bit color
    multi_pass: bool = False     # Multiple passes for quality
    infrared_clean: bool = False # IR dust removal if supported


@dataclass
class ScannerInfo:
    """Information about a connected scanner."""
    device_id: str = ""
    name: str = ""
    manufacturer: str = ""
    model: str = ""
    has_transparency: bool = False
    max_resolution: int = 4800
    min_resolution: int = 75


class ScannerError(Exception):
    """Base exception for scanner operations."""
    pass


class ScannerNotFoundError(ScannerError):
    """No scanner device found."""
    pass


class ScannerBusyError(ScannerError):
    """Scanner is currently busy."""
    pass


class ScannerCommunicationError(ScannerError):
    """Communication error with scanner."""
    pass


class WIAScanner:
    """
    Windows Image Acquisition (WIA) scanner interface.
    Provides direct control of scanners via the WIA COM API.
    Optimized for the Epson V370 with transparency unit.
    """

    def __init__(self):
        self._device = None
        self._device_manager = None
        self._scanner_info: Optional[ScannerInfo] = None
        self._connected = False
        self._wia_available = False
        self._init_wia()

    def _init_wia(self):
        """Initialize the WIA COM interface."""
        try:
            import comtypes.client
            self._device_manager = comtypes.client.CreateObject(
                "WIA.DeviceManager"
            )
            self._wia_available = True
            logger.info("WIA interface initialized successfully")
        except Exception as e:
            logger.warning(f"WIA not available: {e}")
            self._wia_available = False
            # Try win32com as fallback
            try:
                import win32com.client
                self._device_manager = win32com.client.Dispatch(
                    "WIA.DeviceManager"
                )
                self._wia_available = True
                logger.info("WIA interface initialized via win32com")
            except Exception as e2:
                logger.error(f"WIA fallback also failed: {e2}")
                self._wia_available = False

    @property
    def is_available(self) -> bool:
        """Check if WIA is available on this system."""
        return self._wia_available

    @property
    def is_connected(self) -> bool:
        """Check if a scanner is connected."""
        return self._connected and self._device is not None

    @property
    def scanner_info(self) -> Optional[ScannerInfo]:
        """Get info about the connected scanner."""
        return self._scanner_info

    def list_scanners(self) -> List[ScannerInfo]:
        """List all available WIA scanner devices."""
        scanners = []
        if not self._wia_available:
            logger.warning("WIA not available, returning empty scanner list")
            return scanners

        try:
            device_infos = self._device_manager.DeviceInfos
            for i in range(1, device_infos.Count + 1):
                dev_info = device_infos.Item(i)
                # Type 1 = Scanner
                if dev_info.Type == 1:
                    info = ScannerInfo()
                    try:
                        for prop in dev_info.Properties:
                            if prop.PropertyID == 2:  # Device ID
                                info.device_id = prop.Value
                            elif prop.PropertyID == 7:  # Device Name
                                info.name = prop.Value
                            elif prop.PropertyID == 8:  # Description
                                info.manufacturer = prop.Value
                            elif prop.PropertyID == 9:  # Device Type
                                info.model = prop.Value
                    except Exception:
                        info.name = f"Scanner {i}"
                        info.device_id = str(i)

                    # Check for Epson V370 transparency support
                    name_lower = info.name.lower()
                    if "v370" in name_lower or "perfection" in name_lower:
                        info.has_transparency = True
                        info.max_resolution = 4800

                    scanners.append(info)
                    logger.info(f"Found scanner: {info.name} ({info.device_id})")

        except Exception as e:
            logger.error(f"Error listing scanners: {e}")

        return scanners

    def connect(self, device_id: Optional[str] = None) -> ScannerInfo:
        """
        Connect to a scanner device.
        If device_id is None, connects to the first available scanner.
        """
        if not self._wia_available:
            raise ScannerError("WIA is not available on this system")

        try:
            scanners = self.list_scanners()
            if not scanners:
                raise ScannerNotFoundError(
                    "No scanners found. Please check that your Epson V370 "
                    "is connected and drivers are installed."
                )

            target_info = None
            if device_id:
                for s in scanners:
                    if s.device_id == device_id:
                        target_info = s
                        break
                if not target_info:
                    raise ScannerNotFoundError(
                        f"Scanner with ID '{device_id}' not found"
                    )
            else:
                # Prefer Epson V370 if multiple scanners found
                for s in scanners:
                    if "v370" in s.name.lower() or "epson" in s.name.lower():
                        target_info = s
                        break
                if not target_info:
                    target_info = scanners[0]

            # Connect to the device
            device_infos = self._device_manager.DeviceInfos
            for i in range(1, device_infos.Count + 1):
                dev_info = device_infos.Item(i)
                found = False
                try:
                    for prop in dev_info.Properties:
                        if prop.PropertyID == 2 and prop.Value == target_info.device_id:
                            found = True
                            break
                except Exception:
                    pass

                if found:
                    self._device = dev_info.Connect()
                    self._scanner_info = target_info
                    self._connected = True
                    logger.info(f"Connected to: {target_info.name}")
                    return target_info

            raise ScannerCommunicationError("Failed to establish connection")

        except ScannerError:
            raise
        except Exception as e:
            raise ScannerCommunicationError(f"Connection failed: {e}")

    def disconnect(self):
        """Disconnect from the current scanner."""
        self._device = None
        self._connected = False
        self._scanner_info = None
        logger.info("Scanner disconnected")

    def _get_scan_item(self):
        """Get the scanner item for scanning operations."""
        if not self._device:
            raise ScannerError("No scanner connected")

        items = self._device.Items
        if items.Count == 0:
            raise ScannerError("No scan items available on device")
        return items.Item(1)

    def _set_property(self, item, prop_id: int, value):
        """Set a WIA property on a scan item."""
        try:
            props = item.Properties
            for prop in props:
                if prop.PropertyID == prop_id:
                    prop.Value = value
                    return True
        except Exception as e:
            logger.warning(f"Could not set property {prop_id}: {e}")
        return False

    def _get_property(self, item, prop_id: int):
        """Get a WIA property value."""
        try:
            props = item.Properties
            for prop in props:
                if prop.PropertyID == prop_id:
                    return prop.Value
        except Exception as e:
            logger.warning(f"Could not get property {prop_id}: {e}")
        return None

    def _configure_backlight(self, settings: ScanSettings):
        """
        Configure the scanner's light source / backlight for the Epson V370.

        For transparency (film) scanning, the scanner's transparency unit (TPU)
        lid backlight must be activated so light passes through the film.
        For flatbed scanning, the normal reflective light is used.

        The Epson V370 TPU is controlled via:
        1. WIA Document Handling Select property on the device root
        2. The LAMP property on the scan item
        3. Epson-specific FILM_SCAN_MODE property
        """
        if not self._device:
            return

        is_transparency = (settings.source == ScanSource.TRANSPARENCY)

        # ── Method 1: Set Document Handling Select on device root ─────
        # This tells the scanner to switch between flatbed and TPU
        try:
            dev_props = self._device.Properties
            for prop in dev_props:
                if prop.PropertyID == WiaProperty.DOCUMENT_HANDLING_SELECT:
                    if is_transparency:
                        # Enable TPU / transparency adapter
                        prop.Value = (
                            WiaDocumentHandling.FLATBED
                            | WiaDocumentHandling.FILM_TPU
                        )
                        logger.info("Backlight: Document handling set to TPU mode")
                    else:
                        prop.Value = WiaDocumentHandling.FLATBED
                        logger.info("Backlight: Document handling set to flatbed mode")
                    break
        except Exception as e:
            logger.debug(f"Could not set Document Handling Select: {e}")

        # ── Method 2: Set light source on scan item ───────────────────
        # Some Epson WIA drivers expose a light source / lamp property
        try:
            item = self._get_scan_item()

            # Try to enable/disable the lamp
            if is_transparency:
                self._set_property(item, WiaProperty.LAMP, 1)  # Lamp ON
                logger.info("Backlight: Lamp enabled for transparency scan")
            else:
                self._set_property(item, WiaProperty.LAMP, 0)  # Lamp OFF
                logger.info("Backlight: Lamp set to reflective mode")

            # Try Epson film scan mode property
            if is_transparency:
                self._set_property(
                    item, WiaProperty.FILM_SCAN_MODE,
                    WiaLightSource.TRANSPARENCY
                )
                logger.info("Backlight: Film scan mode set to transparency")
            else:
                self._set_property(
                    item, WiaProperty.FILM_SCAN_MODE,
                    WiaLightSource.REFLECTIVE
                )

        except Exception as e:
            logger.debug(f"Could not set lamp/film_scan_mode property: {e}")

        # ── Method 3: Enumerate all properties and find light-related ones ──
        # Fallback for drivers that use non-standard property IDs
        try:
            item = self._get_scan_item()
            props = item.Properties
            for prop in props:
                prop_name = ""
                try:
                    prop_name = str(prop.Name).lower()
                except Exception:
                    pass

                # Look for light source / backlight / TPU properties by name
                if any(kw in prop_name for kw in [
                    "light", "lamp", "tpu", "transparency",
                    "backlight", "film", "source"
                ]):
                    try:
                        if is_transparency:
                            # Try setting to transparency/backlight value
                            prop.Value = 1
                            logger.info(
                                f"Backlight: Set '{prop.Name}' "
                                f"(ID={prop.PropertyID}) = 1"
                            )
                        else:
                            prop.Value = 0
                            logger.info(
                                f"Backlight: Set '{prop.Name}' "
                                f"(ID={prop.PropertyID}) = 0"
                            )
                    except Exception:
                        pass  # Read-only or invalid value
        except Exception as e:
            logger.debug(f"Property enumeration for backlight failed: {e}")

        if is_transparency:
            logger.info(
                "Backlight configuration complete — "
                "TPU (transparency) mode active"
            )
        else:
            logger.info(
                "Backlight configuration complete — "
                "reflective (flatbed) mode active"
            )

    def _configure_scan(self, item, settings: ScanSettings):
        """Apply scan settings to the WIA item."""
        # ── Configure backlight / light source FIRST ──────────────────
        self._configure_backlight(settings)

        # Set resolution
        self._set_property(item, WiaProperty.HORIZONTAL_RESOLUTION, settings.resolution)
        self._set_property(item, WiaProperty.VERTICAL_RESOLUTION, settings.resolution)

        # Set color mode
        if settings.color_mode == ColorMode.COLOR:
            self._set_property(item, WiaProperty.DATA_TYPE, WiaDataType.COLOR)
            self._set_property(item, WiaProperty.CURRENT_INTENT, WiaIntent.COLOR)
        elif settings.color_mode == ColorMode.GRAYSCALE:
            self._set_property(item, WiaProperty.DATA_TYPE, WiaDataType.GRAYSCALE)
            self._set_property(item, WiaProperty.CURRENT_INTENT, WiaIntent.GRAYSCALE)
        else:
            self._set_property(item, WiaProperty.DATA_TYPE, WiaDataType.BW)
            self._set_property(item, WiaProperty.CURRENT_INTENT, WiaIntent.TEXT)

        # Set scan area (convert inches to pixels at given resolution)
        area = settings.scan_area
        h_start = int(area.left * settings.resolution)
        v_start = int(area.top * settings.resolution)
        h_extent = int(area.width * settings.resolution)
        v_extent = int(area.height * settings.resolution)

        self._set_property(item, WiaProperty.HORIZONTAL_START, h_start)
        self._set_property(item, WiaProperty.VERTICAL_START, v_start)
        self._set_property(item, WiaProperty.HORIZONTAL_EXTENT, h_extent)
        self._set_property(item, WiaProperty.VERTICAL_EXTENT, v_extent)

        # Set brightness and contrast
        if settings.brightness != 0:
            self._set_property(item, WiaProperty.BRIGHTNESS, settings.brightness)
        if settings.contrast != 0:
            self._set_property(item, WiaProperty.CONTRAST, settings.contrast)

        logger.info(
            f"Scan configured: {settings.resolution}dpi, "
            f"{settings.color_mode.value}, "
            f"source={settings.source.value}, "
            f"area=({area.left},{area.top},{area.width},{area.height})"
        )

    def preview(self, settings: Optional[ScanSettings] = None,
                progress_callback: Optional[Callable] = None) -> Optional[Image.Image]:
        """
        Perform a low-resolution preview scan.
        Returns a PIL Image or None on failure.
        """
        if not self.is_connected:
            raise ScannerError("No scanner connected")

        preview_settings = ScanSettings(
            resolution=150,  # Low res for preview
            color_mode=settings.color_mode if settings else ColorMode.COLOR,
            source=settings.source if settings else ScanSource.FLATBED,
            scan_area=settings.scan_area if settings else ScanArea.full_flatbed(),
            brightness=settings.brightness if settings else 0,
            contrast=settings.contrast if settings else 0,
        )

        return self._do_scan(preview_settings, progress_callback)

    def scan(self, settings: ScanSettings,
             progress_callback: Optional[Callable] = None) -> Optional[Image.Image]:
        """
        Perform a full-resolution scan with the given settings.
        Returns a PIL Image or None on failure.
        """
        if not self.is_connected:
            raise ScannerError("No scanner connected")

        return self._do_scan(settings, progress_callback)

    def _do_scan(self, settings: ScanSettings,
                 progress_callback: Optional[Callable] = None) -> Optional[Image.Image]:
        """Execute the actual scan operation."""
        try:
            item = self._get_scan_item()
            self._configure_scan(item, settings)

            if progress_callback:
                progress_callback(10, "Scanning...")

            # Transfer image
            import comtypes.client
            image_file = None
            try:
                image_file = item.Transfer(WiaImageFormat.BMP)
            except Exception:
                try:
                    import win32com.client
                    image_file = item.Transfer(WiaImageFormat.BMP)
                except Exception as e:
                    raise ScannerCommunicationError(f"Transfer failed: {e}")

            if progress_callback:
                progress_callback(70, "Processing image...")

            if image_file is None:
                raise ScannerCommunicationError("No image data received")

            # Convert WIA ImageFile to PIL Image
            # Save to temp file and read back
            import tempfile
            temp_path = os.path.join(tempfile.gettempdir(), "skenner_scan.bmp")
            image_file.SaveFile(temp_path)

            img = Image.open(temp_path)
            img.load()  # Ensure image is fully loaded

            # Clean up temp
            try:
                os.remove(temp_path)
            except Exception:
                pass

            if progress_callback:
                progress_callback(100, "Scan complete")

            logger.info(f"Scan complete: {img.size[0]}x{img.size[1]} pixels")
            return img

        except ScannerError:
            raise
        except Exception as e:
            raise ScannerCommunicationError(f"Scan failed: {e}")

    def scan_to_file(self, settings: ScanSettings, output_path: str,
                     file_format: str = "tiff",
                     progress_callback: Optional[Callable] = None) -> str:
        """
        Scan and save directly to a file.
        Returns the output file path.
        """
        img = self.scan(settings, progress_callback)
        if img is None:
            raise ScannerError("Scan returned no image")

        # Determine format and save
        fmt_map = {
            "tiff": ("TIFF", ".tif"),
            "tif": ("TIFF", ".tif"),
            "png": ("PNG", ".png"),
            "jpeg": ("JPEG", ".jpg"),
            "jpg": ("JPEG", ".jpg"),
            "bmp": ("BMP", ".bmp"),
        }

        fmt_info = fmt_map.get(file_format.lower(), ("TIFF", ".tif"))
        if not output_path.lower().endswith(fmt_info[1]):
            output_path += fmt_info[1]

        save_kwargs = {}
        if fmt_info[0] == "TIFF":
            save_kwargs["compression"] = "tiff_lzw"
        elif fmt_info[0] == "JPEG":
            save_kwargs["quality"] = 95

        img.save(output_path, fmt_info[0], **save_kwargs)
        logger.info(f"Saved scan to: {output_path}")
        return output_path


class DemoScanner:
    """
    Demo/simulator scanner for testing without hardware.
    Generates synthetic scan data that mimics film negatives.
    """

    def __init__(self):
        self._connected = False
        self._scanner_info = ScannerInfo(
            device_id="DEMO-V370",
            name="Epson Perfection V370 (Demo)",
            manufacturer="Epson",
            model="Perfection V370",
            has_transparency=True,
            max_resolution=4800,
            min_resolution=75,
        )

    @property
    def is_available(self) -> bool:
        return True

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def scanner_info(self) -> Optional[ScannerInfo]:
        return self._scanner_info if self._connected else None

    def list_scanners(self) -> List[ScannerInfo]:
        return [self._scanner_info]

    def connect(self, device_id: Optional[str] = None) -> ScannerInfo:
        self._connected = True
        logger.info("Demo scanner connected")
        return self._scanner_info

    def disconnect(self):
        self._connected = False

    def preview(self, settings=None, progress_callback=None) -> Optional[Image.Image]:
        return self._generate_demo_image(settings, low_res=True,
                                          progress_callback=progress_callback)

    def scan(self, settings=None, progress_callback=None) -> Optional[Image.Image]:
        return self._generate_demo_image(settings, low_res=False,
                                          progress_callback=progress_callback)

    def scan_to_file(self, settings, output_path, file_format="tiff",
                     progress_callback=None) -> str:
        img = self.scan(settings, progress_callback)
        if img:
            img.save(output_path)
        return output_path

    def _generate_demo_image(self, settings=None, low_res=False,
                              progress_callback=None) -> Image.Image:
        """Generate a synthetic film scan for demonstration."""
        if progress_callback:
            progress_callback(10, "Initializing scan...")

        res = 150 if low_res else (settings.resolution if settings else 600)
        area = settings.scan_area if settings else ScanArea.film_35mm()
        w = int(area.width * res)
        h = int(area.height * res)

        # Limit size for demo
        w = min(w, 4000)
        h = min(h, 3000)

        if progress_callback:
            progress_callback(30, "Capturing...")

        # Generate a synthetic film negative pattern
        rng = np.random.default_rng(42)
        img_data = np.zeros((h, w, 3), dtype=np.uint8)

        # Create gradient background (simulating film base)
        for y in range(h):
            for c in range(3):
                base = 40 + int(20 * np.sin(2 * np.pi * y / h))
                img_data[y, :, c] = base

        if progress_callback:
            progress_callback(50, "Processing...")

        # Add some circular "exposures" simulating film frames
        num_frames = min(6, max(1, w // (h + 10)))
        frame_w = (w - 20) // num_frames
        for i in range(num_frames):
            fx = 10 + i * frame_w + frame_w // 2
            fy = h // 2
            radius = min(frame_w, h) // 3

            # Create a soft circle
            yy, xx = np.ogrid[-fy:h - fy, -fx:w - fx]
            dist = np.sqrt(xx * xx + yy * yy)
            mask = np.clip(1.0 - dist / radius, 0, 1)

            # Add colored content (inverted for negative)
            colors = [
                [200, 150, 100],
                [100, 200, 150],
                [150, 100, 200],
                [180, 180, 100],
                [100, 180, 180],
                [180, 100, 180],
            ]
            color = colors[i % len(colors)]
            for c in range(3):
                img_data[:, :, c] = np.clip(
                    img_data[:, :, c].astype(float) + mask * color[c],
                    0, 255
                ).astype(np.uint8)

        # Add film grain noise
        noise = rng.integers(-15, 15, size=(h, w, 3), dtype=np.int16)
        img_data = np.clip(img_data.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # Add film border (sprocket holes for 35mm)
        if settings and settings.source == ScanSource.TRANSPARENCY:
            # Dark borders
            border = 15
            img_data[:border, :] = 20
            img_data[-border:, :] = 20
            # Sprocket hole indicators
            hole_spacing = w // 12
            for x in range(hole_spacing // 2, w, hole_spacing):
                x1 = max(0, x - 4)
                x2 = min(w, x + 4)
                img_data[:8, x1:x2] = 180
                img_data[-8:, x1:x2] = 180

        if progress_callback:
            progress_callback(90, "Finalizing...")

        # Determine color mode
        mode = "RGB"
        if settings and settings.color_mode == ColorMode.GRAYSCALE:
            gray = np.mean(img_data, axis=2).astype(np.uint8)
            img = Image.fromarray(gray, mode="L")
        else:
            img = Image.fromarray(img_data, mode=mode)

        if progress_callback:
            progress_callback(100, "Complete")

        return img


def get_scanner(use_demo: bool = False):
    """
    Factory function to get the appropriate scanner interface.
    Returns WIAScanner if available, otherwise DemoScanner.
    """
    if use_demo:
        return DemoScanner()

    scanner = WIAScanner()
    if scanner.is_available:
        return scanner

    logger.warning("WIA not available, falling back to demo scanner")
    return DemoScanner()
