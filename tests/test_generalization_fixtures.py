"""Generalisation tests: the same pipeline on different kinds of fictional chats, privacy of the anonymised
download, and the scale-aware TF-IDF stability diagnostic. No private data is used."""

import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import FIXTURES, fixture_bytes, outputs_for  # noqa: E402

import ngram_analysis as ng  # noqa: E402
import run_pipeline as rp  # noqa: E402
import tfidf_analysis as tf  # noqa: E402
from app_config import AppConfig  # noqa: E402
from display_privacy import prepare_display_tables  # noqa: E402
from results_bundle import build_bundle  # noqa: E402

CFG = AppConfig()
ALL = sorted(p.name for p in FIXTURES.glob("*.txt"))
EXPECTED_PARTICIPANTS = {"one_to_one.txt": 2, "group_12.txt": 12, "single_sender.txt": 1, "zero_text.txt": 2,
                         "media_deleted.txt": 2, "numeric_terms.txt": 2, "privacy_cases.txt": 2}


def run(name):
    return rp.run_pipeline(fixture_bytes(name), name, CFG)


def test_fixture_set_is_complete():
    required = {"one_to_one.txt", "group_12.txt", "group_30.txt", "single_sender.txt", "parser_system_events.txt",
                "parser_unicode.txt", "numeric_terms.txt", "privacy_cases.txt", "zero_text.txt", "media_deleted.txt"}
    assert required <= set(ALL)


@pytest.mark.parametrize("name", ALL)
def test_every_fixture_runs_the_whole_pipeline(name):
    r = run(name)
    assert r.analytics_meta["all_reconciliation_checks_passed"]
    assert r.info["n_rows"] > 0
    comp = r.tables["analytics_row_composition"].set_index(["group", "category"])["count"]
    assert comp[("parsed_rows", "header")] + comp[("parsed_rows", "system")] + comp[("parsed_rows", "user")] == r.info["n_rows"]
    assert not any(rp.FORBIDDEN_COLUMNS & set(t.columns) for t in r.tables.values())
    names = zipfile.ZipFile(io.BytesIO(build_bundle(r, 2, False))).namelist()           # download builds for every kind of chat
    assert len(names) == 22 and not any(n.startswith(("processed_chat", "analysis_corpus")) for n in names)


@pytest.mark.parametrize("name,count", sorted(EXPECTED_PARTICIPANTS.items()))
def test_participant_counts(name, count):
    assert len(run(name).tables["analytics_sender_counts"]) == count


def test_thirty_participant_group_uses_pseudonyms_only():
    senders = run("group_30.txt").tables["analytics_sender_counts"]["participant_id"]
    assert len(senders) >= 25 and all(re.fullmatch(r"Participant_\d+", s) for s in senders)


def test_one_to_one_and_single_sender_have_no_system_rows_and_no_group_assumptions():
    for name in ("one_to_one.txt", "single_sender.txt"):
        comp = run(name).tables["analytics_row_composition"].set_index(["group", "category"])["count"]
        assert comp[("parsed_rows", "system")] == 0


def test_zero_text_chat_is_limited_not_broken():
    r = run("zero_text.txt")
    assert r.info["n_text_messages"] == 0 and r.analytics_meta["limited_result"]
    assert r.tables["ngram_unigrams"].empty and r.tables["tfidf_top_terms"].empty and r.tables["key_terms"].empty
    assert any("No text messages" in w for w in r.warnings)


@pytest.mark.parametrize("n_text", [1, 2, 5])
def test_very_small_chats_run_and_warn(n_text, tmp_path):
    lines = ["‎header"] + [f"[3/10/26, 9:0{i}:00 AM] Alex Demo: ground practice {i}" for i in range(n_text)]
    r = rp.run_pipeline(("\n".join(lines) + "\n").encode(), "small.txt", CFG)
    assert r.info["n_text_messages"] == n_text
    assert any("text message" in w for w in r.warnings)
    assert r.analytics_meta["all_reconciliation_checks_passed"]


def test_all_identical_and_stopword_only_and_emoji_only_chats_run():
    for body in ("ok", "the and of", "\U0001F600\U0001F602"):
        lines = ["‎header"] + [f"[3/10/26, 9:0{i}:00 AM] A: {body}" for i in range(6)]
        r = rp.run_pipeline(("\n".join(lines) + "\n").encode(), "x.txt", CFG)
        assert r.analytics_meta["all_reconciliation_checks_passed"]


# -------------------------------------------------------------------- privacy ---
FORBIDDEN_STRINGS = ["9000012345", "90000 12345", "09000-012345", "012345", "011 2345", "2345 6789", "6789",
                     "chat.whatsapp", "fictionalinvite", "demo.person", "example.org", "example.com", "example.net",
                     "www.", "@", "http", "+91", "Alex Demo", "Sam Sample"]


def _bundle_text(run_result, show_single=False):
    z = zipfile.ZipFile(io.BytesIO(build_bundle(run_result, 2, show_single)))
    return "\n".join(z.read(n).decode("utf-8") for n in z.namelist())


def test_privacy_cases_do_not_reach_the_download_or_display_tables():
    r = run("privacy_cases.txt")
    blob = _bundle_text(r).lower()
    for value in FORBIDDEN_STRINGS:
        assert value.lower() not in blob, value
    display, _ = prepare_display_tables(r.tables, 2, True)           # even with "show single-message terms" switched on
    shown = "\n".join(display[t].to_csv(index=False) for t in
                      ("ngram_unigrams", "ngram_bigrams", "ngram_trigrams", "tfidf_top_terms", "key_terms")).lower()
    for value in FORBIDDEN_STRINGS:
        assert value.lower() not in shown, value


def test_privacy_cases_are_masked_at_tokenisation_not_only_hidden_at_display():
    for text in ("call 9000012345 now", "or 09000-012345 today", "office 011 2345 6789 open", "+91 9000012345",
                 "+91-9000012345", "+91 90000 12345"):
        assert ng.PHONE_TOKEN in ng.analysis_tokenize(text), text
    for text in ("join chat.whatsapp.com/FICTIONALINVITE01 now", "join https://chat.whatsapp.com/X now",
                 "mail demo.person@example.org", "visit www.example.com/page", "see example.net/docs"):
        assert ng.URL_TOKEN in ng.analysis_tokenize(text.lower()), text


def test_dates_prices_and_ordinary_numbers_are_not_masked_as_phones():
    assert ng.PHONE_TOKEN not in ng.analysis_tokenize("meeting on 10-03-2026 14:30 at 5 pm paid 500 rupees")
    assert ng.PHONE_TOKEN not in ng.analysis_tokenize("year 2026 room 305 total 12345")


def test_names_in_several_messages_are_not_hidden_documented_limitation():
    """Privacy filtering is a precaution, not PII detection: a name repeated across messages stays visible."""
    r = run("privacy_cases.txt")
    display, _ = prepare_display_tables(r.tables, 2, False)
    assert "meera" in set(display["ngram_unigrams"]["ngram"])


def test_download_metadata_has_no_source_line_numbers():
    r = run("group_12.txt")
    z = zipfile.ZipFile(io.BytesIO(build_bundle(r, 2, False)))
    meta = json.loads(z.read("tfidf_run_metadata.json"))
    assert all("empty_document_line_start" not in v for v in meta["variants"].values())


def test_bundle_contains_no_sender_names_in_any_fixture():
    for name, people in (("group_12.txt", ["Alex Demo", "Riya Testwala", "Kabir Fictional", "Omkar Testkar"]),
                         ("one_to_one.txt", ["Alex Demo", "Sam Sample"]),
                         ("group_30.txt", ["Member 07 Fictional", "Member 21 Fictional"])):
        blob = _bundle_text(run(name)).lower()
        for p in people:
            assert p.lower() not in blob, (name, p)


# --------------------------------------------------- TF-IDF stability diagnostic ---
def test_stability_indices_full_below_threshold_and_sampled_above():
    idx, mode = tf.stability_indices(50)
    assert mode == "full_leave_one_out" and idx == list(range(50))
    idx, mode = tf.stability_indices(1000)
    assert mode == "sampled_leave_one_out" and len(idx) <= tf.LOO_SAMPLE_RUNS
    assert idx == sorted(set(idx)) and idx[0] == 0 and idx[-1] == 999
    assert tf.stability_indices(1000) == (idx, mode)                 # deterministic


def test_sampled_stability_records_mode_and_is_deterministic():
    docs = [[f"w{i % 17}", f"w{(i * 3) % 23}", "common"] for i in range(260)]
    a = tf.leave_one_out_stability(docs)
    b = tf.leave_one_out_stability(docs)
    assert a == b and a["mode"] == "sampled_leave_one_out"
    assert a["n_documents"] == 260 and 0 < a["n_runs"] <= tf.LOO_SAMPLE_RUNS
    full = tf.leave_one_out_stability(docs[:40])
    assert full["mode"] == "full_leave_one_out" and full["n_runs"] == 40


def test_stability_mode_never_changes_the_tfidf_scores(tmp_path, monkeypatch):
    """The diagnostic is separate from the main output: forcing the sampled mode leaves every score identical."""
    base = outputs_for("group_12.txt")
    original = tf.leave_one_out_stability
    monkeypatch.setattr(tf, "leave_one_out_stability", lambda terms, k=tf.TOP_K: original(terms, k, full_max=10, sample_runs=5))
    tf.run_tfidf(base / "processed_chat.csv", tmp_path, base)
    for name in ("tfidf_top_terms.csv", "tfidf_terms_by_message.csv", "tfidf_variant_comparison.csv"):
        assert (tmp_path / name).read_bytes() == (base / name).read_bytes(), name
    meta = json.loads((tmp_path / "tfidf_run_metadata.json").read_text(encoding="utf-8"))
    assert meta["variants"]["all"]["leave_one_out_top_k"]["mode"] == "sampled_leave_one_out"
    assert json.loads((base / "tfidf_run_metadata.json").read_text(encoding="utf-8"))[
        "variants"]["all"]["leave_one_out_top_k"]["mode"] == "full_leave_one_out"


def test_larger_chat_completes_in_reasonable_time():
    import time
    lines = ["‎header"]
    for i in range(420):
        lines.append(f"[3/{1 + i // 60}/26, {1 + i % 11}:{i % 60:02d}:00 PM] P{i % 7}: word{i % 211} word{(i * 7) % 307} "
                     f"common{i % 5} filler{(i * 13) % 97}")
    t = time.perf_counter()
    r = rp.run_pipeline(("\n".join(lines) + "\n").encode(), "large.txt", CFG)
    assert r.info["n_text_messages"] == 420
    assert r.tfidf_meta["variants"]["all"]["leave_one_out_top_k"]["mode"] == "sampled_leave_one_out"
    assert time.perf_counter() - t < 60
