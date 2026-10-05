"""Regression tests for the parser, placeholder classification, tokenizer and typed CSV round trip.

Each test pins a bug found in the master audit (docs/final_audit_fixes.md) or a documented rule. All data are the
fictional chats in tests/fixtures/ or inline strings; the private development chat is never used here.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import FIXTURES, fixture_bytes, outputs_for  # noqa: E402

import conversation_analytics as ca  # noqa: E402
import ngram_analysis as ng  # noqa: E402
import preprocessor as pp  # noqa: E402
import run_pipeline as rp  # noqa: E402
from app_config import AppConfig  # noqa: E402
from csv_io import read_csv_typed  # noqa: E402


def parse(name):
    entries, failures = pp.parse_chat(FIXTURES / name)
    return pd.DataFrame(entries), failures


# ------------------------------------------------ 1. sender-less timestamped lines ---
def test_sender_less_timestamped_lines_are_system_rows():
    df, failures = parse("parser_system_events.txt")
    assert not failures
    assert set(df["message_type"]) == {"system", "user"}            # nothing "unparsed", no header (notice has a timestamp)
    assert (df["message_type"] == "system").sum() == 10 and (df["message_type"] == "user").sum() == 2
    assert df.loc[df["message_type"] == "system", "sender"].isna().all()   # system rows never carry a participant


def test_system_sentence_with_colon_inside_quotes_is_not_a_participant():
    df, _ = parse("parser_system_events.txt")
    users = set(df.loc[df["message_type"] == "user", "sender"])
    assert users == {"Sam Sample", "Alex Demo"}


def test_system_events_keep_generic_categories_and_never_enter_nlp():
    out = outputs_for("parser_system_events.txt")
    comp = pd.read_csv(out / "analytics_row_composition.csv").set_index(["group", "category"])["count"]
    assert comp[("parsed_rows", "system")] == 10 and comp[("parsed_rows", "user")] == 2
    assert comp[("system_category", "security_code_changed")] == 1
    assert comp[("system_category", "member_added")] == 3            # added, "You were added", joined
    assert comp[("system_category", "settings_changed")] == 3        # group name, subject, "changed settings"
    assert comp[("system_category", "other_system_event")] == 3      # notice, created group, left
    corpus = pd.read_csv(out / "analysis_corpus.csv", keep_default_na=False)
    assert len(corpus) == 2                                          # only the two real user messages
    senders = pd.read_csv(out / "analytics_sender_counts.csv")
    assert senders["user_rows"].sum() == 2


def test_sender_less_line_pipeline_does_not_crash():
    r = rp.run_pipeline(fixture_bytes("parser_system_events.txt"), "x.txt", AppConfig())
    assert r.analytics_meta["all_reconciliation_checks_passed"]


# ------------------------------------------------------- 2. invisible Unicode marks ---
def test_invisible_marks_before_the_bracket_start_a_new_row():
    df, failures = parse("parser_unicode.txt")
    assert not failures
    assert len(df) == 13 and (df["message_type"] == "user").sum() == 12      # header + 12 user rows, none glued together
    first = df[df["message_type"] == "user"].iloc[0]
    assert first["sender"] == "Alex Demo" and pp.classify_media(first["message"]) == "image"
    marked = df[df["message"].str.contains("mark before bracket")].iloc[0]
    assert marked["sender"] == "Sam Sample" and marked["message_type"] == "user"      # U+200E U+200F before "["


def test_invisible_mark_inline_does_not_merge_rows(tmp_path):
    data = ("‎header\n[3/10/26, 9:00:00 AM] A: one\n‎[3/10/26, 9:01:00 AM] A: ‎image omitted\n"
            "[3/10/26, 9:02:00 AM] B: after\n")
    p = tmp_path / "inline.txt"
    p.write_text(data, encoding="utf-8")
    entries, _ = pp.parse_chat(p)
    assert [e["message_type"] for e in entries] == ["header", "user", "user", "user"]
    assert entries[1]["message"] == "one"                                      # not "one\n‎[3/10/26 ..."


def test_multiline_and_blank_continuation_lines_stay_one_message():
    df, _ = parse("parser_unicode.txt")
    multi = df[df["message"].str.startswith("first line")].iloc[0]
    assert multi["message"] == "first line\nsecond line\n\nafter a blank line"
    assert multi["line_end"] - multi["line_start"] == 3


def test_message_that_quotes_a_timestamp_or_starts_with_a_bracket_is_one_user_message():
    df, _ = parse("parser_unicode.txt")
    quoted = df[df["message"].str.contains("quoted timestamp")].iloc[0]
    assert quoted["message_type"] == "user" and quoted["sender"] == "Alex Demo"
    assert df[df["message"].str.startswith("[see this]")].iloc[0]["message_type"] == "user"


def test_devanagari_sender_names_and_year_rollover():
    df, _ = parse("parser_unicode.txt")
    assert "राधा नमुना" in set(df["sender"].dropna())
    out = pp.add_datetime_features(df.copy())
    assert out["datetime"].notna().sum() == 12 and out["datetime"].max().year == 2027


# ---------------------------------------------------- 3. media / deleted placeholders ---
@pytest.mark.parametrize("text,kind", [
    ("<image omitted>", "image"), ("<video omitted>", "video"), ("<Media omitted>", "media"),
    ("<unknown message>", "unknown"), ("<album message>", "album"), ("image omitted", "image"),
    ("‎image omitted", "image"), ("sticker omitted", "sticker"), ("audio omitted", "audio"),
    ("GIF omitted", "gif"), ("document omitted", "document"), ("Contact card omitted", "contact"),
    ("<attached: 00000001-PHOTO-2026-03-10.jpg>", "attachment"), ("Missed voice call", "call"),
])
def test_known_media_placeholders_are_classified(text, kind):
    assert pp.classify_media(text) == kind


def test_bracketed_placeholder_with_a_caption_is_still_media():
    assert pp.classify_media("<image omitted> look at this") == "image"
    assert pp.classify_media("caption first <video omitted>") == "video"
    assert pp.classify_media("<image omitted>\nsecond line caption") == "image"


@pytest.mark.parametrize("text", [
    "I said image omitted yesterday", "omitted", "hello", "the image was omitted from the report", "ok", "",
    "<3", "sticker", "call me", "video call tomorrow at five",
])
def test_ordinary_text_is_never_media(text):
    assert pp.classify_media(text) is None


@pytest.mark.parametrize("text,deleted", [
    ("This message was deleted", True), ("You deleted this message", True),
    ("\U0001F6AB This message was deleted", True), ("This message was deleted by admin Alex Demo", True),
    ("the file was deleted by mistake", False), ("deleted", False), ("I think this message was deleted twice", False),
])
def test_deleted_placeholders(text, deleted):
    assert pp.is_deleted_placeholder(text) is deleted


def test_media_deleted_fixture_counts_and_nlp_exclusion():
    out = outputs_for("media_deleted.txt")
    comp = pd.read_csv(out / "analytics_row_composition.csv").set_index(["group", "category"])["count"]
    assert (comp[("user_rows", "text")], comp[("user_rows", "media")], comp[("user_rows", "deleted")]) == (5, 13, 4)
    corpus = pd.read_csv(out / "analysis_corpus.csv", keep_default_na=False)
    blob = " ".join(corpus["tokens"]).lower()
    assert len(corpus) == 5
    assert "attached" not in blob and "sticker" not in blob.replace("sticker omitted today", "")   # placeholders never become words
    assert "edited" not in blob                                      # "<This message was edited>" marker is metadata
    assert "forwarded" not in blob


# ------------------------------------------------------------------- 4. tokenizer ---
@pytest.mark.parametrize("raw,expected", [
    ("रहा।", ["रहा"]), ("कल मैच है॥", ["कल", "मैच", "है"]), ("don’t", ["don't"]),
    ("“now”", ["now"]), ("wait…", ["wait"]), ("(ok)", ["ok"]), ("!!!", []),
    ("hi\U0001F600", ["hi\U0001F600"]), ("\U0001F600", ["\U0001F600"]), ("don't", ["don't"]),
    ("a-b", ["a-b"]), ("नमस्कार,", ["नमस्कार"]),
])
def test_tokenizer_normalises_unicode_punctuation(raw, expected):
    assert pp.tokenize(raw) == expected
    assert ng.analysis_tokenize(raw) == expected


def test_curly_apostrophe_stopwords_are_removed_like_plain_ones():
    assert ng.remove_stopwords(ng.analysis_tokenize("don’t go now please")) == ["go", "now", "please"]
    assert ng.analysis_tokenize("don’t go") == ng.analysis_tokenize("don't go")


def test_danda_and_plain_word_are_the_same_term_in_the_vocabulary():
    tokens = [ng.analysis_tokenize(t) for t in ("आज सराव आहे", "सराव आहे।", "आहे॥")]
    table = ng.ngram_table(tokens, 1)
    assert "आहे" in set(table["ngram"]) and not any("।" in t or "॥" in t for t in table["ngram"])
    assert int(table.set_index("ngram").loc["आहे", "count_all"]) == 3


# ------------------------------------------------- 5. typed CSV round trip (numeric terms) ---
def test_numeric_terms_survive_the_whole_pipeline_as_strings():
    r = rp.run_pipeline(fixture_bytes("numeric_terms.txt"), "x.txt", AppConfig())
    for table in ("ngram_unigrams", "tfidf_top_terms", "key_terms"):
        terms = r.tables[table]["ngram" if table == "ngram_unigrams" else "term"]
        assert terms.map(type).eq(str).all(), table
        assert {"007", "12345", "2026", "123abc", "abc123"} <= set(terms), table     # 007 never becomes 7
    comparison = r.tables["tfidf_variant_comparison"]["term"]
    assert "007" in set(comparison) and comparison.map(type).eq(str).all()


def test_words_that_pandas_treats_as_missing_stay_words():
    r = rp.run_pipeline(fixture_bytes("numeric_terms.txt"), "x.txt", AppConfig())
    terms = set(r.tables["tfidf_top_terms"]["term"])
    assert {"none", "null", "nan", "na"} <= terms and r.tables["tfidf_top_terms"]["term"].notna().all()


def test_all_numeric_vocabulary_does_not_crash(tmp_path):
    lines = ["‎header"] + [f"[3/10/26, 9:0{i}:00 AM] A: 12345 007" for i in range(5)]
    p = tmp_path / "numbers.txt"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = rp.run_pipeline(p.read_bytes(), "numbers.txt", AppConfig())
    assert set(r.tables["tfidf_top_terms"]["term"]) == {"12345", "007"}


def test_numeric_only_message_column_stays_text(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("[3/10/26, 9:00:00 AM] A: 123\n[3/10/26, 9:01:00 AM] A: 456\n", encoding="utf-8")     # no header line
    df, _ = pp.build_dataset(p)
    pp.save_processed_csv(df, tmp_path / "processed_chat.csv")
    typed = read_csv_typed(tmp_path / "processed_chat.csv")
    assert typed["clean_message"].map(type).eq(str).all()
    ng.run_analysis(tmp_path / "processed_chat.csv", tmp_path)               # used to fail on an all-numeric text column


def test_message_text_none_is_kept_as_text(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("[3/10/26, 9:00:00 AM] A: None\n[3/10/26, 9:01:00 AM] A: NA\n", encoding="utf-8")
    df, _ = pp.build_dataset(p)
    pp.save_processed_csv(df, tmp_path / "processed_chat.csv")
    typed = read_csv_typed(tmp_path / "processed_chat.csv")
    assert typed["message"].tolist() == ["None", "NA"]
    d = ca.prepare(typed)
    assert d["message"].tolist() == ["None", "NA"]


# -------------------------------------------------------------------- 6. date order ---
def test_ambiguous_date_order_is_a_prominent_warning():
    r = rp.run_pipeline(fixture_bytes("one_to_one.txt"), "x.txt", AppConfig())
    if r.info["date_order_evidence"].startswith("All month/day values"):
        assert any("date order cannot be confirmed" in w for w in r.warnings)
        assert "wrong" in r.info["date_order_evidence"]
    else:
        assert "consistent with Month/Day/Year" in r.info["date_order_evidence"]


def test_confirmed_month_day_year_has_no_date_warning():
    r = rp.run_pipeline(fixture_bytes("group_12.txt"), "x.txt", AppConfig())     # contains day values above 12
    assert "consistent with Month/Day/Year" in r.info["date_order_evidence"]
    assert not any("date order" in w for w in r.warnings)
