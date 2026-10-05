"""Headless smoke tests of the Streamlit app (streamlit.testing.v1.AppTest).
Skipped automatically when Streamlit is not installed."""

import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import demo_data  # noqa: E402
from app_config import AppConfig  # noqa: E402
from run_manager import RunManager  # noqa: E402
from test_dashboard_core import FORBIDDEN, SENSITIVE_CHAT, chat  # noqa: E402

APP = str(ROOT / "app" / "streamlit_app.py")
PAGES = ("Overview", "Conversation", "NLP Insights", "Patterns")


def new_app(manager=None):
    at = AppTest.from_file(APP, default_timeout=120)
    if manager is not None:
        at.session_state["run_manager"] = manager
    return at


def rendered_text(at):
    """All text the page renders: markdown, captions, headings, alerts, tables, widget labels."""
    parts = []
    for group in (at.markdown, at.caption, at.title, at.header, at.subheader, at.warning, at.error,
                  at.info, at.success, at.text, at.code):
        parts += [str(e.value) for e in group]
    for df in at.dataframe:
        parts.append(df.value.astype(str).to_csv(index=False))
    for w in list(at.metric):
        parts += [str(w.label), str(w.value)]
    for w in list(at.button) + list(at.radio) + list(at.toggle) + list(at.slider) + list(at.tabs):
        parts.append(str(w.label))
    return "\n".join(parts)


def loaded_manager(data=None, name="a.txt"):
    m = RunManager(AppConfig())
    assert m.submit(data or demo_data.build_demo_chat().encode(), name) == "replaced"
    return m


def test_empty_state_before_any_upload():
    at = new_app().run()
    assert not at.exception
    text = rendered_text(at)
    assert "No chat loaded yet" in text and "Expected file format" in text and "Privacy" in text
    assert [r.value for r in at.sidebar.radio][0] == "Overview"


def test_demo_button_runs_pipeline_end_to_end_and_pages_render():
    at = new_app().run()
    demo = [b for b in at.sidebar.button if "demo" in b.label.lower()]
    assert demo, "demo button missing"
    demo[0].click().run()
    assert not at.exception
    manager = at.session_state["run_manager"]
    assert manager.current is not None and manager.current.filename == demo_data.DEMO_FILENAME
    for page in PAGES:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, page
    assert "Participants (descriptive counts only)" not in rendered_text(at)   # Patterns page: not a page here
    at.sidebar.radio[0].set_value("Conversation").run()
    assert "Participants (descriptive counts only)" in rendered_text(at)       # a section, not a page


def test_exactly_four_pages_and_no_participants_page():
    at = new_app(loaded_manager()).run()
    assert list(at.sidebar.radio[0].options) == list(PAGES)


def test_overview_shows_run_status_dates_and_assumptions():
    at = new_app(loaded_manager()).run()
    text = rendered_text(at)
    assert "a.txt" in text                                     # current-run file name
    assert "2025-03-10" in text and "Month/Day/Year" in text and "unverified" in text
    assert "Parsed rows" in text and "Unique text messages" in text


def test_pages_hide_sensitive_values():
    at = new_app(loaded_manager(SENSITIVE_CHAT, "sensitive.txt")).run()
    for page in PAGES:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, page
        text = rendered_text(at).lower()
        for value in FORBIDDEN:
            assert value.lower() not in text, (page, value)


def test_nlp_toggle_reveals_single_message_terms_only_when_asked():
    at = new_app(loaded_manager(SENSITIVE_CHAT, "sensitive.txt")).run()
    at.sidebar.radio[0].set_value("NLP Insights").run()
    assert not at.exception
    toggle = [t for t in at.toggle if "only one message" in t.label][0]
    assert toggle.value is False
    assert "zephyrine" not in rendered_text(at).lower()
    # revealing single-message terms is an explicit user choice (the hidden terms are display-only)
    toggle.set_value(True).run()
    assert not at.exception


def test_failed_second_upload_keeps_previous_run_visible_in_ui():
    m = loaded_manager()
    assert m.submit(b"not a chat at all\n", "b.txt") == "failed"
    at = new_app(m).run()
    assert not at.exception
    assert any("does not look like a supported" in e.value for e in at.error)
    assert any("previous successful run" in e.value and "a.txt" in e.value for e in at.info)
    assert "Parsed rows" in rendered_text(at)                   # previous run still rendered


def test_zero_text_run_renders_all_pages_without_error():
    data = chat(("3/10/25, 9:00:00 AM", "Ann", "<image omitted>"), ("3/11/25, 9:00:00 AM", "Ann", "<video omitted>"))
    at = new_app(loaded_manager(data, "media_only.txt")).run()
    assert any("No text messages" in w.value for w in at.warning)
    for page in PAGES:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, page


def test_clear_button_removes_the_run():
    at = new_app(loaded_manager()).run()
    [b for b in at.sidebar.button if "clear" in b.label.lower()][0].click().run()
    assert at.session_state["run_manager"].current is None
    assert "No chat loaded yet" in rendered_text(at)


# ------------------------------------------------ real upload flow through the UI ---
def upload(at, name, data):
    at.sidebar.file_uploader[0].upload(name, data, "text/plain").run()
    assert not at.exception
    return at


def test_upload_invalid_file_shows_clear_error_and_no_run():
    at = upload(new_app().run(), "notes.txt", b"just some notes\nnothing here\n")
    assert any("does not look like a supported" in e.value for e in at.error)
    assert at.session_state["run_manager"].current is None
    assert "No chat loaded yet" in rendered_text(at)


def test_upload_empty_file_shows_clear_error():
    at = upload(new_app().run(), "empty.txt", b"")
    assert any("empty" in e.value.lower() for e in at.error)


def test_upload_success_then_second_success_replaces_first():
    at = upload(new_app().run(), "first.txt", demo_data.build_demo_chat().encode())
    assert at.session_state["run_manager"].current.filename == "first.txt"
    second = chat(("3/10/25, 9:00:00 AM", "Zoe", "hello there team"), ("3/12/25, 9:00:00 AM", "Yan", "see you soon team"))
    upload(at, "second.txt", second)
    manager = at.session_state["run_manager"]
    assert manager.current.filename == "second.txt" and manager.last_error is None
    assert "second.txt" in rendered_text(at) and "first.txt" not in rendered_text(at)


def test_upload_success_then_failed_second_keeps_first_visible():
    at = upload(new_app().run(), "first.txt", demo_data.build_demo_chat().encode())
    upload(at, "broken.txt", b"this is not a chat\n")
    manager = at.session_state["run_manager"]
    assert manager.current.filename == "first.txt" and manager.last_error is not None
    assert any("previous successful run" in i.value and "first.txt" in i.value for i in at.info)
    assert "first.txt" in rendered_text(at)


def test_upload_cleans_up_temporary_directory(monkeypatch):
    import run_pipeline as rp
    made = []
    original = rp.make_run_dir

    def recording():
        d = original()
        made.append(d)
        return d

    monkeypatch.setattr(rp, "make_run_dir", recording)
    at = upload(new_app().run(), "first.txt", demo_data.build_demo_chat().encode())
    upload(at, "broken.txt", b"this is not a chat\nat all\n")
    assert len(made) == 2 and not any(d.exists() for d in made)


def test_upload_sensitive_chat_never_renders_sensitive_values():
    at = upload(new_app().run(), "sensitive.txt", SENSITIVE_CHAT)
    for page in PAGES:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, page
        text = rendered_text(at).lower()
        for value in FORBIDDEN:
            assert value.lower() not in text, (page, value)


# ------------------------------------------------------------- final polish: layout and integration ---
def test_overview_has_kpi_cards_charts_and_key_findings():
    at = new_app(loaded_manager()).run()
    text = rendered_text(at)
    for label in ("Total Messages", "Text Messages", "Media / Deleted", "Active Days", "Message Composition",
                  "Daily Activity", "Key Findings", "About This Analysis"):
        assert label in text, label
    assert "Script Mix:" in text                                       # finding built from the Script Mix table
    assert "sentiment" in text.lower() and "No sentiment, emotion" in text   # scope statement: not implemented


def test_nlp_insights_has_six_tabs_with_script_mix_and_key_terms():
    at = new_app(loaded_manager()).run()
    at.sidebar.radio[0].set_value("NLP Insights").run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Unigrams", "Bigrams", "Trigrams", "TF-IDF", "Script Mix", "Key Terms"]
    text = rendered_text(at)
    assert "describes the writing systems" in text and "does not identify languages" in text
    assert "Key-term coverage measures how many distinct messages contain a term" in text
    assert "language detection" not in text.lower().replace("no language detection is performed", "")


def test_patterns_uses_template_labels_not_raw_text():
    at = new_app(loaded_manager()).run()
    at.sidebar.radio[0].set_value("Patterns").run()
    assert not at.exception
    text = rendered_text(at)
    assert "Template T1" in text and "Repetition Summary" in text and "Interpretation" in text
    assert "example.com" not in text                                   # demo links are never displayed


def test_conversation_page_order_and_secondary_statistics():
    at = new_app(loaded_manager()).run()
    at.sidebar.radio[0].set_value("Conversation").run()
    assert not at.exception
    heads = [s.value for s in at.subheader]
    wanted = ["Conversation Activity", "Message Composition", "Repetition Analysis", "Secondary Statistics"]
    assert [h for h in heads if h in wanted] == wanted                # activity first, secondary statistics last
    assert [t.label for t in at.tabs] == ["Hour of day", "Weekday", "Text length"]


def test_error_guidance_is_shown_for_invalid_uploads_without_technical_details():
    at = upload(new_app().run(), "notes.txt", b"just some notes\nnothing here\n")
    captions = " ".join(c.value for c in at.caption)
    assert "What to do:" in captions and "bracketed" in captions
    shown = rendered_text(at)
    assert "Traceback" not in shown and "Error:" not in shown


def test_every_pipeline_stage_has_a_friendly_label():
    import run_pipeline as rp
    sys.path.insert(0, str(ROOT / "app"))
    import ui
    assert set(rp.STAGES) == set(ui.STAGE_LABELS)
    for code in ("wrong_type", "empty", "unsupported_format", "analysis_failed", "dates_invalid"):
        assert ui.error_help(code)


# ------------------------------------------- generalisation: every kind of chat, every page ---
FIXTURE_CHATS = ["one_to_one.txt", "group_12.txt", "group_30.txt", "single_sender.txt", "zero_text.txt",
                 "parser_system_events.txt", "media_deleted.txt", "privacy_cases.txt"]
FICTIONAL_PEOPLE = ["Alex Demo", "Sam Sample", "Riya Testwala", "Kabir Fictional", "Member 07 Fictional", "Solo Fictional",
                    "Omkar Testkar"]


@pytest.mark.parametrize("name", FIXTURE_CHATS)
def test_all_pages_render_for_every_kind_of_chat_without_names_or_links(name):
    from helpers import fixture_bytes
    at = new_app(loaded_manager(fixture_bytes(name), name)).run()
    assert not at.exception, name
    for page in PAGES:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, (name, page)
        text = re.sub(r"<style>.*?</style>", "", rendered_text(at), flags=re.S)     # CSS holds the SVG namespace URL
        for person in FICTIONAL_PEOPLE:
            assert person.lower() not in text.lower(), (name, page, person)
        for token in ("http", "chat.whatsapp", "@", "9000012345"):
            assert token not in text.lower(), (name, page, token)


def test_patterns_page_uses_repeated_templates_wording_and_neutral_script_wording():
    from helpers import fixture_bytes
    at = new_app(loaded_manager(fixture_bytes("group_12.txt"), "g.txt")).run()
    at.sidebar.radio[0].set_value("Patterns").run()
    text = rendered_text(at)
    assert "Repeated Templates" in text and "Template Groups" not in text
    at.sidebar.radio[0].set_value("Overview").run()
    overview = rendered_text(at)
    assert "more than one writing system" in overview and "mix Latin and Devanagari" not in overview
    assert "Hindi" not in overview and "Marathi" not in overview.replace("Marathi or Hindi", "")


def test_zero_text_chat_shows_explanation_on_every_page():
    from helpers import fixture_bytes
    at = new_app(loaded_manager(fixture_bytes("zero_text.txt"), "z.txt")).run()
    for page in ("Overview", "Conversation", "NLP Insights"):
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception and any("no text messages" in i.value.lower() for i in at.info), page
    at.sidebar.radio[0].set_value("Patterns").run()
    assert any("No text messages" in w.value for w in at.warning)
