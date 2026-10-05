import re
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import ngram_analysis as ng  # noqa: E402
from helpers import SAMPLE_CSV  # noqa: E402


def test_generate_ngrams_basic():
    t = ["a", "b", "c", "d"]
    assert ng.generate_ngrams(t, 1) == [("a",), ("b",), ("c",), ("d",)]
    assert ng.generate_ngrams(t, 2) == [("a", "b"), ("b", "c"), ("c", "d")]
    assert ng.generate_ngrams(t, 3) == [("a", "b", "c"), ("b", "c", "d")]
    assert ng.generate_ngrams(t, 4) == [("a", "b", "c", "d")]


def test_generate_ngrams_short_and_invalid():
    assert ng.generate_ngrams(["a"], 2) == []
    assert ng.generate_ngrams([], 1) == []
    with pytest.raises(ValueError):
        ng.generate_ngrams(["a"], 0)


def test_count_formula_len_minus_n_plus_1():
    t = list("abcdefg")
    for n in (1, 2, 3):
        assert len(ng.generate_ngrams(t, n)) == len(t) - n + 1


def test_no_cross_message_ngrams():
    c = ng.ngram_frequencies([["a", "b"], ["c", "d"]], 2)
    assert ("b", "c") not in c
    assert c == {("a", "b"): 1, ("c", "d"): 1}


def test_repeated_ngram_in_one_message_counts_twice_but_one_doc():
    msgs = [["go", "go", "go"]]
    assert ng.ngram_frequencies(msgs, 2)[("go", "go")] == 2
    assert ng.document_frequencies(msgs, 2)[("go", "go")] == 1


def test_all_vs_unique_counts():
    msgs = [["share", "photo"]] * 3 + [["share", "size"]]
    t = ng.ngram_table(msgs, 2).set_index("ngram")
    assert t.loc["share photo", "count_all"] == 3
    assert t.loc["share photo", "count_unique"] == 1
    assert t.loc["share photo", "repetition_ratio"] == 3.0
    assert t.loc["share size", "count_all"] == t.loc["share size", "count_unique"] == 1


def test_table_sorted_and_deterministic():
    t = ng.ngram_table([["b"], ["a"], ["a"]], 1)
    assert list(t["ngram"]) == ["a", "b"]


def test_url_and_phone_masking():
    toks = ng.analysis_tokenize("join https://chat.whatsapp.com/abc?x=1&y=2 now")
    assert toks == ["join", "<URL>", "now"]
    toks = ng.analysis_tokenize("call +91 12345 67890 today")
    assert toks == ["call", "<PHONE>", "today"]
    assert "1234" not in " ".join(toks)


def test_forwarded_marker_removed_from_text():
    assert ng.analysis_tokenize("[forwarded] jane doe") == ["jane", "doe"]
    assert ng.analysis_tokenize("[Forwarded] Jane") == ["Jane"]  # case-insensitive
    assert ng.analysis_tokenize("  [forwarded]   hello") == ["hello"]


def test_forwarded_marker_only_removed_at_start_and_only_once():
    assert ng.analysis_tokenize("see [forwarded] note") == ["see", "forwarded", "note"]  # mid-text: real language, brackets stripped as punctuation
    assert ng.analysis_tokenize("[forwarded] [forwarded] x") == ["forwarded", "x"]  # only the first marker is metadata
    assert ng.analysis_tokenize("forwarded message") == ["forwarded", "message"]  # plain word kept


def test_forwarded_marker_with_url_still_masked():
    assert ng.analysis_tokenize("[forwarded] https://chat.whatsapp.com/x") == ["<URL>"]


def test_marker_only_message_gives_no_tokens():
    assert ng.analysis_tokenize("[forwarded]") == []


def test_forwarded_flag_preserved_in_corpus():
    import pandas as pd
    df = pd.DataFrame({
        "line_start": [1, 2], "sender": ["a", "a"], "message_type": ["user", "user"],
        "is_media": [False, False], "is_deleted": [False, False],
        "is_forwarded": [True, False],
        "clean_message": ["[forwarded] hello there", "hello there"],
    })
    c = ng.build_analysis_corpus(df)
    assert list(c["is_forwarded"]) == [True, False]
    assert list(c["text_masked"]) == ["hello there", "hello there"]
    assert list(c["is_repeat"]) == [False, True]  # repeats are flagged, not dropped
    assert len(c) == 2


def test_placeholders_survive_stopword_removal():
    assert ng.remove_stopwords(["open", "this", "<URL>"]) == ["open", "<URL>"]


def test_anonymize_senders_stable():
    assert ng.anonymize_senders(["+91 1", "bob", "+91 1"]) == ["Sender_1", "Sender_2", "Sender_1"]


def test_token_script():
    assert ng.token_script("खेळाडू") == "devanagari"
    assert ng.token_script("team") == "latin"
    assert ng.token_script("<URL>") == "placeholder"
    assert ng.token_script("2026") == "other"


def test_sample_dataset_end_to_end(tmp_path):
    csv = SAMPLE_CSV                                  # fictional 12-participant group fixture
    before = csv.read_bytes()
    corpus, tables, diag = ng.run_analysis(csv, tmp_path)
    assert csv.read_bytes() == before                 # source untouched
    assert len(corpus) == 143
    blob = "".join(p.read_text(encoding="utf-8") for p in tmp_path.glob("*.csv"))
    # identifiers are derived from the raw data at test time (never hard-coded in the repository)
    raw = pd.read_csv(csv)
    phones = {m for t in raw["message"].astype(str) for m in re.findall(r"\+\d[\d ]{7,}\d", t)}
    phones |= {s for s in raw["sender"].dropna() if s.startswith("+")}
    groups = {g for p in phones for g in p.split()[1:] if len(g) >= 4}
    assert groups and "+91" not in blob
    assert not any(re.search(r"(?<![\d.])" + g + r"(?!\d)", blob) for g in groups), "phone number group leaked"
    assert "chat.whatsapp.com" not in blob
    # forwarded marker is metadata: forwarded text rows kept, no 'forwarded' vocabulary
    assert corpus["is_forwarded"].sum() == int(
        (raw["is_forwarded"] & (raw["message_type"] == "user") & ~raw["is_media"] & ~raw["is_deleted"]).sum()) > 0
    assert not any("forwarded" in t for t in tables["unigrams_with_stopwords"]["ngram"])
    assert not any("forwarded" in t for t in tables["bigrams"]["ngram"])
    assert (corpus["tokens"].apply(len) > 0).all()
    for t in tables.values():
        assert (t["count_all"] >= t["count_unique"]).all()
