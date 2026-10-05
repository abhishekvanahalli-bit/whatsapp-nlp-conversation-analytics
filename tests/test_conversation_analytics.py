import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import conversation_analytics as ca  # noqa: E402
import ngram_analysis as ng  # noqa: E402
from helpers import SAMPLE_CHAT, SAMPLE_CSV, SAMPLE_DIR  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = SAMPLE_DIR                         # outputs of the fictional 12-participant group fixture
PROTECTED = [SAMPLE_CHAT, SAMPLE_CSV] + sorted(
    p for p in RESULTS.iterdir() if p.name.startswith(("ngram_", "tfidf_", "analysis_corpus")))

needs_data = pytest.mark.skipif(not SAMPLE_CSV.exists(), reason="synthetic sample outputs missing")
PHONE_RE = re.compile(r"\+?\d[\d ]{7,}\d")
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)


# ----------------------------------------------------------- synthetic data ---
def make_df(rows):
    """rows: (message_type, sender, message, datetime, media, deleted, forwarded, media_type)"""
    cols = ["message_type", "sender", "message", "datetime", "is_media", "is_deleted",
            "is_forwarded", "media_type"]
    df = pd.DataFrame(rows, columns=cols)
    df["line_start"] = range(1, len(df) + 1)
    df["clean_message"] = df["message"].str.lower()
    return df


def synthetic():
    return make_df([
        ("header", None, "encrypted notice", None, False, False, False, None),
        ("system", None, "+91 11111 22222 added +91 33333 44444", "2026-01-01 08:00:00", False, False, False, None),
        ("user", "+91 11111 22222", "join https://chat.whatsapp.com/AAA now", "2026-01-01 09:00:00", False, False, False, None),
        ("user", "+91 11111 22222", "join https://chat.whatsapp.com/BBB now", "2026-01-01 09:05:00", False, False, False, None),
        ("user", "Bob", "hello there", "2026-01-04 10:00:00", False, False, False, None),
        ("user", "Bob", "hello there", "2026-01-04 10:01:00", False, False, False, None),
        ("user", "+91 11111 22222", "<image omitted>", "2026-01-04 11:00:00", True, False, False, "image"),
        ("user", "+91 11111 22222", "This message was deleted", "2026-01-04 11:30:00", False, True, False, None),
        ("user", "Bob", "[Forwarded] one off", "2026-01-04 12:00:00", False, False, True, None),
    ])


# ------------------------------------------------------------ unit tests ---
def test_user_row_kind():
    d = synthetic()
    kinds = ca.user_row_kind(d).tolist()
    assert kinds == ["", "", "text", "text", "text", "text", "media", "deleted", "text"]


def test_system_category_generic_labels():
    assert ca.system_category("‎+91 99999 99999's security code changed. Tap to learn more.") == "security_code_changed"
    assert ca.system_category("Some Name's security code changed. Tap to learn more.") == "security_code_changed"
    assert ca.system_category("+91 1 added +91 2") == "member_added"
    assert ca.system_category("+91 1 changed settings: only admins can send messages") == "settings_changed"
    assert ca.system_category("something unexpected") == "other_system_event"
    assert {ca.system_category(m) for m in ("a added b", "x", "security code changed")} <= set(ca.SYSTEM_CATEGORIES)


def test_participants_first_appearance_and_independent_prefix():
    out = ca.assign_participants(["z", "a", "z", None, "b", "a"])
    assert out == ["Participant_1", "Participant_2", "Participant_1", None, "Participant_3", "Participant_2"]
    assert all(p is None or p.startswith("Participant_") for p in out)
    assert not any(p and "Sender_" in p for p in out)     # independent of the NLP labels


def test_daily_activity_zero_filled_calendar():
    d = ca.prepare(synthetic())
    daily = ca.daily_activity_table(d)
    assert list(daily["date"]) == ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
    assert list(daily["total_rows"]) == [3, 0, 0, 5]
    assert list(daily["is_active"]) == [True, False, False, True]
    row = daily.iloc[3]
    assert (row["text_messages"], row["media_rows"], row["deleted_rows"], row["system_rows"]) == (3, 1, 1, 0)
    assert daily["total_rows"].sum() == d["dt"].notna().sum()


def test_hour_and_weekday_tables_sum_to_timestamped_rows():
    d = ca.prepare(synthetic())
    hours, week = ca.hour_histogram_table(d), ca.weekday_table(d)
    assert len(hours) == 24 and hours[["user_rows", "system_rows"]].sum().sum() == 8
    assert week[["user_rows", "system_rows"]].sum().sum() == 8
    assert week["calendar_days_in_range"].sum() == 4
    assert list(week["weekday"]) == list(ca.WEEKDAYS)


def test_repetition_exact_vs_template():
    raw = synthetic()
    d = ca.prepare(raw)
    corpus = ng.build_analysis_corpus(raw)
    summary, groups, _ = ca.repetition_tables(d, corpus)
    s = summary.set_index("metric")["count"]
    assert s["text_messages"] == 5 and s["unique_texts_after_masking"] == 3
    assert s["repeat_messages_after_masking"] == 2           # invite pair + hello pair
    assert s["exact_raw_duplicate_groups"] == 1              # only the hello pair is raw-identical
    assert s["repeats_visible_only_after_masking"] == 1      # the invite pair differs only by link
    assert list(groups["template_id"]) == ["T1", "T2"]
    assert list(groups["exact_raw_identical"]) == [False, True]
    assert "text" not in " ".join(groups.columns).lower().replace("distinct_raw_texts", "")


def test_metadata_counts_synthetic():
    raw = synthetic()
    d = ca.prepare(raw)
    m = ca.metadata_counts_table(d, ng.build_analysis_corpus(raw)).set_index("metric")["count"]
    assert m["forwarded_user_rows"] == 1 and m["forwarded_text_messages"] == 1
    assert m["deleted_rows"] == 1 and m["media_rows"] == 1
    assert m["text_messages_with_url"] == 2
    assert m["text_messages_with_phone_pattern"] == 0


def test_reconciliation_detects_a_mismatch():
    raw = synthetic()
    d = ca.prepare(raw)
    corpus = ng.build_analysis_corpus(raw)
    summary, groups, _ = ca.repetition_tables(d, corpus)
    tables = {"composition": ca.row_composition_table(d), "metadata": ca.metadata_counts_table(d, corpus),
              "daily": ca.daily_activity_table(d), "senders": ca.sender_counts_table(d),
              "hour": ca.hour_histogram_table(d), "weekday": ca.weekday_table(d),
              "length": ca.text_length_summary_table(corpus)}
    assert all(c["passed"] for c in ca.reconciliation_checks(d, tables, summary, groups))
    tables["senders"].loc[0, "user_rows"] += 1                # corrupt one table
    assert not all(c["passed"] for c in ca.reconciliation_checks(d, tables, summary, groups))


def test_failed_reconciliation_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "reconciliation_checks",
                        lambda *a, **k: [{"check": "forced", "left": 1, "right": 2, "passed": False}])
    with pytest.raises(AssertionError):
        ca.run_analytics(SAMPLE_CSV, tmp_path, RESULTS)
    assert list(tmp_path.iterdir()) == []


# --------------------------------------------- real-data pipeline checks ---
@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("analytics")
    before = {p: p.read_bytes() for p in PROTECTED if p.exists()}
    tables, meta = ca.run_analytics(SAMPLE_CSV, out, RESULTS)
    return out, before, tables, meta


@needs_data
def test_only_approved_files_generated(run):
    out, *_ = run
    assert {p.name for p in out.iterdir()} == set(ca.OUTPUT_FILES)


@needs_data
def test_known_totals_and_reconciliation(run):
    _, _, tables, meta = run
    assert meta["all_reconciliation_checks_passed"] and meta["n_reconciliation_checks"] >= 25
    comp = tables["composition"].set_index(["group", "category"])["count"]
    assert (comp[("parsed_rows", "header")], comp[("parsed_rows", "system")],
            comp[("parsed_rows", "user")]) == (1, 7, 160)      # fictional group_12 fixture
    assert (comp[("user_rows", "text")], comp[("user_rows", "media")],
            comp[("user_rows", "deleted")]) == (143, 12, 5)
    s = tables["repetition_summary"].set_index("metric")["count"]
    assert (s["text_messages"], s["unique_texts_after_masking"],
            s["repeat_messages_after_masking"]) == (143, 44, 99)
    assert sorted(tables["senders"]["user_rows"]) == [7, 9, 10, 11, 11, 14, 15, 16, 16, 16, 17, 18]
    assert tables["senders"]["user_rows"].sum() == 160
    assert all(c["passed"] for c in meta["reconciliation_checks"])


@needs_data
def test_agrees_with_existing_nlp_outputs(run):
    _, _, tables, _ = run
    corpus = pd.read_csv(RESULTS / "analysis_corpus.csv")
    s = tables["repetition_summary"].set_index("metric")["count"]
    assert s["text_messages"] == len(corpus)
    assert s["repeat_messages_after_masking"] == int(corpus["is_repeat"].sum())
    m = tables["metadata"].set_index("metric")["count"]
    assert m["forwarded_text_messages"] == int(corpus["is_forwarded"].sum())
    tfidf = json.loads((RESULTS / "tfidf_run_metadata.json").read_text(encoding="utf-8"))
    assert tfidf["variants"]["all"]["n_documents_N"] == s["text_messages"]
    assert tfidf["variants"]["unique"]["n_documents_N"] == s["unique_texts_after_masking"]


@needs_data
def test_daily_timeline_covers_full_calendar(run):
    _, _, tables, _ = run
    daily = tables["daily"]
    dates = pd.to_datetime(daily["date"])
    assert (dates.diff().dropna() == pd.Timedelta(days=1)).all()   # no gaps: zero-filled
    assert int(daily["total_rows"].sum()) == 167


# ------------------------------------------------------------ privacy tests ---
def _output_blob(out):
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(out.iterdir()))


def _forbidden(raw):
    """Sensitive strings loaded from the raw data at test time (never stored)."""
    senders = set(raw["sender"].dropna())
    msgs = raw["message"].astype(str)
    phones = {m.group().strip() for t in msgs for m in PHONE_RE.finditer(t)}
    urls = {m.group().rstrip(".,)") for t in msgs for m in URL_RE.finditer(t)}
    names = set()
    for t in raw.loc[raw["message_type"] == "system", "message"].astype(str):
        rest = PHONE_RE.sub("", t.replace("‎", ""))
        rest = re.sub(r"'s security code changed\. tap to learn more\.|\badded\b|"
                      r"changed settings: only admins can send messages", "", rest, flags=re.I)
        rest = rest.strip()
        if len(rest) >= 3:
            names.add(rest)
    return senders, phones, urls, names


@needs_data
def test_privacy_no_identifiers_or_links(run):
    out, *_ = run
    raw = pd.read_csv(SAMPLE_CSV)
    senders, phones, urls, names = _forbidden(raw)
    assert senders and phones and urls and names, "privacy test would be vacuous"
    blob = _output_blob(out)
    low = blob.lower()
    for s in senders | phones | urls | names:
        assert s.lower() not in low, f"leaked: {s[:4]}..."
    digits = {re.sub(r"\D", "", s) for s in senders | phones if len(re.sub(r"\D", "", s)) >= 8}
    for dgt in digits:
        assert dgt not in re.sub(r"\D", "", blob), "phone digits leaked"
    assert not re.search(r"\d{8,}", blob)                   # no long digit runs at all
    for token in ("http", "www.", "chat.whatsapp", "+91", "@"):
        assert token not in low, token
    assert "sender_" not in low                             # NLP pseudonyms are not reused


@needs_data
def test_privacy_no_raw_message_or_system_text(run):
    out, *_ = run
    raw = pd.read_csv(SAMPLE_CSV)
    blob = _output_blob(out).lower()
    for col in ("message", "clean_message"):
        for text in raw[col].astype(str):
            if len(text.strip()) >= 12:
                assert text.strip().lower() not in blob
    texts = raw.loc[(raw["message_type"] != "header") & ~raw["is_media"], "clean_message"].astype(str)
    for t in texts:
        words = re.findall(r"\w+", t.lower())
        for i in range(len(words) - 3):                      # no 4-word run of any message
            assert " ".join(words[i:i + 4]) not in re.sub(r"[^\w]+", " ", blob), t[:20]
    for p in out.glob("*.csv"):
        cols = [c.lower() for c in pd.read_csv(p).columns]
        assert not {"sender", "message", "text", "url", "clean_message", "tokens"} & set(cols), p.name


@needs_data
def test_privacy_only_generic_labels_and_pseudonyms(run):
    out, _, tables, _ = run
    cats = set(tables["composition"].query("group == 'system_category'")["category"])
    assert cats == set(ca.SYSTEM_CATEGORIES)
    assert all(re.fullmatch(r"Participant_\d+", p) for p in tables["senders"]["participant_id"])
    assert all(re.fullmatch(r"T\d+", t) for t in tables["repetition_groups"]["template_id"])
    assert not (set(pd.read_csv(RESULTS / "analysis_corpus.csv")["sender_anon"])
                & set(tables["senders"]["participant_id"]))


@needs_data
def test_no_timezone_claim_and_excluded_analyses_absent(run):
    out, _, _, meta = run
    assert "not verified" in meta["timestamps"]
    low = _output_blob(out).lower()
    for tz in ("utc", "gmt", "ist ", "timezone: ", "+05:30"):
        assert tz not in low
    for p in out.glob("*.csv"):
        cols = set(pd.read_csv(p).columns)
        assert not {"period", "morning", "afternoon", "evening", "night"} & cols
    assert not any("network" in n or "reply" in n for n in ca.OUTPUT_FILES)


# --------------------------------------------------------- robustness tests ---
@needs_data
def test_deterministic_output(tmp_path, run):
    out, *_ = run
    second = tmp_path / "second"
    second.mkdir()
    ca.run_analytics(SAMPLE_CSV, second, RESULTS)
    for p in out.iterdir():
        assert p.read_bytes() == (second / p.name).read_bytes(), p.name


@needs_data
def test_raw_and_existing_outputs_unchanged(run):
    _, before, *_ = run
    assert before, "nothing protected was snapshotted"
    for p, content in before.items():
        assert p.read_bytes() == content, f"{p.name} changed"
