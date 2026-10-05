"""Tests of the optional dashboard theme image (presentation only)."""

import io
import sys
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import theme  # noqa: E402
from results_bundle import build_bundle  # noqa: E402
from test_dashboard_app import loaded_manager, new_app, rendered_text  # noqa: E402


def image_bytes(colour, fmt="PNG", size=(120, 60)):
    buf = io.BytesIO()
    Image.new("RGB", size, colour).save(buf, format=fmt)
    return buf.getvalue()


def theme_buttons(at):
    return {b.label: b for b in at.sidebar.button if b.label in ("Apply Theme", "Reset Theme")}


def apply_theme(at, data, name="theme.png", mime="image/png"):
    at.sidebar.file_uploader[1].upload(name, data, mime).run()
    assert not at.exception
    theme_buttons(at)["Apply Theme"].click().run()
    assert not at.exception
    return at


def all_css(at):
    return "\n".join(str(m.value) for m in list(at.markdown) + list(at.sidebar.markdown))


# 1. no theme image -> default theme
def test_no_theme_image_keeps_default_theme():
    at = new_app().run()
    assert not at.exception
    assert "theme" not in at.session_state
    assert "background-image" not in all_css(at)                  # no banner / tint overrides
    assert theme.theme_css(None) == ""
    assert theme_buttons(at)["Apply Theme"].disabled and theme_buttons(at)["Reset Theme"].disabled


# 2. valid theme image -> accepted, restrained palette
@pytest.mark.parametrize("fmt,colour", [("PNG", (30, 140, 70)), ("JPEG", (110, 60, 170)), ("WEBP", (40, 90, 200))])
def test_valid_image_is_accepted_and_palette_is_restrained(fmt, colour):
    built = theme.build_theme(image_bytes(colour, fmt))
    for value in (built.accent, built.accent2, built.bg, built.surface, built.border):
        assert len(value) == 7 and value.startswith("#")
    assert min(int(built.bg[i:i + 2], 16) for i in (1, 3, 5)) > 225   # the interface stays light
    assert theme.contrast(built.accent, built.surface) >= theme.MIN_CONTRAST     # accents readable on cards
    assert theme.contrast(theme.TEXT, built.surface) > 10                        # dark text stays readable
    assert built.banner.startswith("data:image/jpeg;base64,") and built.preview


def _channels(hex_colour):
    return [int(hex_colour[i:i + 2], 16) for i in (1, 3, 5)]


def test_blue_green_and_purple_images_give_matching_accents():
    r, g, b = _channels(theme.build_theme(image_bytes((20, 150, 60))).accent)
    assert g > r and g > b                                          # green
    r, g, b = _channels(theme.build_theme(image_bytes((40, 90, 210))).accent)
    assert b > r and b > g                                          # blue
    r, g, b = _channels(theme.build_theme(image_bytes((120, 50, 180))).accent)
    assert b > g and r > g                                          # purple


def test_dark_or_grey_image_falls_back_to_default_light_palette():
    for colour in ((10, 10, 10), (128, 128, 128)):                  # dark / grey: no automatic dark mode
        assert theme.build_theme(image_bytes(colour)).accent == theme.DEFAULT_ACCENT


def test_applying_valid_theme_changes_accent_css_but_not_chart_colours():
    at = apply_theme(new_app(loaded_manager()).run(), image_bytes((20, 150, 60)))
    built = at.session_state["theme"]
    css = all_css(at)
    assert built.accent in css and "background-image" in css
    import charts
    kinds = [charts.KIND_COLOURS[k] for k in ("text", "media", "deleted", "system")]
    assert len(set(kinds)) == 4                                     # categories stay distinguishable
    assert all(theme.contrast(c, charts.SURFACE) >= 3 for c in kinds)    # and visible on the white panel


# 3. invalid images -> friendly message, no stack trace
@pytest.mark.parametrize("data,name", [
    (b"not an image at all", "theme.png"),
    (image_bytes((1, 2, 3))[:40], "broken.png"),                     # corrupted
    (b"GIF89a" + b"\x00" * 30, "x.gif"),                            # unsupported format
    (b"", "empty.png"),
])
def test_invalid_theme_image_gives_friendly_error(data, name):
    at = new_app().run()
    at.sidebar.file_uploader[1].upload(name, data, "image/png").run()
    assert not at.exception
    text = rendered_text(at) + " ".join(w.value for w in at.sidebar.warning) + " ".join(c.value for c in at.sidebar.caption)
    assert "Theme image could not be applied." in text
    assert "Upload a PNG, JPG, JPEG or WEBP image." in text
    assert "Traceback" not in text
    assert theme_buttons(at)["Apply Theme"].disabled
    assert "theme" not in at.session_state


def test_oversized_image_is_refused(monkeypatch):
    monkeypatch.setattr(theme, "MAX_PIXELS", 1000)
    with pytest.raises(theme.ThemeError):
        theme.build_theme(image_bytes((0, 0, 255), size=(100, 100)))


# 4. reset -> default theme
def test_reset_returns_to_default_theme():
    at = apply_theme(new_app().run(), image_bytes((20, 150, 60)))
    assert "theme" in at.session_state
    theme_buttons(at)["Reset Theme"].click().run()
    assert not at.exception
    assert "theme" not in at.session_state
    assert "background-image" not in all_css(at)


# 5. the theme does not change analysis results; 6. it is not in the download; 7. a failure cannot break analysis
def test_theme_does_not_modify_analysis_results_or_download_bundle():
    manager = loaded_manager()
    before = {k: v.copy() for k, v in manager.current.tables.items()}
    bundle_before = build_bundle(manager.current, manager.config.min_term_messages, False)
    at = apply_theme(new_app(manager).run(), image_bytes((110, 60, 170), "JPEG"), "t.jpg", "image/jpeg")
    run = at.session_state["run_manager"].current
    assert run is manager.current
    for name, frame in before.items():
        assert frame.equals(run.tables[name]), name
    bundle_after = build_bundle(run, manager.config.min_term_messages, False)
    za, zb = zipfile.ZipFile(io.BytesIO(bundle_after)), zipfile.ZipFile(io.BytesIO(bundle_before))
    assert za.namelist() == zb.namelist()                          # same files with identical contents
    assert all(za.read(n) == zb.read(n) for n in za.namelist())
    names = za.namelist()
    assert not any(n.lower().endswith((".png", ".jpg", ".jpeg", ".webp")) for n in names)
    assert not any("theme" in n.lower() for n in names)
    assert theme.build_theme(image_bytes((1, 2, 3))).banner.encode()[:30] not in bundle_after


def test_theme_failure_does_not_break_chat_analysis():
    at = new_app().run()
    at.sidebar.file_uploader[1].upload("bad.png", b"garbage", "image/png").run()
    assert not at.exception
    import demo_data
    at.sidebar.file_uploader[0].upload("a.txt", demo_data.build_demo_chat().encode(), "text/plain").run()
    assert not at.exception
    assert at.session_state["run_manager"].current is not None
    assert "Total Messages" in rendered_text(at)


def test_theme_survives_a_new_chat_upload():
    import demo_data
    at = apply_theme(new_app(loaded_manager()).run(), image_bytes((20, 150, 60)))
    chosen = at.session_state["theme"]
    at.sidebar.file_uploader[0].upload("b.txt", demo_data.build_synthetic_chat(40).encode(), "text/plain").run()
    assert not at.exception
    assert at.session_state["theme"] is chosen


# ------------------------------------------- readability for any kind of theme image ---
@pytest.mark.parametrize("colour", [
    (40, 90, 210), (20, 150, 60), (120, 50, 180),               # blue, green, purple
    (5, 5, 5), (250, 250, 250), (128, 128, 128),                # very dark, very light, grey
    (255, 235, 59), (200, 30, 30), (255, 200, 220), (10, 10, 60),
])
def test_every_theme_image_gives_a_readable_light_palette(colour):
    built = theme.build_theme(image_bytes(colour))
    for accent in (built.accent, built.accent2):                      # accents are readable on cards AND on the page
        assert theme.contrast(accent, built.surface) >= theme.MIN_CONTRAST
        assert theme.contrast(accent, built.bg) >= theme.MIN_CONTRAST
    for surface in (built.bg, built.sidebar, built.surface, built.elev):
        assert theme.contrast(theme.TEXT, surface) >= 12              # primary text
        assert theme.contrast(theme.MUTED, surface) >= 4.5            # secondary text
        assert min(int(surface[i:i + 2], 16) for i in (1, 3, 5)) > 215   # always a light interface (the sidebar is a little darker than the page)
    assert theme.contrast("#ffffff", built.accent) >= theme.MIN_CONTRAST  # white text on the primary button


def test_grayscale_and_near_white_images_fall_back_to_the_default_palette():
    for colour in ((0, 0, 0), (255, 255, 255), (90, 90, 90)):
        b = theme.build_theme(image_bytes(colour))
        assert b.accent == theme.DEFAULT_ACCENT and b.bg == theme.DEFAULT_SURFACES["bg"]


@pytest.mark.parametrize("colour", [(250, 250, 250), (5, 5, 5), (37, 99, 235), (255, 200, 0), (128, 128, 128)])
def test_header_strip_is_always_pale_so_text_on_it_stays_readable(colour):
    import base64
    from PIL import ImageStat
    built = theme.build_theme(image_bytes(colour))
    strip = Image.open(io.BytesIO(base64.b64decode(built.banner.split(",", 1)[1]))).convert("L")
    assert sum(ImageStat.Stat(strip).mean) / 255 >= theme.BANNER_MIN_BRIGHTNESS - 0.03
