"""
Preset management: save, load, import, and export processing presets.
Also handles session settings persistence (remember last-used settings).
"""

import json
import logging
import os
import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

from .image_processor import ProcessingSettings, LevelsAdjustment, ColorBalance
from .utils import get_app_data_dir

logger = logging.getLogger(__name__)

PRESETS_DIR = os.path.join(get_app_data_dir(), "presets")
SESSION_FILE = os.path.join(get_app_data_dir(), "last_session.json")


@dataclass
class Preset:
    """A named processing settings preset."""
    name: str = "Untitled Preset"
    description: str = ""
    category: str = "User"
    created: str = ""
    modified: str = ""
    film_profile: str = ""
    settings: Optional[ProcessingSettings] = None

    def __post_init__(self):
        if not self.created:
            self.created = datetime.datetime.now().isoformat()
        if not self.modified:
            self.modified = self.created
        if self.settings is None:
            self.settings = ProcessingSettings()


def _settings_to_dict(settings: ProcessingSettings) -> dict:
    """Convert ProcessingSettings to a JSON-serializable dict."""
    d = {}
    d["invert_negative"] = settings.invert_negative
    d["orange_mask_removal"] = settings.orange_mask_removal
    d["saturation"] = settings.saturation
    d["vibrance"] = settings.vibrance
    d["exposure"] = settings.exposure
    d["brightness"] = settings.brightness
    d["contrast"] = settings.contrast
    d["highlights"] = settings.highlights
    d["shadows"] = settings.shadows
    d["sharpness"] = settings.sharpness
    d["sharpen_radius"] = settings.sharpen_radius
    d["noise_reduction"] = settings.noise_reduction
    d["grain_reduction"] = settings.grain_reduction
    d["dust_removal"] = settings.dust_removal
    d["scratch_removal"] = settings.scratch_removal
    d["rotation"] = settings.rotation
    d["flip_horizontal"] = settings.flip_horizontal
    d["flip_vertical"] = settings.flip_vertical
    d["crop_left"] = settings.crop_left
    d["crop_top"] = settings.crop_top
    d["crop_right"] = settings.crop_right
    d["crop_bottom"] = settings.crop_bottom

    # Levels
    if settings.levels_master:
        d["levels_master"] = {
            "black_point": settings.levels_master.black_point,
            "white_point": settings.levels_master.white_point,
            "midtone": settings.levels_master.midtone,
            "output_black": settings.levels_master.output_black,
            "output_white": settings.levels_master.output_white,
        }

    # Color balance
    if settings.color_balance:
        d["color_balance"] = {
            "red_shift": settings.color_balance.red_shift,
            "green_shift": settings.color_balance.green_shift,
            "blue_shift": settings.color_balance.blue_shift,
            "temperature": settings.color_balance.temperature,
        }

    return d


def _dict_to_settings(d: dict) -> ProcessingSettings:
    """Convert a dict back to ProcessingSettings."""
    levels_data = d.get("levels_master", {})
    levels = LevelsAdjustment(
        black_point=levels_data.get("black_point", 0),
        white_point=levels_data.get("white_point", 255),
        midtone=levels_data.get("midtone", 1.0),
        output_black=levels_data.get("output_black", 0),
        output_white=levels_data.get("output_white", 255),
    )

    cb_data = d.get("color_balance", {})
    color_balance = ColorBalance(
        red_shift=cb_data.get("red_shift", 0.0),
        green_shift=cb_data.get("green_shift", 0.0),
        blue_shift=cb_data.get("blue_shift", 0.0),
        temperature=cb_data.get("temperature", 0.0),
    )

    return ProcessingSettings(
        invert_negative=d.get("invert_negative", False),
        orange_mask_removal=d.get("orange_mask_removal", False),
        levels_master=levels,
        saturation=d.get("saturation", 1.0),
        vibrance=d.get("vibrance", 0.0),
        exposure=d.get("exposure", 0.0),
        brightness=d.get("brightness", 0.0),
        contrast=d.get("contrast", 0.0),
        highlights=d.get("highlights", 0.0),
        shadows=d.get("shadows", 0.0),
        sharpness=d.get("sharpness", 0.0),
        sharpen_radius=d.get("sharpen_radius", 1.0),
        noise_reduction=d.get("noise_reduction", 0.0),
        grain_reduction=d.get("grain_reduction", 0.0),
        dust_removal=d.get("dust_removal", False),
        scratch_removal=d.get("scratch_removal", False),
        rotation=d.get("rotation", 0),
        flip_horizontal=d.get("flip_horizontal", False),
        flip_vertical=d.get("flip_vertical", False),
        crop_left=d.get("crop_left", 0.0),
        crop_top=d.get("crop_top", 0.0),
        crop_right=d.get("crop_right", 1.0),
        crop_bottom=d.get("crop_bottom", 1.0),
    )


def _preset_to_dict(preset: Preset) -> dict:
    """Serialize a Preset to dict."""
    return {
        "name": preset.name,
        "description": preset.description,
        "category": preset.category,
        "created": preset.created,
        "modified": preset.modified,
        "film_profile": preset.film_profile,
        "settings": _settings_to_dict(preset.settings),
    }


def _dict_to_preset(d: dict) -> Preset:
    """Deserialize a Preset from dict."""
    return Preset(
        name=d.get("name", "Untitled"),
        description=d.get("description", ""),
        category=d.get("category", "User"),
        created=d.get("created", ""),
        modified=d.get("modified", ""),
        film_profile=d.get("film_profile", ""),
        settings=_dict_to_settings(d.get("settings", {})),
    )


# ── Preset CRUD ────────────────────────────────────────────────────────────

def _ensure_presets_dir():
    os.makedirs(PRESETS_DIR, exist_ok=True)


def save_preset(preset: Preset) -> str:
    """Save a preset to disk. Returns the file path."""
    _ensure_presets_dir()

    # Sanitize filename
    safe_name = "".join(
        c if c.isalnum() or c in "._- " else "_"
        for c in preset.name
    ).strip()
    if not safe_name:
        safe_name = "preset"

    filepath = os.path.join(PRESETS_DIR, f"{safe_name}.json")
    preset.modified = datetime.datetime.now().isoformat()

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(_preset_to_dict(preset), f, indent=2)

    logger.info(f"Preset saved: {filepath}")
    return filepath


def load_preset(filepath: str) -> Optional[Preset]:
    """Load a preset from a JSON file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _dict_to_preset(data)
    except Exception as e:
        logger.error(f"Failed to load preset from {filepath}: {e}")
        return None


def list_presets() -> List[Preset]:
    """List all saved presets."""
    _ensure_presets_dir()
    presets = []

    for filename in sorted(os.listdir(PRESETS_DIR)):
        if filename.endswith(".json") and filename != "last_session.json":
            filepath = os.path.join(PRESETS_DIR, filename)
            preset = load_preset(filepath)
            if preset:
                presets.append(preset)

    return presets


def delete_preset(name: str) -> bool:
    """Delete a preset by name."""
    _ensure_presets_dir()
    safe_name = "".join(
        c if c.isalnum() or c in "._- " else "_"
        for c in name
    ).strip()
    filepath = os.path.join(PRESETS_DIR, f"{safe_name}.json")

    if os.path.exists(filepath):
        os.remove(filepath)
        logger.info(f"Preset deleted: {filepath}")
        return True
    return False


def export_preset(preset: Preset, filepath: str):
    """Export a preset to an arbitrary file location."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(_preset_to_dict(preset), f, indent=2)
    logger.info(f"Preset exported: {filepath}")


def import_preset(filepath: str) -> Optional[Preset]:
    """Import a preset from an external file."""
    preset = load_preset(filepath)
    if preset:
        save_preset(preset)  # Save to presets dir
    return preset


# ── Session Persistence ────────────────────────────────────────────────────

def save_session(settings_dict: Dict[str, Any]):
    """
    Save current session state (all UI settings) for restoration on next launch.
    """
    try:
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(settings_dict, f, indent=2)
        logger.debug("Session saved")
    except Exception as e:
        logger.warning(f"Failed to save session: {e}")


def load_session() -> Optional[Dict[str, Any]]:
    """Load saved session state from last run."""
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("Session loaded")
        return data
    except Exception as e:
        logger.warning(f"Failed to load session: {e}")
        return None


def get_full_session_dict(scan_settings_dict: dict,
                           processing_dict: dict,
                           ui_state: dict) -> dict:
    """Pack all session state into a single dict for persistence."""
    return {
        "version": "1.0",
        "saved_at": datetime.datetime.now().isoformat(),
        "scan_settings": scan_settings_dict,
        "processing": processing_dict,
        "ui_state": ui_state,
    }


def unpack_session(data: dict) -> tuple:
    """Unpack session dict into (scan_dict, processing_dict, ui_dict)."""
    return (
        data.get("scan_settings", {}),
        data.get("processing", {}),
        data.get("ui_state", {}),
    )


# ── Built-in Presets ──────────────────────────────────────────────────────

def get_builtin_presets() -> List[Preset]:
    """Return a list of built-in, read-only presets."""
    presets = []

    # Clean scan — minimal processing
    presets.append(Preset(
        name="Clean Scan (Minimal)",
        description="No processing adjustments — just inversion and orange mask.",
        category="Built-in",
        settings=ProcessingSettings(
            invert_negative=True,
            orange_mask_removal=True,
        ),
    ))

    # High contrast B&W
    presets.append(Preset(
        name="High Contrast B&W",
        description="Strong blacks and whites for B&W film.",
        category="Built-in",
        settings=ProcessingSettings(
            invert_negative=True,
            contrast=30.0,
            brightness=5.0,
            levels_master=LevelsAdjustment(
                black_point=15,
                white_point=240,
                midtone=1.1,
            ),
            sharpness=80,
        ),
    ))

    # Vintage warm
    presets.append(Preset(
        name="Vintage Warm",
        description="Warm tones with slightly faded look.",
        category="Built-in",
        settings=ProcessingSettings(
            invert_negative=True,
            orange_mask_removal=True,
            color_balance=ColorBalance(
                temperature=15.0,
                red_shift=5.0,
                green_shift=-2.0,
            ),
            saturation=0.9,
            contrast=-10.0,
            levels_master=LevelsAdjustment(
                output_black=10,
                output_white=245,
            ),
        ),
    ))

    # Slide/chrome accurate
    presets.append(Preset(
        name="Slide Film Accurate",
        description="Clean, accurate reproduction for positive/slide film.",
        category="Built-in",
        settings=ProcessingSettings(
            invert_negative=False,
            orange_mask_removal=False,
            saturation=1.1,
            contrast=10.0,
            sharpness=50,
            sharpen_radius=0.8,
        ),
    ))

    # Heavy grain reduction
    presets.append(Preset(
        name="Grain Tamer",
        description="Aggressive grain/noise reduction for high-ISO film.",
        category="Built-in",
        settings=ProcessingSettings(
            invert_negative=True,
            orange_mask_removal=True,
            noise_reduction=60,
            grain_reduction=50,
            sharpness=40,
            sharpen_radius=1.5,
        ),
    ))

    return presets
