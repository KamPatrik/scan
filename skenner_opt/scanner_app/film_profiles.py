"""
Film color profiles for common film stocks.
Provides pre-configured processing settings for accurate color reproduction
from various film types (negatives, slides, B&W).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .image_processor import (
    ProcessingSettings, LevelsAdjustment, ColorBalance
)


@dataclass
class FilmProfile:
    """
    A film profile defines processing parameters for a specific film stock.
    """
    name: str = ""
    category: str = ""          # "Color Negative", "Color Slide", "B&W Negative"
    manufacturer: str = ""
    iso: int = 0
    description: str = ""

    # Base processing settings
    processing: ProcessingSettings = field(default_factory=ProcessingSettings)

    # Film base color (for orange mask removal on negatives)
    base_r: int = 0
    base_g: int = 0
    base_b: int = 0


def _create_color_neg_profile(name: str, manufacturer: str, iso: int,
                                description: str,
                                base_rgb: tuple = (180, 120, 70),
                                saturation: float = 1.1,
                                contrast: float = 10.0,
                                temperature: float = 0.0,
                                r_shift: float = 0.0,
                                g_shift: float = 0.0,
                                b_shift: float = 0.0) -> FilmProfile:
    """Helper to create a color negative film profile."""
    proc = ProcessingSettings()
    proc.invert_negative = True
    proc.orange_mask_removal = True
    proc.saturation = saturation
    proc.contrast = contrast
    proc.color_balance = ColorBalance(
        red_shift=r_shift, green_shift=g_shift,
        blue_shift=b_shift, temperature=temperature
    )
    return FilmProfile(
        name=name, category="Color Negative", manufacturer=manufacturer,
        iso=iso, description=description, processing=proc,
        base_r=base_rgb[0], base_g=base_rgb[1], base_b=base_rgb[2],
    )


def _create_slide_profile(name: str, manufacturer: str, iso: int,
                           description: str,
                           saturation: float = 1.2,
                           contrast: float = 15.0,
                           temperature: float = 0.0,
                           vibrance: float = 10.0) -> FilmProfile:
    """Helper to create a color slide/reversal film profile."""
    proc = ProcessingSettings()
    proc.invert_negative = False
    proc.orange_mask_removal = False
    proc.saturation = saturation
    proc.contrast = contrast
    proc.vibrance = vibrance
    proc.color_balance = ColorBalance(temperature=temperature)
    return FilmProfile(
        name=name, category="Color Slide", manufacturer=manufacturer,
        iso=iso, description=description, processing=proc,
    )


def _create_bw_profile(name: str, manufacturer: str, iso: int,
                        description: str,
                        contrast: float = 15.0,
                        brightness: float = 0.0) -> FilmProfile:
    """Helper to create a B&W negative film profile."""
    proc = ProcessingSettings()
    proc.invert_negative = True
    proc.orange_mask_removal = False
    proc.saturation = 0.0  # Desaturate
    proc.contrast = contrast
    proc.brightness = brightness
    return FilmProfile(
        name=name, category="B&W Negative", manufacturer=manufacturer,
        iso=iso, description=description, processing=proc,
    )


# ── Film Profile Database ──────────────────────────────────────────────────

FILM_PROFILES: Dict[str, FilmProfile] = {}


def _register_profiles():
    """Register all built-in film profiles."""
    global FILM_PROFILES

    profiles = [
        # ── Generic Profiles ────────────────────────────────────────────
        FilmProfile(
            name="Generic Color Negative",
            category="Color Negative",
            manufacturer="Generic",
            description="Default settings for color negative (C-41) film",
            processing=ProcessingSettings(
                invert_negative=True,
                orange_mask_removal=True,
                saturation=1.1,
                contrast=10.0,
            ),
        ),
        FilmProfile(
            name="Generic Color Slide",
            category="Color Slide",
            manufacturer="Generic",
            description="Default settings for color slide/reversal (E-6) film",
            processing=ProcessingSettings(
                invert_negative=False,
                saturation=1.2,
                contrast=15.0,
            ),
        ),
        FilmProfile(
            name="Generic B&W Negative",
            category="B&W Negative",
            manufacturer="Generic",
            description="Default settings for black and white negative film",
            processing=ProcessingSettings(
                invert_negative=True,
                orange_mask_removal=False,
                saturation=0.0,
                contrast=15.0,
            ),
        ),
        FilmProfile(
            name="No Processing",
            category="None",
            manufacturer="Generic",
            description="Raw scan with no adjustments applied",
            processing=ProcessingSettings(),
        ),

        # ── Kodak Color Negatives ───────────────────────────────────────
        _create_color_neg_profile(
            "Kodak Portra 160", "Kodak", 160,
            "Fine grain, natural colors, excellent skin tones",
            base_rgb=(185, 125, 75), saturation=1.05, contrast=8.0,
            temperature=2.0,
        ),
        _create_color_neg_profile(
            "Kodak Portra 400", "Kodak", 400,
            "Versatile portrait film, pleasant warm tones",
            base_rgb=(180, 120, 70), saturation=1.08, contrast=8.0,
            temperature=3.0,
        ),
        _create_color_neg_profile(
            "Kodak Portra 800", "Kodak", 800,
            "High-speed portrait film, slightly more grain",
            base_rgb=(175, 118, 68), saturation=1.05, contrast=7.0,
            temperature=3.0,
        ),
        _create_color_neg_profile(
            "Kodak Ektar 100", "Kodak", 100,
            "Ultra-vivid colors, finest grain color negative",
            base_rgb=(190, 130, 80), saturation=1.35, contrast=18.0,
            temperature=-2.0,
        ),
        _create_color_neg_profile(
            "Kodak Gold 200", "Kodak", 200,
            "Consumer film, warm tones, saturated colors",
            base_rgb=(185, 125, 72), saturation=1.25, contrast=12.0,
            temperature=5.0,
        ),
        _create_color_neg_profile(
            "Kodak ColorPlus 200", "Kodak", 200,
            "Budget-friendly, good everyday colors",
            base_rgb=(182, 122, 70), saturation=1.15, contrast=10.0,
            temperature=3.0,
        ),
        _create_color_neg_profile(
            "Kodak Ultramax 400", "Kodak", 400,
            "All-purpose consumer film, punchy colors",
            base_rgb=(178, 120, 68), saturation=1.2, contrast=12.0,
            temperature=4.0,
        ),

        # ── Fuji Color Negatives ────────────────────────────────────────
        _create_color_neg_profile(
            "Fuji Superia 400", "Fujifilm", 400,
            "Popular consumer film, cooler tones, good greens",
            base_rgb=(170, 118, 72), saturation=1.15, contrast=12.0,
            temperature=-3.0, g_shift=3.0,
        ),
        _create_color_neg_profile(
            "Fuji C200", "Fujifilm", 200,
            "Budget film, slightly cool, natural rendition",
            base_rgb=(172, 120, 74), saturation=1.1, contrast=10.0,
            temperature=-2.0,
        ),
        _create_color_neg_profile(
            "Fuji Pro 400H", "Fujifilm", 400,
            "Professional, fine grain, slightly desaturated pastels",
            base_rgb=(168, 116, 70), saturation=0.95, contrast=7.0,
            temperature=-1.0,
        ),

        # ── Harman Color Negatives ──────────────────────────────────────
        # Harman Phoenix 200: Harman Technology's (Ilford) first color film.
        # C-41 process. Defining traits: extreme halation (red/orange glow
        # around highlights from minimal anti-halation backing), very
        # prominent grain for ISO 200, high contrast, strong warm/red color
        # shift, vivid bleeding reds, muted greens and blues, narrow
        # exposure latitude, and a lighter reddish-amber film base compared
        # to Kodak stocks. An intentionally "imperfect" experimental film
        # with a lo-fi, artistic aesthetic.
        _create_color_neg_profile(
            "Harman Phoenix 200", "Harman", 200,
            "Experimental C-41 film by Ilford/Harman. Extreme halation, "
            "heavy grain, high contrast, vivid bleeding reds, warm cast, "
            "muted greens/blues. Lo-fi creative aesthetic",
            base_rgb=(160, 105, 60),   # Lighter reddish-amber base (thinner mask)
            saturation=1.30,            # Highly saturated, especially reds
            contrast=22.0,              # Notably high contrast for a negative film
            temperature=10.0,           # Strong warm shift (signature look)
            r_shift=8.0,               # Pronounced red channel push (halation/red cast)
            g_shift=-3.0,              # Slightly suppressed greens
            b_shift=-5.0,             # Muted blues
        ),

        # ── Kodak Slide Films ──────────────────────────────────────────
        _create_slide_profile(
            "Kodak Ektachrome E100", "Kodak", 100,
            "Modern Ektachrome, clean colors, neutral balance",
            saturation=1.2, contrast=15.0, temperature=0.0, vibrance=15.0,
        ),
        _create_slide_profile(
            "Kodachrome 64", "Kodak", 64,
            "Legendary warm tones, rich reds and blues",
            saturation=1.3, contrast=20.0, temperature=5.0, vibrance=20.0,
        ),

        # ── Fuji Slide Films ───────────────────────────────────────────
        _create_slide_profile(
            "Fuji Velvia 50", "Fujifilm", 50,
            "Hyper-saturated, vivid colors, high contrast",
            saturation=1.5, contrast=22.0, temperature=-2.0, vibrance=25.0,
        ),
        _create_slide_profile(
            "Fuji Velvia 100", "Fujifilm", 100,
            "Very saturated with slightly less contrast than Velvia 50",
            saturation=1.4, contrast=18.0, temperature=-2.0, vibrance=20.0,
        ),
        _create_slide_profile(
            "Fuji Provia 100F", "Fujifilm", 100,
            "Neutral, accurate colors, fine grain",
            saturation=1.15, contrast=14.0, temperature=-1.0, vibrance=10.0,
        ),
        _create_slide_profile(
            "Fuji Astia 100F", "Fujifilm", 100,
            "Soft, natural, lower contrast slide film",
            saturation=1.05, contrast=10.0, temperature=0.0, vibrance=5.0,
        ),

        # ── B&W Negative Films ─────────────────────────────────────────
        _create_bw_profile(
            "Kodak Tri-X 400", "Kodak", 400,
            "Classic B&W, rich tones, distinctive grain",
            contrast=18.0, brightness=2.0,
        ),
        _create_bw_profile(
            "Kodak T-Max 100", "Kodak", 100,
            "Fine grain, high sharpness, smooth tones",
            contrast=15.0, brightness=0.0,
        ),
        _create_bw_profile(
            "Kodak T-Max 400", "Kodak", 400,
            "Versatile B&W, finer grain than Tri-X",
            contrast=14.0, brightness=1.0,
        ),
        _create_bw_profile(
            "Ilford HP5 Plus 400", "Ilford", 400,
            "Classic British B&W, beautiful tonal range",
            contrast=16.0, brightness=1.0,
        ),
        _create_bw_profile(
            "Ilford FP4 Plus 125", "Ilford", 125,
            "Medium-speed B&W, excellent sharpness",
            contrast=15.0, brightness=0.0,
        ),
        _create_bw_profile(
            "Ilford Delta 100", "Ilford", 100,
            "Modern T-grain B&W, very fine grain",
            contrast=14.0, brightness=0.0,
        ),
        _create_bw_profile(
            "Ilford Delta 3200", "Ilford", 3200,
            "Ultra-fast B&W, prominent grain, moody",
            contrast=12.0, brightness=3.0,
        ),
        _create_bw_profile(
            "Fomapan 100", "Foma", 100,
            "Czech classic, retro look, extended tonal range",
            contrast=13.0, brightness=0.0,
        ),
        _create_bw_profile(
            "Fomapan 400", "Foma", 400,
            "Versatile B&W, slightly softer contrast",
            contrast=14.0, brightness=1.0,
        ),
    ]

    for profile in profiles:
        FILM_PROFILES[profile.name] = profile


# Initialize profiles on module load
_register_profiles()


def get_profile(name: str) -> Optional[FilmProfile]:
    """Get a film profile by name."""
    return FILM_PROFILES.get(name)


def get_profiles_by_category(category: str) -> List[FilmProfile]:
    """Get all profiles in a category."""
    return [p for p in FILM_PROFILES.values() if p.category == category]


def get_all_categories() -> List[str]:
    """Get list of all profile categories."""
    categories = list(set(p.category for p in FILM_PROFILES.values()))
    # Sort in logical order
    order = ["None", "Color Negative", "Color Slide", "B&W Negative"]
    categories.sort(key=lambda c: order.index(c) if c in order else 99)
    return categories


def get_all_profiles() -> List[FilmProfile]:
    """Get all film profiles sorted by category then name."""
    profiles = list(FILM_PROFILES.values())
    order = {"None": 0, "Color Negative": 1, "Color Slide": 2, "B&W Negative": 3}
    profiles.sort(key=lambda p: (order.get(p.category, 99), p.name))
    return profiles
