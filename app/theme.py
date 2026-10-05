"""Optional dashboard theme image (presentation only).

The dashboard is a light, soft analytics interface. A user may upload an image; a small restrained palette is
derived from it with Pillow (already a declared dependency) and written into the CSS variables that drive the whole
interface: accent, secondary accent, and faintly tinted light surfaces. A small, pale, faded strip of
the image decorates the page header. Readability always wins: text colours never change, accents are darkened until
they meet a minimum contrast on the cards, and grey, near-white, near-black or colourless images fall back to the
default palette.

The result is held in the browser session only: nothing is written to disk, nothing is sent anywhere, and
nothing here touches the analysis, the result tables or the anonymised download.
"""

import base64
import colorsys
import html
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, ImageStat, UnidentifiedImageError

ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
MAX_BYTES = 8 * 1024 * 1024            # larger files are refused before decoding
MAX_PIXELS = 36_000_000                # refuse extremely large images (decompression-bomb guard)
DEFAULT_ACCENT = "#1e5ae0"
DEFAULT_ACCENT2 = "#08766a"
DEFAULT_SURFACES = {"bg": "#edf1f7", "sidebar": "#e4eaf3", "surface": "#ffffff", "elev": "#f6f8fc",
                    "border": "#cdd6e4"}
TEXT, MUTED = "#172033", "#525d70"     # fixed text colours (a theme never changes them)
BANNER_MIN_BRIGHTNESS = 0.88          # the header strip is washed towards white until its mean brightness (0-1) reaches this
MIN_CONTRAST = 4.5                     # accents against the card surface and the page background
FRIENDLY_ERROR = "Theme image could not be applied."
FRIENDLY_HINT = "Upload a PNG, JPG, JPEG or WEBP image."


class ThemeError(Exception):
    """Any problem with a theme image. The message is always the short friendly text."""


@dataclass(frozen=True)
class Theme:
    accent: str          # primary accent (selected navigation, tabs, buttons, KPI edge)
    accent2: str         # secondary accent (small highlights)
    bg: str              # page background (light, faintly tinted)
    sidebar: str
    surface: str         # cards and chart panels
    elev: str            # inputs, upload box
    border: str
    banner: str          # data: URI of a small faded header image
    preview: bytes = b""  # small PNG thumbnail for the sidebar preview


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(int(round(c * 255)) for c in rgb)


def _hsl_to_hex(h, s, l):
    return _hex(colorsys.hls_to_rgb(h, l, s))


def _luminance(hex_colour):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(int(hex_colour[i:i + 2], 16)) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _accent(hue, sat, light, backgrounds):
    """Accent colour darkened until it reads clearly on every light background it is used on."""
    colour = _hsl_to_hex(hue, sat, light)
    while min(contrast(colour, bg) for bg in backgrounds) < MIN_CONTRAST and light > 0.12:
        light -= 0.02
        colour = _hsl_to_hex(hue, sat, light)
    return colour


def _open(data):
    """Decode and validate. Raises ThemeError for anything that is not a modest PNG/JPEG/WEBP image."""
    if not data or len(data) > MAX_BYTES:
        raise ThemeError(FRIENDLY_ERROR)
    try:
        Image.MAX_IMAGE_PIXELS = MAX_PIXELS
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in ALLOWED_FORMATS or probe.width * probe.height > MAX_PIXELS:
                raise ThemeError(FRIENDLY_ERROR)
            img = ImageOps.exif_transpose(probe)
            img.load()
            return img.convert("RGB")
    except ThemeError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, SyntaxError):
        raise ThemeError(FRIENDLY_ERROR) from None


def extract_palette(img):
    """Dict of light-UI colours from the image: hue histogram weighted by saturation, deterministic.

    Pixels that are near-grey, near-white or near-black are ignored. If almost no colour is left (a dark, light or
    greyscale image) the default palette is returned, so the dashboard never loses readability."""
    small = img.copy()
    small.thumbnail((48, 48))
    bins = [0.0] * 12
    hue_sum = [0.0] * 12
    raw = small.tobytes()
    for r, g, b in zip(raw[0::3], raw[1::3], raw[2::3]):
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        weight = s * (1 - abs(2 * l - 1))
        if s < 0.2 or weight <= 0:
            continue
        k = min(int(h * 12), 11)
        bins[k] += weight
        hue_sum[k] += h * weight
    if sum(bins) < 1.0:
        return {"accent": DEFAULT_ACCENT, "accent2": DEFAULT_ACCENT2, **DEFAULT_SURFACES}
    first = max(range(12), key=lambda k: bins[k])
    hue1 = hue_sum[first] / bins[first]
    others = [k for k in range(12) if min(abs(k - first), 12 - abs(k - first)) >= 2 and bins[k] > 0]
    second = max(others, key=lambda k: bins[k]) if others else None
    hue2 = hue_sum[second] / bins[second] if second is not None and bins[second] > 0.15 * bins[first] \
        else (hue1 + 0.12) % 1.0
    bg = _hsl_to_hex(hue1, 0.20, 0.935)             # only a faint tint: the page stays a light blue-grey
    surface = "#ffffff"
    sidebar = _hsl_to_hex(hue1, 0.22, 0.905)
    return {
        "accent": _accent(hue1, 0.72, 0.48, (surface, bg, sidebar)),
        "accent2": _accent(hue2, 0.62, 0.40, (surface, bg, sidebar)),
        "bg": bg, "sidebar": sidebar, "surface": surface,
        "elev": DEFAULT_SURFACES["elev"], "border": DEFAULT_SURFACES["border"],
    }


def make_banner(img):
    """Small JPEG data URI (cropped to a wide strip) used only as a faded header background. The strip is washed
    towards white so that dark text stays readable on top of it whatever the image (very dark, very light or
    saturated): its mean brightness is at least BANNER_MIN_BRIGHTNESS."""
    strip = ImageOps.fit(img, (720, 150), method=Image.LANCZOS)
    white = Image.new("RGB", strip.size, (255, 255, 255))
    strip = Image.blend(strip, white, 0.55)
    mean = sum(ImageStat.Stat(strip.convert("L")).mean) / 255
    if mean < BANNER_MIN_BRIGHTNESS:
        strip = Image.blend(strip, white, min(1.0, (BANNER_MIN_BRIGHTNESS - mean) / (1 - mean) + 0.01))
    buf = io.BytesIO()
    strip.save(buf, format="JPEG", quality=70, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def make_preview(img):
    thumb = img.copy()
    thumb.thumbnail((240, 160))
    buf = io.BytesIO()
    thumb.save(buf, format="PNG")
    return buf.getvalue()


def build_theme(data):
    """Bytes of an uploaded image -> Theme. Raises ThemeError (friendly text only) on any problem."""
    img = _open(data)
    try:
        return Theme(**extract_palette(img), banner=make_banner(img), preview=make_preview(img))
    except ThemeError:
        raise
    except Exception:                                      # never let a theme problem escape as a stack trace
        raise ThemeError(FRIENDLY_ERROR) from None


def _rgb(hex_colour):
    return ", ".join(str(int(hex_colour[i:i + 2], 16)) for i in (1, 3, 5))


def theme_css(theme):
    """CSS variable overrides plus the faded header strip. Text colours and chart category colours are never touched."""
    if theme is None:
        return ""
    v = {k: html.escape(getattr(theme, k)) for k in ("accent", "accent2", "bg", "sidebar", "surface", "elev", "border")}
    return f"""
<style>
  .stApp {{ --wa-bg: {v['bg']}; --wa-sidebar: {v['sidebar']}; --wa-surface: {v['surface']};
          --wa-elev: {v['elev']}; --wa-border: {v['border']}; --wa-accent: {v['accent']};
          --wa-accent2: {v['accent2']}; --wa-accent-soft: rgba({_rgb(theme.accent)}, 0.11); }}
  .stApp .st-key-banner {{ background-image: linear-gradient(90deg, {v['surface']} 0%, {v['surface']} 42%,
                    rgba(255,255,255,0) 100%), url("{theme.banner}"); background-size: cover;
                    background-position: right center; border-radius: 14px; padding: 0.9rem 1.2rem 0.1rem 1.2rem !important;
                    margin-bottom: 0.6rem; border: 1px solid {v['border']}; }}
</style>
"""
