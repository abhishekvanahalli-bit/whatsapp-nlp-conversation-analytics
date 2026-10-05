import json
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ngram_analysis as ng  # noqa: E402
import preprocessor as pp  # noqa: E402
import script_mix_analysis as sm  # noqa: E402
from helpers import SAMPLE_CHAT, SAMPLE_CSV, SAMPLE_DIR, corpus_counts  # noqa: E402
from test_dashboard_core import FORBIDDEN, SENSITIVE_CHAT, chat  # noqa: E402

needs_data = pytest.mark.skipif(not SAMPLE_CSV.exists(), reason="synthetic sample outputs missing")

DEV = "खेळाडू"            # a Devanagari word
DEV2 = "सर्व"                        # another


def prof(text):
    return sm.profile_text(text)


# ------------------------------------------------------------ message classes ---
def test_latin_only():
    p = prof("Please share your picture")
    assert p.message_class == "latin_only" and p.latin_tokens == 4 and p.devanagari_tokens == 0
    assert p.alternations == 0 and p.devanagari_share == 0.0


def test_devanagari_only():
    p = prof(f"{DEV} {DEV2}")
    assert p.message_class == "devanagari_only" and p.devanagari_tokens == 2 and p.latin_tokens == 0
    assert p.alternations == 0 and p.devanagari_share == 1.0


def test_mixed_script_and_alternations():
    p = prof(f"group {DEV} {DEV2} join")          # latin, dev, dev, latin -> 2 alternations
    assert p.message_class == "mixed_script"
    assert (p.latin_tokens, p.devanagari_tokens, p.alternations) == (2, 2, 2)
    assert p.devanagari_share == 0.5


def test_alternation_counting_rules():
    assert prof(f"a {DEV} b").alternations == 2
    assert prof(f"a b {DEV} {DEV2} c").alternations == 2          # runs of one script do not add
    assert prof(f"{DEV} a {DEV2} b {DEV}").alternations == 4
    assert prof("a b c").alternations == 0


def test_punctuation_only_is_no_alphabetic():
    for text in ("...", "!!! ???", "- - -", "।", "।।"):      # includes danda
        assert prof(text).message_class == "no_alphabetic", text


def test_url_and_phone_only_are_no_alphabetic():
    assert prof("https://chat.whatsapp.com/SECRETCODE123").message_class == "no_alphabetic"
    assert prof("www.example.org/invite").message_class == "no_alphabetic"
    assert prof("call +91 99999 88888").message_class == "latin_only"       # 'call' only; number masked, not counted
    assert prof("+91 99999 88888").message_class == "no_alphabetic"


def test_numbers_and_emoji_are_not_letters():
    for text in ("2026", "12/34", "\U0001F3D0", "\U0001F3D0 ❤️ 123", "१२३"):  # incl. Devanagari digits
        assert prof(text).message_class == "no_alphabetic", text
    p = prof("match \U0001F3D0 2026")
    assert p.message_class == "latin_only" and p.n_alphabetic == 1 and p.n_tokens == 3


def test_empty_and_whitespace_text():
    for text in ("", "   ", "\n\t"):
        p = prof(text)
        assert p.message_class == "no_alphabetic" and p.n_tokens == 0 and p.alternations == 0
        assert math.isnan(p.devanagari_share) and p.is_short
    assert sm.profile_text(None).message_class == "no_alphabetic"


def test_zero_width_joiner_and_devanagari_marks_belong_to_the_word():
    word = "क्‍ष"                                     # letters, virama and ZWJ
    p = sm.message_profile([word])
    assert p.message_class == "devanagari_only" and p.devanagari_tokens == 1 and p.devanagari_letters == 2


def test_token_glued_across_scripts_is_mixed_token():
    p = sm.message_profile([f"abc{DEV}"])
    assert p.message_class == "mixed_script" and p.mixed_tokens == 1
    assert p.latin_tokens == 0 and p.devanagari_tokens == 0 and p.devanagari_share == 0.0


def test_other_script_only():
    assert sm.message_profile(["مرحبا"]).message_class == "other_script_only"      # Arabic
    assert sm.message_profile(["a", "مرحبا"]).message_class == "mixed_script"


def test_short_messages_are_classed_and_flagged_not_dropped():
    assert prof("ok").is_short and prof("ok").message_class == "latin_only"
    assert prof(f"{DEV}").is_short and prof(f"{DEV}").message_class == "devanagari_only"
    assert not prof("one two three four").is_short


def test_letter_script_uses_unicode_names():
    assert sm.letter_script("a") == "latin" and sm.letter_script("é") == "latin"      # accented Latin
    assert sm.letter_script("ख") == "devanagari"
    assert sm.letter_script("१") is None and sm.letter_script("।") is None        # digit, danda
    assert sm.letter_script("7") is None and sm.letter_script("\U0001F3D0") is None


def test_repeated_execution_is_deterministic():
    text = f"group {DEV} join {DEV2} team"
    assert prof(text) == prof(text) == prof(text)


# ---------------------------------------------------------------- aggregates ---
def corpus_from(texts, repeats=None):
    toks = [ng.analysis_tokenize(t.lower()) for t in texts]
    seen, flags = set(), []
    for t in toks:
        key = tuple(t)
        flags.append(key in seen)
        seen.add(key)
    return pd.DataFrame({"tokens": toks, "is_repeat": flags if repeats is None else repeats})


def test_aggregate_reconciliation_and_variants():
    texts = ["hello there team", "hello there team", f"group {DEV} join", "https://x.io/a", f"{DEV} {DEV2}", "!!!"]
    by = sm.profiles_by_variant(corpus_from(texts))
    assert len(by["all"]) == 6 and len(by["unique"]) == 5                  # exact repeat collapses only in 'unique'
    summary = sm.summary_table(by)
    for variant, n in (("all", 6), ("unique", 5)):
        sub = summary[summary["variant"] == variant]
        assert sub["messages"].sum() == n and (sub["denominator"] == n).all()
    all_counts = summary[summary["variant"] == "all"].set_index("message_class")["messages"].to_dict()
    assert all_counts == {"latin_only": 2, "devanagari_only": 1, "mixed_script": 1, "other_script_only": 0,
                          "no_alphabetic": 2}
    uniq_counts = summary[summary["variant"] == "unique"].set_index("message_class")["messages"].to_dict()
    assert uniq_counts["latin_only"] == 1                                   # the repeat is not counted again


def test_stats_table_values_on_known_messages():
    texts = [f"a {DEV} b", f"a b {DEV} {DEV2}", "plain english text", "..."]
    stats = sm.stats_table(sm.profiles_by_variant(corpus_from(texts)))
    s = stats[stats["variant"] == "all"].set_index("metric")["value"]
    assert s["mixed_script_messages"] == 2 and s["total_alternations"] == 3          # 2 (a DEV b) + 1 (a b DEV DEV2)
    assert s["max_alternations_mixed"] == 2 and s["median_alternations_mixed"] == 1.5
    assert s["min_devanagari_share_mixed"] == round(1 / 3, 4) and s["max_devanagari_share_mixed"] == 0.5
    assert s["share_0.25_to_0.5"] == 2 and s["no_alphabetic_messages"] == 1
    assert s["alphabetic_tokens_latin"] == 7 and s["alphabetic_tokens_devanagari"] == 3


def test_no_mixed_messages_gives_blank_statistics_not_errors():
    stats = sm.stats_table(sm.profiles_by_variant(corpus_from(["only english words here"])))
    s = stats[stats["variant"] == "all"].set_index("metric")["value"]
    assert s["mixed_script_messages"] == 0 and s["median_alternations_mixed"] == ""


def test_empty_corpus():
    by = sm.profiles_by_variant(pd.DataFrame({"tokens": [], "is_repeat": []}))
    assert by == {"all": [], "unique": []}
    summary, stats = sm.summary_table(by), sm.stats_table(by)
    assert summary["messages"].sum() == 0 and (summary["denominator"] == 0).all()
    assert stats.loc[stats["metric"] == "mixed_script_messages", "value"].tolist() == [0, 0]


# ------------------------------------------------ sample data (fictional fixture) ---
@needs_data
def test_sample_data_counts_and_reconciliation(tmp_path):
    summary, stats, meta = sm.run_script_mix(SAMPLE_CSV, tmp_path, SAMPLE_DIR)
    n_all, n_unique, _ = corpus_counts()
    a = summary[summary["variant"] == "all"].set_index("message_class")["messages"].to_dict()
    assert sum(a.values()) == n_all
    assert a == {"latin_only": 103, "devanagari_only": 28, "mixed_script": 2, "other_script_only": 0, "no_alphabetic": 10}
    u = summary[summary["variant"] == "unique"].set_index("message_class")["messages"].to_dict()
    assert sum(u.values()) == n_unique
    assert meta["all_reconciliation_checks_passed"]
    assert meta["agreement_with_existing_script_diagnostics"]["agrees"] is True


@needs_data
def test_real_data_reconciles_with_existing_outputs(tmp_path):
    sm.run_script_mix(SAMPLE_CSV, tmp_path, SAMPLE_DIR)
    corpus = pd.read_csv(SAMPLE_DIR / "analysis_corpus.csv")
    summary = pd.read_csv(tmp_path / "script_mix_summary.csv")
    assert summary[summary["variant"] == "all"]["messages"].sum() == len(corpus)
    assert summary[summary["variant"] == "unique"]["messages"].sum() == int((~corpus["is_repeat"]).sum())
    diag = pd.read_csv(SAMPLE_DIR / "ngram_script_diagnostics.csv").set_index("script")["tokens_before"]
    stats = pd.read_csv(tmp_path / "script_mixing_stats.csv")
    s = stats[stats["variant"] == "all"].set_index("metric")["value"]
    assert s["alphabetic_tokens_latin"] == diag["latin"] and s["alphabetic_tokens_devanagari"] == diag["devanagari"]


@needs_data
def test_outputs_are_deterministic_and_leave_existing_files_alone(tmp_path):
    protected = [p for p in SAMPLE_DIR.iterdir() if p.is_file()] + [SAMPLE_CHAT]
    before = {p: p.read_bytes() for p in protected if p.exists()}
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    sm.run_script_mix(SAMPLE_CSV, a, SAMPLE_DIR)
    sm.run_script_mix(SAMPLE_CSV, b, SAMPLE_DIR)
    for name in sm.OUTPUT_FILES:
        assert (a / name).read_bytes() == (b / name).read_bytes(), name
    assert all(p.read_bytes() == c for p, c in before.items())


def test_reconciliation_failure_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "reconciliation_checks",
                        lambda *a, **k: ([{"check": "forced", "left": 1, "right": 2, "passed": False}], None))
    with pytest.raises(AssertionError):
        sm.run_script_mix(SAMPLE_CSV, tmp_path, SAMPLE_DIR)
    assert list(tmp_path.iterdir()) == []


# ------------------------------------------------------------------- privacy ---
def test_outputs_contain_only_aggregate_counts_no_sensitive_values(tmp_path):
    chat_file = tmp_path / "chat.txt"
    chat_file.write_bytes(SENSITIVE_CHAT)
    df, _ = pp.build_dataset(chat_file)
    pp.save_processed_csv(df, tmp_path / "processed_chat.csv")
    out = tmp_path / "out"
    out.mkdir()
    summary, stats, meta = sm.run_script_mix(tmp_path / "processed_chat.csv", out)
    blob = "\n".join((out / n).read_text(encoding="utf-8") for n in sm.OUTPUT_FILES).lower()
    for value in FORBIDDEN:
        assert value.lower() not in blob, value
    csv_blob = "\n".join((out / n).read_text(encoding="utf-8") for n in sm.OUTPUT_FILES if n.endswith(".csv")).lower()
    for marker in ("sender", "participant", "http", "+1 555", "@", "line_start"):
        assert marker not in csv_blob, marker
    assert len(summary) == 2 * len(sm.CLASSES)                                # fixed size: no per-message rows
    assert set(summary.columns) == {"variant", "message_class", "messages", "denominator", "short_messages"}
    assert set(stats.columns) == {"variant", "metric", "value", "denominator"}
    assert "line_start" not in blob and json.loads((out / "script_mix_metadata.json").read_text(encoding="utf-8"))


def test_zero_text_chat_runs_and_reports_zeros(tmp_path):
    chat_file = tmp_path / "chat.txt"
    chat_file.write_bytes(chat(("3/10/25, 9:00:00 AM", "Ann", "<image omitted>")))
    df, _ = pp.build_dataset(chat_file)
    pp.save_processed_csv(df, tmp_path / "processed_chat.csv")
    out = tmp_path / "out"
    out.mkdir()
    summary, stats, meta = sm.run_script_mix(tmp_path / "processed_chat.csv", out)
    assert summary["messages"].sum() == 0 and meta["all_reconciliation_checks_passed"]
