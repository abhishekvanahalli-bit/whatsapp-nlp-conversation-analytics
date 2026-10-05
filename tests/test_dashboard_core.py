"""Tests for the dashboard's non-UI core: validation, temporary-run adapter, run
management, display privacy filter, pseudonyms, and the zero-text hardening."""

import io
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import conversation_analytics as ca  # noqa: E402
import demo_data  # noqa: E402
import display_privacy as dp  # noqa: E402
import ngram_analysis as ng  # noqa: E402
import preprocessor as pp  # noqa: E402
import results_bundle  # noqa: E402
import run_pipeline as rp  # noqa: E402
from app_config import AppConfig  # noqa: E402
from helpers import SAMPLE_CSV, SAMPLE_DIR  # noqa: E402
from run_manager import RunManager  # noqa: E402

HEADER = demo_data.HEADER
CFG = AppConfig()


def chat(*rows):
    """Build export text from (stamp, sender_or_None, text) rows; stamp like '3/10/25, 9:00:00 AM'."""
    lines = [HEADER]
    for stamp, sender, text in rows:
        lines.append(f"[{stamp}] " + (text if sender is None else f"{sender}: {text}"))
    return ("\n".join(lines) + "\n").encode("utf-8")


def run(data, name="chat.txt", config=CFG, **kw):
    return rp.run_pipeline(data, name, config, **kw)


def fail_code(data, name="chat.txt", config=CFG):
    with pytest.raises(rp.UserFacingError) as e:
        run(data, name, config)
    return e.value.code


# ----------------------------------------------------- invalid / empty input ---
def test_wrong_extension_rejected():
    assert fail_code(demo_data.build_demo_chat().encode(), "chat.csv") == "wrong_type"
    assert fail_code(demo_data.build_demo_chat().encode(), "chat") == "wrong_type"


def test_empty_and_whitespace_input_rejected():
    assert fail_code(b"") == "empty"
    assert fail_code(b"   \n\n\t \n") == "empty"


def test_non_utf8_rejected():
    assert fail_code(b"\xff\xfe\x00\x81 not utf8 \x80\x81") == "not_utf8"


def test_not_a_chat_is_unsupported_format():
    assert fail_code(b"just some notes\nsecond line\n") == "unsupported_format"


def test_other_export_style_is_unsupported_not_claimed():
    android = b"9/13/26, 2:12 PM - Ann: hello there\n9/13/26, 2:13 PM - Bob: hi\n"
    assert fail_code(android) == "unsupported_format"


def test_day_month_dates_are_rejected_instead_of_misread():
    ddmm = chat(("25/09/26, 2:11:31 PM", "Ann", "hello there"), ("26/09/26, 2:12:31 PM", "Bob", "hi all"))
    assert fail_code(ddmm) == "date_order_unsupported"
    mixed = chat(("5/3/26, 2:11:31 PM", "Ann", "hello there"), ("26/3/26, 2:12:31 PM", "Bob", "hi all"))
    assert fail_code(mixed) == "date_order_unsupported"          # some values <= 12 would be silently misread
    impossible = chat(("13/14/26, 2:11:31 PM", "Ann", "hello there"))
    assert fail_code(impossible) == "date_order_inconsistent"


def test_error_messages_never_contain_file_content():
    secret = "topsecretmarker"
    for data, name in ((f"{secret}\nmore\n".encode(), "x.txt"), (secret.encode(), "x.pdf")):
        with pytest.raises(rp.UserFacingError) as e:
            run(data, name)
        assert secret not in e.value.message


def test_configurable_size_and_count_limits():
    data = demo_data.build_demo_chat().encode()
    assert fail_code(data, config=AppConfig(max_upload_mb=0.0001)) == "too_large"
    assert fail_code(data, config=AppConfig(max_parsed_rows=10)) == "too_many_rows"
    assert fail_code(data, config=AppConfig(max_text_messages=5)) == "too_many_messages"


def test_config_from_env_overrides_and_ignores_bad_values():
    cfg = AppConfig.from_env({"WA_MAX_UPLOAD_MB": "3", "WA_MAX_TEXT_MESSAGES": "50", "WA_TOP_K_DEFAULT": "abc"})
    assert cfg.max_upload_mb == 3.0 and cfg.max_text_messages == 50
    assert cfg.top_k_default == AppConfig().top_k_default


# ----------------------------------------------------------- small / zero text ---
def test_small_chat_is_not_rejected_but_warns():
    r = run(chat(("3/10/25, 9:00:00 AM", "Ann", "hello there team")))
    assert r.info["n_text_messages"] == 1
    assert any("not meaningful" in w for w in r.warnings)


def test_media_only_chat_runs_with_limited_result_and_warning():
    r = run(chat(("3/10/25, 9:00:00 AM", "Ann", "<image omitted>"), ("3/10/25, 9:01:00 AM", "Ann", "<video omitted>")))
    assert r.info["n_text_messages"] == 0
    assert r.analytics_meta["limited_result"] is True
    assert "no_text_messages" in r.analytics_meta["limitation_reasons"]
    assert any("No text messages" in w for w in r.warnings)
    comp = r.tables["analytics_row_composition"].set_index(["group", "category"])["count"]
    assert comp[("user_rows", "media")] == 2 and comp[("user_rows", "text")] == 0
    assert r.tables["ngram_unigrams"].empty and r.tables["tfidf_top_terms"].empty
    assert r.analytics_meta["all_reconciliation_checks_passed"]


def test_system_only_chat_does_not_crash():
    r = run(chat(("3/10/25, 9:00:00 AM", None, "- Ann added Bob")))
    assert r.info["n_text_messages"] == 0 and r.analytics_meta["limited_result"]
    assert r.tables["analytics_sender_counts"].empty


def test_zero_text_analytics_module_directly(tmp_path):
    """The hardening lives in the analytics module itself, not only in the app."""
    df, _ = pp.build_dataset(_write(tmp_path, chat(("3/10/25, 9:00:00 AM", "Ann", "<image omitted>"))))
    pp.save_processed_csv(df, tmp_path / "processed_chat.csv")
    tables, meta = ca.run_analytics(tmp_path / "processed_chat.csv", tmp_path, tmp_path)
    assert meta["limited_result"] and meta["all_reconciliation_checks_passed"]
    rep = tables["repetition_summary"].set_index("metric")["count"]
    assert rep["text_messages"] == 0 and rep["largest_template_group_size"] == 0
    assert (tables["length"]["n"] == 0).all()


def test_no_valid_timestamps_analytics_does_not_crash(tmp_path):
    df, _ = pp.build_dataset(_write(tmp_path, chat(("25/09/26, 2:11:31 PM", "Ann", "hello there"))))
    pp.save_processed_csv(df, tmp_path / "processed_chat.csv")
    _, meta = ca.run_analytics(tmp_path / "processed_chat.csv", tmp_path, tmp_path)
    assert "no_valid_timestamps" in meta["limitation_reasons"]
    assert meta["first_timestamp_as_exported"] is None


def test_hardening_leaves_existing_outputs_byte_identical(tmp_path):
    ca.run_analytics(SAMPLE_CSV, tmp_path, SAMPLE_DIR)
    for name in ca.OUTPUT_FILES:
        existing = SAMPLE_DIR / name
        if existing.exists():
            assert (tmp_path / name).read_bytes() == existing.read_bytes(), name


def _write(tmp_path, data):
    p = tmp_path / "upload.txt"
    p.write_bytes(data)
    return p


# ------------------------------------------------------ warnings and date info ---
def test_date_info_and_assumption_are_reported():
    r = run(demo_data.build_demo_chat().encode())
    assert r.info["first_timestamp"] == "2025-03-10 09:00:00"
    assert r.info["last_timestamp"] == "2025-03-21 15:15:00"
    assert "Month/Day/Year" in r.info["date_format_note"] and "unverified" in r.info["date_format_note"]
    assert "above 12" in r.info["date_order_evidence"]


def test_ambiguous_date_order_is_flagged():
    r = run(chat(("05/09/26, 2:11:31 PM", "Ann", "hello there"), ("06/09/26, 2:12:31 PM", "Bob", "hi all")))
    assert "cannot be confirmed" in r.info["date_order_evidence"]
    assert any("cannot be confirmed" in w for w in r.warnings)


def test_unrecognised_placeholders_not_treated_as_media():
    r = run(chat(("3/10/25, 9:00:00 AM", "Ann", "<poll omitted>"), ("3/10/25, 9:01:00 AM", "Ann", "<image omitted>"),
                 ("3/10/25, 9:02:00 AM", "Ann", "hello there")))
    comp = r.tables["analytics_row_composition"].set_index(["group", "category"])["count"]
    assert comp[("user_rows", "media")] == 1                      # only the known <image omitted> placeholder
    assert comp[("user_rows", "text")] == 2                       # the unknown placeholder type is counted as text
    assert r.info["unrecognised_placeholders"] == 1
    assert any("do not recognise" in w or "does not recognise" in w for w in r.warnings)


# --------------------------------------------------------- temporary directories ---
def test_run_dir_removed_after_success_and_after_failure():
    made = []

    def factory():
        d = rp.make_run_dir()
        made.append(d)
        return d

    run(demo_data.build_demo_chat().encode(), run_dir_factory=factory)
    assert len(made) == 1 and not made[0].exists()

    with pytest.raises(rp.UserFacingError):                        # fails after the directory is created
        run(b"not a chat\nat all\n", run_dir_factory=factory)
    assert len(made) == 2 and not made[1].exists()


def test_run_dir_removed_when_an_analysis_step_crashes(monkeypatch):
    made = []

    def factory():
        d = rp.make_run_dir()
        made.append(d)
        return d

    monkeypatch.setattr(rp.tf, "run_tfidf", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom secret")))
    with pytest.raises(rp.UserFacingError) as e:
        run(demo_data.build_demo_chat().encode(), run_dir_factory=factory)
    assert e.value.code == "analysis_failed" and "boom secret" not in e.value.message
    assert not made[0].exists()


def test_run_dir_is_outside_project_results_folder():
    d = rp.make_run_dir()
    try:
        assert rp.PROJECT_RESULTS_DIR not in d.parents and d != rp.PROJECT_RESULTS_DIR
    finally:
        rp.remove_run_dir(d)


def test_pipeline_does_not_touch_project_results_folder():
    def snapshot():       # every file under results/ (results/sample holds the committed fictional example)
        return {p.relative_to(ng.RESULTS_DIR).as_posix(): p.read_bytes()
                for p in ng.RESULTS_DIR.rglob("*") if p.is_file()} if ng.RESULTS_DIR.exists() else {}
    before = snapshot()
    run(demo_data.build_demo_chat().encode())
    after = snapshot()
    assert before == after


def test_only_approved_tables_are_loaded():
    r = run(demo_data.build_demo_chat().encode())
    assert "analysis_corpus" not in r.tables and "tfidf_terms_by_message" not in r.tables
    assert "processed_chat" not in r.tables
    for frame in r.tables.values():
        assert not (rp.FORBIDDEN_COLUMNS & set(frame.columns))
    assert "top10_terms_by_total_tfidf" not in json.dumps(r.tfidf_meta)


# ------------------------------------------------------------- run management ---
def test_successful_new_upload_replaces_previous_run():
    m = RunManager(CFG)
    assert m.submit(demo_data.build_demo_chat().encode(), "a.txt") == "replaced"
    first = m.current
    other = chat(("3/10/25, 9:00:00 AM", "Zoe", "hello there team"), ("3/11/25, 9:00:00 AM", "Yan", "hello again team"))
    assert m.submit(other, "b.txt") == "replaced"
    assert m.current is not first and m.current.filename == "b.txt" and m.last_error is None
    assert m.current.info["n_text_messages"] == 2


def test_failed_second_upload_keeps_previous_run_visible():
    m = RunManager(CFG)
    m.submit(demo_data.build_demo_chat().encode(), "a.txt")
    first = m.current
    assert m.submit(b"this is not a chat\n", "b.txt") == "failed"
    assert m.current is first and m.current.filename == "a.txt"
    assert m.last_error is not None and m.last_error.code == "unsupported_format"
    assert m.submit(demo_data.build_demo_chat().encode(), "c.txt") == "replaced"     # recovers, error cleared
    assert m.last_error is None and m.current.filename == "c.txt"


def test_unexpected_runner_error_is_generic_and_keeps_previous_run():
    m = RunManager(CFG)
    m.submit(demo_data.build_demo_chat().encode(), "a.txt")
    first = m.current

    def broken(data, filename, config=None, progress=None):
        raise RuntimeError("internal detail: secret content")

    m.runner = broken
    assert m.submit(b"anything", "b.txt") == "failed"
    assert m.current is first and "secret" not in m.last_error.message


def test_same_file_is_not_reprocessed_on_rerun():
    calls = []

    def counting(data, filename, config=None, progress=None):
        calls.append(filename)
        return rp.run_pipeline(data, filename, config or CFG, progress)

    m = RunManager(CFG, runner=counting)
    data = demo_data.build_demo_chat().encode()
    assert m.submit(data, "a.txt") == "replaced"
    assert m.submit(data, "a.txt") == "unchanged"
    assert len(calls) == 1
    m.submit(b"junk", "bad.txt")
    assert m.submit(b"junk", "bad.txt") == "unchanged" and len(calls) == 2


def test_clear_drops_the_run():
    m = RunManager(CFG)
    m.submit(demo_data.build_demo_chat().encode(), "a.txt")
    m.clear()
    assert m.current is None and m.last_error is None


# --------------------------------------------------------------- participants ---
def test_participants_are_independent_per_run_and_hide_real_senders():
    a = run(chat(("3/10/25, 9:00:00 AM", "Alice Real", "hello there"), ("3/10/25, 9:01:00 AM", "Bob Real", "hi all")))
    b = run(chat(("3/10/25, 9:00:00 AM", "Carol Other", "hello there"), ("3/10/25, 9:01:00 AM", "Alice Real", "hi")))
    for r in (a, b):
        ids = list(r.tables["analytics_sender_counts"]["participant_id"])
        assert ids == [f"Participant_{i}" for i in range(1, len(ids) + 1)]
    # numbering restarts per run and carries no link across runs
    assert list(b.tables["analytics_sender_counts"]["participant_id"])[0] == "Participant_1"
    blob = json.dumps({k: v.to_dict("list") for k, v in {**a.tables, **b.tables}.items()}, default=str)
    assert "Alice" not in blob and "Bob Real" not in blob and "Carol" not in blob and "Sender_" not in blob


def test_assign_participants_first_appearance_only_pseudonyms_returned():
    assert ca.assign_participants(["x", "y", "x", None]) == ["Participant_1", "Participant_2", "Participant_1", None]


# ------------------------------------------------------------- privacy filtering ---
def _terms(**kw):
    return pd.DataFrame({"ngram": list(kw), "count_all": [v[0] for v in kw.values()],
                         "count_unique": [v[0] for v in kw.values()], "msgs_all": [v[1] for v in kw.values()],
                         "repetition_ratio": 1.0})


def test_single_message_terms_hidden_by_default_and_revealable():
    tables = {"ngram_unigrams": _terms(common=(4, 4), rare=(1, 1), twice=(2, 2)),
              "ngram_unigrams_with_stopwords": _terms(common=(4, 4)),
              "ngram_bigrams": _terms(**{"a b": (3, 3), "c d": (1, 1)}), "ngram_trigrams": _terms(**{"x y z": (1, 1)}),
              "tfidf_top_terms": pd.DataFrame({"variant": ["all", "all", "unique"], "term": ["common", "rare", "rare"],
                                               "script": "latin", "df": [4, 1, 1], "idf": 1.0, "total_tfidf": 1.0,
                                               "mean_tfidf_in_docs": 1.0, "n_docs_top3": 0}),
              "tfidf_variant_comparison": pd.DataFrame({"term": ["common", "rare"], "rank_all": [1, 2]})}
    shown, notice = dp.prepare_display_tables(tables, 2, False)
    assert list(shown["ngram_unigrams"]["ngram"]) == ["common", "twice"]
    assert list(shown["ngram_bigrams"]["ngram"]) == ["a b"] and shown["ngram_trigrams"].empty
    assert set(shown["tfidf_top_terms"]["term"]) == {"common"}
    assert list(shown["tfidf_variant_comparison"]["term"]) == ["common"]
    assert notice["rows_hidden_single_message"] > 0
    revealed, _ = dp.prepare_display_tables(tables, 2, True)
    assert "rare" in set(revealed["ngram_unigrams"]["ngram"])
    assert len(tables["ngram_unigrams"]) == 3                       # underlying table untouched


def test_sensitive_looking_terms_are_dropped_defensively():
    tables = {"ngram_unigrams": _terms(**{"https://x.io/a": (5, 5), "call 0123456789": (5, 5),
                                          "me@mail.com": (5, 5), "fine": (5, 5)})}
    shown, notice = dp.prepare_display_tables(tables, 2, True)
    assert list(shown["ngram_unigrams"]["ngram"]) == ["fine"] and notice["rows_hidden_sensitive_pattern"] == 3


# --------------------------------------------- no sensitive values in display data ---
SENSITIVE_CHAT = chat(
    ("3/10/25, 9:00:00 AM", None, "- Zed Quillfeather added +1 555 010 0142"),
    ("3/10/25, 9:01:00 AM", "+1 555 010 0142", "Join here https://secret.example.org/invite/XYZ123SECRET now"),
    ("3/10/25, 9:02:00 AM", "Zed Quillfeather", "Call +1 555 010 0999 about the meeting schedule"),
    ("3/10/25, 9:03:00 AM", "Zed Quillfeather", "Bring zephyrine to the meeting tomorrow"),
    ("3/11/25, 9:03:00 AM", "+1 555 010 0142", "Join here https://secret.example.org/invite/OTHER456 now"),
    ("3/11/25, 9:04:00 AM", "Zed Quillfeather", "The meeting schedule changed again"),
    ("3/11/25, 9:05:00 AM", "Zed Quillfeather", "Zed Quillfeather's security code changed. Tap to learn more."),
)
FORBIDDEN = ["+1 555 010 0142", "555 010 0142", "5550100142", "555 010 0999", "5550100999", "Zed Quillfeather",
             "Quillfeather", "secret.example.org", "XYZ123SECRET", "OTHER456", "https://", "zephyrine",
             "Bring zephyrine", "The meeting schedule changed again", "Call +1"]


def _display_blob(r):
    display, _ = dp.prepare_display_tables(r.tables, 2, False)
    parts = [json.dumps({k: v.astype(str).to_dict("list") for k, v in display.items()}, default=str),
             json.dumps(r.analytics_meta, default=str), json.dumps(r.tfidf_meta, default=str),
             json.dumps(r.info, default=str), json.dumps(r.warnings)]
    with zipfile.ZipFile(io.BytesIO(results_bundle.build_bundle(r, 2, False))) as z:
        parts += [z.read(n).decode("utf-8") for n in z.namelist()]
    return "\n".join(parts)


def test_no_raw_sensitive_values_in_display_ready_data_or_download():
    r = run(SENSITIVE_CHAT, "sensitive.txt")
    blob = _display_blob(r).lower()
    for value in FORBIDDEN:
        assert value.lower() not in blob, value
    assert "participant_1" in blob


def test_download_bundle_contains_only_approved_files():
    r = run(demo_data.build_demo_chat().encode())
    with zipfile.ZipFile(io.BytesIO(results_bundle.build_bundle(r))) as z:
        names = set(z.namelist())
    assert "README.txt" in names and "analytics_run_metadata.json" in names
    assert not {n for n in names if n.startswith(("processed_chat", "analysis_corpus", "tfidf_terms_by_message"))}
    # Script Mix and Key Terms were integrated into the dashboard (final polish): +3 files in the bundle
    assert {"script_mix_summary.csv", "script_mixing_stats.csv", "key_terms.csv"} <= names
    assert len(names) == 1 + 9 + 7 + 3 + 2


def test_demo_data_is_synthetic_and_runs_end_to_end():
    text = demo_data.build_demo_chat()
    assert "example.com" in text and "+91" not in text
    real = ROOT / "data" / "chat.txt"
    if real.exists():
        real_lines = {ln.split("] ", 1)[-1] for ln in real.read_text(encoding="utf-8").splitlines() if len(ln) > 30}
        demo_lines = {ln.split("] ", 1)[-1] for ln in text.splitlines() if len(ln) > 30}
        # nothing copied from the real chat (WhatsApp's own standard header notice is boilerplate)
        assert not ((real_lines & demo_lines) - {HEADER})
    r = run(text.encode(), demo_data.DEMO_FILENAME)
    assert r.info["n_text_messages"] > 0 and r.analytics_meta["all_reconciliation_checks_passed"]


# ------------------------------------------ Script Mix and Key Terms in the dashboard pipeline ---
def test_pipeline_stages_include_script_mix_and_key_terms_in_order():
    assert rp.STAGES.index("Script Mix") < rp.STAGES.index("Key Terms") < rp.STAGES.index("Conversation analytics")
    seen = []
    run(demo_data.build_demo_chat().encode(), progress=lambda i, label: seen.append(label))
    assert seen == list(rp.STAGES)                                   # every real stage reported, in order


def test_script_mix_and_key_terms_tables_are_loaded_and_reconcile():
    r = run(demo_data.build_demo_chat().encode())
    mix = r.tables["script_mix_summary"]
    n_text = r.info["n_text_messages"]
    assert mix[mix["variant"] == "all"]["messages"].sum() == n_text
    assert mix[mix["variant"] == "unique"]["messages"].sum() == int(
        r.tables["analytics_repetition_summary"].set_index("metric").loc["unique_texts_after_masking", "count"])
    kt_table = r.tables["key_terms"]
    assert not kt_table.empty and set(["term", "unique_texts_containing", "messages_containing"]) <= set(kt_table.columns)
    assert not rp.FORBIDDEN_COLUMNS & set(kt_table.columns)


def test_key_terms_display_filter_hides_single_message_terms_and_sensitive_patterns():
    table = pd.DataFrame({"rank": [1, 2, 3, 4], "term": ["common", "rare", "https://x.io/a", "call0123456789"],
                          "script": "latin", "unique_texts_containing": [4, 1, 3, 3], "messages_containing": [4, 1, 3, 3],
                          "occurrences_all": [5, 1, 3, 3], "occurrences_unique": [5, 1, 3, 3],
                          "repetition_ratio": 1.0, "tfidf_total_unique": 1.0})
    shown, notice = dp.prepare_display_tables({"key_terms": table}, 2, False)
    assert list(shown["key_terms"]["term"]) == ["common"]
    assert notice["rows_hidden_single_message"] == 1 and notice["rows_hidden_sensitive_pattern"] == 2
    revealed, _ = dp.prepare_display_tables({"key_terms": table}, 2, True)
    assert "rare" in set(revealed["key_terms"]["term"])
    assert len(table) == 4                                          # underlying table untouched


def test_key_terms_and_script_mix_in_download_bundle_are_filtered():
    r = run(SENSITIVE_CHAT, "sensitive.txt")
    with zipfile.ZipFile(io.BytesIO(results_bundle.build_bundle(r, 2, False))) as z:
        kt_text = z.read("key_terms.csv").decode("utf-8").lower()
        mix_text = z.read("script_mix_summary.csv").decode("utf-8").lower()
    assert "zephyrine" not in kt_text and "meeting" in kt_text
    for value in FORBIDDEN:
        assert value.lower() not in kt_text and value.lower() not in mix_text, value
