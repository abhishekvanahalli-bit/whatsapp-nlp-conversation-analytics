"""
Key Terms: terms ranked by how many DIFFERENT messages contain them.

    message_document_frequency(term) = number of unique messages containing term

This is a view over results the pipeline already produces, not a new NLP
algorithm (design: docs/language_and_keyword_design.md, Part B, LIMITED).

How it differs from the existing rankings
- Unigram frequency (`count_all` in ngram_unigrams) = total occurrences of the
  term, so one message repeated five times counts five times, and a word
  repeated inside one message counts every repeat.
- Key-term message coverage (`unique_texts_containing`) = number of DISTINCT
  messages that contain the term at least once. A word repeated inside one
  message counts once; identical messages count once (the unique-text variant).
  "Distinct" means distinct masked text, exactly as in the TF-IDF sensitivity
  variant (two messages that differ only by an English stopword are distinct).
- TF-IDF ranks distinctiveness (rarity is rewarded); coverage ranks breadth.

Source (reused, nothing recomputed in production):
- tfidf_top_terms.csv, variant "unique": `df` is exactly the number of unique
  texts containing the term, since TF-IDF documents are messages. Terms there
  already respect the existing decisions: forwarded marker stripped, URLs and
  phone numbers masked and excluded, English stopwords removed, no Marathi
  stopword list.
- tfidf_top_terms.csv, variant "all": messages containing the term, repeats kept.
- ngram_unigrams.csv: occurrences with and without repeats.
`run_key_terms` additionally recomputes coverage independently from the
analysis corpus and stops if it disagrees with the reused tables.

Ranking: coverage (unique messages) descending, then the term alphabetically.

Privacy: terms come from the chat and can include names. The derived
`key_terms.csv` is an INTERNAL result like the other term tables; anything
shown or downloaded must pass the display filter (`display_privacy`), which by
default hides terms occurring in only one message (`min_messages`). That
filter is a precaution, not PII detection.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from csv_io import read_csv_typed  # noqa: E402
from ngram_analysis import (  # noqa: E402  (existing, tested analysis layer)
    PLACEHOLDERS,
    PROCESSED_CSV,
    RESULTS_DIR,
    build_analysis_corpus,
    token_script,
)

COLUMNS = ["rank", "term", "script", "unique_texts_containing", "messages_containing",
           "occurrences_all", "occurrences_unique", "repetition_ratio", "tfidf_total_unique"]
OUTPUT_FILES = ("key_terms.csv", "key_terms_metadata.json")


def message_document_frequency(term_lists):
    """Counter: term -> number of messages containing it at least once.
    A term repeated inside one message still counts once."""
    counter = Counter()
    for terms in term_lists:
        counter.update(set(terms))
    return counter


def build_key_terms(tfidf_top_terms, ngram_unigrams, min_messages=1):
    """Key-terms table from the existing result tables.

    min_messages: keep terms contained in at least this many UNIQUE messages
    (1 = all terms, the internal table; the display layer uses its own filter).
    Returns the table sorted by coverage descending then term ascending."""
    if tfidf_top_terms.empty:
        return pd.DataFrame(columns=COLUMNS)
    uniq = tfidf_top_terms[tfidf_top_terms["variant"] == "unique"][["term", "df", "total_tfidf"]]
    uniq = uniq.rename(columns={"df": "unique_texts_containing", "total_tfidf": "tfidf_total_unique"})
    allv = tfidf_top_terms[tfidf_top_terms["variant"] == "all"][["term", "df"]].rename(
        columns={"df": "messages_containing"})
    counts = ngram_unigrams[["ngram", "count_all", "count_unique"]].rename(
        columns={"ngram": "term", "count_all": "occurrences_all", "count_unique": "occurrences_unique"})
    table = uniq.merge(allv, on="term", how="left").merge(counts, on="term", how="left")
    # placeholders can never be key terms (TF-IDF already excludes them; this is a guard)
    table = table[~table["term"].isin(PLACEHOLDERS)]
    table = table[table["unique_texts_containing"] >= min_messages]
    table["script"] = table["term"].map(token_script)
    table["repetition_ratio"] = (table["occurrences_all"] / table["occurrences_unique"]).round(2)
    table = table.sort_values(["unique_texts_containing", "term"], ascending=[False, True]).reset_index(drop=True)
    table.insert(0, "rank", range(1, len(table) + 1))
    for column in ("unique_texts_containing", "messages_containing", "occurrences_all", "occurrences_unique"):
        table[column] = table[column].astype("Int64")
    return table[COLUMNS]


def coverage_from_corpus(corpus):
    """Independent recomputation of coverage from the analysis corpus, used to
    validate the reused tables: (all-messages Counter, unique-texts Counter)."""
    term_lists = [[w for w in tokens if w not in PLACEHOLDERS] for tokens in corpus["tokens_no_stopwords"]]
    # "unique message" = first copy of each distinct MASKED TEXT (the pipeline's is_repeat definition,
    # applied before stopword removal), exactly as in the TF-IDF sensitivity variant
    unique = [terms for terms, repeat in zip(term_lists, corpus["is_repeat"]) if not repeat]
    return message_document_frequency(term_lists), message_document_frequency(unique)


def run_key_terms(processed_csv=PROCESSED_CSV, results_dir=RESULTS_DIR, tables_dir=None):
    """Build key_terms.csv (+ metadata) from the existing tfidf_top_terms.csv and
    ngram_unigrams.csv in `tables_dir` (default results_dir). Existing files are
    only read. Raises AssertionError, writing nothing, if coverage from the
    reused tables disagrees with an independent recomputation."""
    src = Path(tables_dir if tables_dir is not None else results_dir)
    for name in ("tfidf_top_terms.csv", "ngram_unigrams.csv"):
        if not (src / name).exists():
            raise FileNotFoundError(f"{name} not found in {src}; run the n-gram and TF-IDF analyses first")
    tfidf = read_csv_typed(src / "tfidf_top_terms.csv")
    unigrams = read_csv_typed(src / "ngram_unigrams.csv")
    table = build_key_terms(tfidf, unigrams)

    corpus = build_analysis_corpus(read_csv_typed(processed_csv))
    cov_all, cov_unique = coverage_from_corpus(corpus)
    mismatches = [t for t, u, a in zip(table["term"], table["unique_texts_containing"], table["messages_containing"])
                  if cov_unique.get(t, 0) != u or cov_all.get(t, 0) != a]
    checks = [
        {"check": "coverage (unique texts) matches independent recomputation", "mismatched_terms": len(mismatches),
         "passed": not mismatches},
        {"check": "every term occurs at least as often as it is contained", "mismatched_terms": int(
            (table["occurrences_all"] < table["messages_containing"]).sum()),
         "passed": bool((table["occurrences_all"] >= table["messages_containing"]).all())},
        {"check": "no placeholder terms", "mismatched_terms": int(table["term"].isin(PLACEHOLDERS).sum()),
         "passed": not table["term"].isin(PLACEHOLDERS).any()},
        {"check": "term count equals unique-variant vocabulary",
         "mismatched_terms": int(len(table) != int((tfidf["variant"] == "unique").sum())),
         "passed": len(table) == int((tfidf["variant"] == "unique").sum())},
    ]
    if not all(c["passed"] for c in checks):
        raise AssertionError(f"key terms validation failed: {checks}")

    metadata = {
        "design": "docs/language_and_keyword_design.md",
        "metric": "unique_texts_containing = number of unique messages containing the term",
        "ranking": "unique_texts_containing descending, then term ascending",
        "differs_from": {"unigram_frequency": "total occurrences (repeats and in-message repeats counted)",
                         "tfidf": "distinctiveness (rarity rewarded)"},
        "sources": ["tfidf_top_terms.csv", "ngram_unigrams.csv"],
        "n_terms": int(len(table)),
        "n_unique_messages": int(corpus["is_repeat"].eq(False).sum()),
        "n_messages": int(len(corpus)),
        "privacy": "INTERNAL table; terms can include names. Apply the display filter before display/download",
        "checks": checks,
    }
    out = Path(results_dir)
    table.to_csv(out / "key_terms.csv", index=False, encoding="utf-8")
    (out / "key_terms_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return table, metadata


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    table, meta = run_key_terms()
    print(table.head(15).to_string(index=False))
    print("terms:", meta["n_terms"], "checks passed:", all(c["passed"] for c in meta["checks"]))
