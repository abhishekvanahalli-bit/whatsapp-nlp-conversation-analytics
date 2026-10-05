import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import display_privacy as dp  # noqa: E402
import key_terms as kt  # noqa: E402
import ngram_analysis as ng  # noqa: E402
import preprocessor as pp  # noqa: E402
import tfidf_analysis as tf  # noqa: E402
from helpers import SAMPLE_CHAT, SAMPLE_CSV, SAMPLE_DIR, corpus_counts  # noqa: E402
from test_dashboard_core import FORBIDDEN, SENSITIVE_CHAT, chat  # noqa: E402

needs_data = pytest.mark.skipif(not SAMPLE_CSV.exists(), reason="synthetic sample outputs missing")


def run_chain(tmp_path, data, name="run"):
    """Run the real pipeline modules on a chat in a temp dir; returns (dir, key_terms table, metadata)."""
    d = tmp_path / name
    d.mkdir()
    (d / "chat.txt").write_bytes(data)
    df, _ = pp.build_dataset(d / "chat.txt")
    processed = d / "processed_chat.csv"
    pp.save_processed_csv(df, processed)
    ng.run_analysis(processed, d)
    tf.run_tfidf(processed, d, d)
    table, meta = kt.run_key_terms(processed, d)
    return d, table, meta


def by_term(table):
    return table.set_index("term")


CHAT = chat(
    ("3/10/25, 9:00:00 AM", "Ann", "alpha beta beta beta"),                  # beta x3 in ONE message
    ("3/10/25, 9:01:00 AM", "Bob", "alpha gamma"),
    ("3/11/25, 9:00:00 AM", "Ann", "alpha gamma"),                           # exact repeat of the line above
    ("3/11/25, 9:01:00 AM", "Bob", "delta once"),
    ("3/12/25, 9:00:00 AM", "Ann", "the and of alpha"),                      # only alpha is not a stopword
    ("3/12/25, 9:01:00 AM", "Bob", "visit https://x.example.org/a call +1 555 010 0199 now"),
)


# ------------------------------------------------ message document frequency ---
def test_term_in_one_message_once():
    assert kt.message_document_frequency([["a", "b"], ["c"]]) == {"a": 1, "b": 1, "c": 1}


def test_repeated_occurrences_inside_one_message_count_once():
    cov = kt.message_document_frequency([["x", "x", "x", "y"], ["y"]])
    assert cov["x"] == 1 and cov["y"] == 2


def test_term_once_across_multiple_messages():
    cov = kt.message_document_frequency([["z"], ["z", "a"], ["b", "z"]])
    assert cov["z"] == 3 and cov["a"] == 1


def test_empty_corpus_and_empty_messages():
    assert kt.message_document_frequency([]) == {}
    assert kt.message_document_frequency([[], []]) == {}


def test_unique_variant_collapses_identical_masked_texts_only():
    term_lists = [["a", "b"], ["a", "b"], ["a", "c"]]
    corpus = pd.DataFrame({"tokens_no_stopwords": term_lists, "is_repeat": [False, True, False]})
    cov_all, cov_unique = kt.coverage_from_corpus(corpus)
    assert cov_all["a"] == 3 and cov_unique["a"] == 2                               # the repeat counts only in 'all'
    assert cov_all["b"] == 2 and cov_unique["b"] == 1 and cov_unique["c"] == 1


def test_messages_differing_only_by_a_stopword_are_distinct_unique_messages():
    # identical after stopword removal, but different masked texts: both are "unique messages"
    corpus = pd.DataFrame({"tokens_no_stopwords": [["alpha"], ["alpha"]], "is_repeat": [False, False]})
    assert kt.coverage_from_corpus(corpus)[1]["alpha"] == 2


def test_coverage_from_corpus_excludes_placeholders():
    corpus = pd.DataFrame({"tokens_no_stopwords": [["<URL>", "a"], ["<PHONE>", "a"]], "is_repeat": [False, False]})
    cov_all, _ = kt.coverage_from_corpus(corpus)
    assert set(cov_all) == {"a"}


# --------------------------------------------------------- table from results ---
def test_pipeline_table_on_known_chat(tmp_path):
    _, table, meta = run_chain(tmp_path, CHAT)
    t = by_term(table)
    # alpha is in messages 1, 2, 3, 5 (4 messages); 2 and 3 are identical so 3 unique texts contain it
    assert (t.loc["alpha", "messages_containing"], t.loc["alpha", "unique_texts_containing"]) == (4, 3)
    assert t.loc["alpha", "occurrences_all"] == 4
    # beta occurs three times in a single message: frequency 3, coverage 1
    assert (t.loc["beta", "occurrences_all"], t.loc["beta", "messages_containing"], t.loc["beta", "unique_texts_containing"]) == (3, 1, 1)
    # gamma is in two identical messages: all-message coverage 2, unique-text coverage 1
    assert (t.loc["gamma", "messages_containing"], t.loc["gamma", "unique_texts_containing"]) == (2, 1)
    assert t.loc["gamma", "occurrences_all"] == 2 and t.loc["gamma", "occurrences_unique"] == 1
    assert t.loc["delta", "unique_texts_containing"] == 1
    assert all(c["passed"] for c in meta["checks"])


def test_frequency_and_coverage_rank_differently(tmp_path):
    _, table, _ = run_chain(tmp_path, CHAT)
    t = by_term(table)
    by_frequency = t.sort_values(["occurrences_all"], ascending=False, kind="stable").index[:2].tolist()
    assert table.iloc[0]["term"] == "alpha"                                           # widest coverage
    assert t.loc["beta", "occurrences_all"] == 3 > t.loc["gamma", "occurrences_all"] == 2
    assert t.loc["beta", "unique_texts_containing"] == 1 == t.loc["gamma", "unique_texts_containing"]
    assert by_frequency[0] in ("alpha", "beta")                                        # frequency alone would not separate them


def test_deterministic_ranking_ties_are_alphabetical(tmp_path):
    _, table, _ = run_chain(tmp_path, CHAT)
    tied = table[table["unique_texts_containing"] == 1]["term"].tolist()
    assert tied == sorted(tied)
    assert table["rank"].tolist() == list(range(1, len(table) + 1))
    cov = table["unique_texts_containing"].tolist()
    assert cov == sorted(cov, reverse=True)


def test_repeat_runs_are_byte_identical(tmp_path):
    a, _, _ = run_chain(tmp_path, CHAT, "a")
    b, _, _ = run_chain(tmp_path, CHAT, "b")
    for name in kt.OUTPUT_FILES:
        assert (a / name).read_bytes() == (b / name).read_bytes(), name


def test_english_stopwords_are_excluded_and_no_marathi_list_is_used(tmp_path):
    dev = "सर्व"
    data = chat(("3/10/25, 9:00:00 AM", "Ann", f"the and of alpha {dev}"), ("3/10/25, 9:01:00 AM", "Bob", f"alpha {dev}"))
    _, table, _ = run_chain(tmp_path, data)
    terms = set(table["term"])
    assert not terms & {"the", "and", "of"}
    assert {"alpha", dev} <= terms                                                     # Devanagari terms are kept


def test_urls_phones_and_placeholders_never_become_key_terms(tmp_path):
    _, table, _ = run_chain(tmp_path, CHAT)
    terms = set(table["term"])
    assert not terms & set(ng.PLACEHOLDERS) and not any(t.startswith(("http", "www")) for t in terms)
    assert not any(any(ch.isdigit() for ch in t) and len(t) >= 7 for t in terms)
    assert {"visit", "call", "now"} <= terms                                           # the words around them remain
    assert "x.example.org" not in " ".join(terms)


def test_forwarded_marker_is_not_a_term(tmp_path):
    data = chat(("3/10/25, 9:00:00 AM", "Ann", "[Forwarded] workshop schedule"), ("3/10/25, 9:01:00 AM", "Bob", "workshop time"))
    _, table, _ = run_chain(tmp_path, data)
    assert "forwarded" not in set(table["term"]) and by_term(table).loc["workshop", "unique_texts_containing"] == 2


def test_min_messages_filter_hides_single_message_terms(tmp_path):
    d, table, _ = run_chain(tmp_path, CHAT)
    filtered = kt.build_key_terms(pd.read_csv(d / "tfidf_top_terms.csv"), pd.read_csv(d / "ngram_unigrams.csv"), min_messages=2)
    assert set(filtered["term"]) == {"alpha"}
    assert len(table) > len(filtered)


def test_empty_corpus_gives_empty_schema_table(tmp_path):
    _, table, meta = run_chain(tmp_path, chat(("3/10/25, 9:00:00 AM", "Ann", "<image omitted>")))
    assert table.empty and list(table.columns) == kt.COLUMNS and meta["n_terms"] == 0
    assert kt.build_key_terms(pd.DataFrame(), pd.DataFrame()).empty


def test_validation_fails_loudly_if_reused_tables_disagree(tmp_path):
    d, _, _ = run_chain(tmp_path, CHAT)
    tfidf = pd.read_csv(d / "tfidf_top_terms.csv")
    tfidf.loc[(tfidf["variant"] == "unique") & (tfidf["term"] == "alpha"), "df"] += 1      # corrupt one value
    tampered = tmp_path / "tampered"
    tampered.mkdir()
    tfidf.to_csv(tampered / "tfidf_top_terms.csv", index=False)
    (tampered / "ngram_unigrams.csv").write_bytes((d / "ngram_unigrams.csv").read_bytes())
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(AssertionError):
        kt.run_key_terms(d / "processed_chat.csv", out, tampered)
    assert list(out.iterdir()) == []


def test_missing_source_tables_raise_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        kt.run_key_terms(SAMPLE_CSV, tmp_path, tmp_path)


# ------------------------------------------------------------------ privacy ---
def test_internal_table_has_no_identifiers_and_display_filter_hides_rare_terms(tmp_path):
    d, table, _ = run_chain(tmp_path, SENSITIVE_CHAT)
    internal = ((d / "key_terms.csv").read_text(encoding="utf-8") + (d / "key_terms_metadata.json").read_text(encoding="utf-8")).lower()
    # phone numbers, URLs and sender identifiers are masked before any term is formed
    for value in ("+1 555 010 0142", "555 010 0142", "5550100142", "5550100999", "secret.example.org", "xyz123secret",
                  "other456", "https://", "http", "www."):
        assert value not in internal, value
    # the INTERNAL table keeps single-message terms (names typed in message text can be among them)
    assert {"zephyrine", "quillfeather's"} <= set(table["term"])
    shown, _ = dp.prepare_display_tables({"tfidf_top_terms": pd.read_csv(d / "tfidf_top_terms.csv"),
                                          "ngram_unigrams": pd.read_csv(d / "ngram_unigrams.csv")}, 2, False)
    display = kt.build_key_terms(shown["tfidf_top_terms"], shown["ngram_unigrams"])
    shown_blob = display.to_csv(index=False).lower()
    for value in FORBIDDEN:                                                        # every sensitive value, incl. rare terms
        assert value.lower() not in shown_blob, value
    assert "meeting" in set(display["term"])                                       # terms in several messages remain


# --------------------------------------------------------------- real data ---
@needs_data
def test_real_data_coverage_matches_independent_recomputation(tmp_path):
    table, meta = kt.run_key_terms(SAMPLE_CSV, tmp_path, SAMPLE_DIR)
    n_all, n_unique, _ = corpus_counts()
    assert meta["n_messages"] == n_all and meta["n_unique_messages"] == n_unique
    assert all(c["passed"] for c in meta["checks"])
    assert len(table) == int((pd.read_csv(SAMPLE_DIR / "tfidf_top_terms.csv")["variant"] == "unique").sum())
    assert table["unique_texts_containing"].max() <= n_unique and table["messages_containing"].max() <= n_all
    assert (table["messages_containing"] >= table["unique_texts_containing"]).all()
    assert not set(table["term"]) & set(ng.PLACEHOLDERS)


@needs_data
def test_real_data_ranking_differs_from_unigram_frequency(tmp_path):
    table, _ = kt.run_key_terms(SAMPLE_CSV, tmp_path, SAMPLE_DIR)
    freq = pd.read_csv(SAMPLE_DIR / "ngram_unigrams.csv")
    freq = freq[freq["ngram"].isin(table["term"])].sort_values(["count_all", "ngram"], ascending=[False, True])
    assert table["term"].head(15).tolist() != freq["ngram"].head(15).tolist()
    repeated_inside = table[table["occurrences_unique"] > table["unique_texts_containing"]]
    assert not repeated_inside.empty                                        # some term repeats within a message: counted once


@needs_data
def test_real_data_run_leaves_existing_files_untouched(tmp_path):
    protected = [p for p in SAMPLE_DIR.iterdir() if p.is_file()] + [SAMPLE_CHAT]
    before = {p: p.read_bytes() for p in protected}
    kt.run_key_terms(SAMPLE_CSV, tmp_path, SAMPLE_DIR)
    assert all(p.read_bytes() == c for p, c in before.items())
