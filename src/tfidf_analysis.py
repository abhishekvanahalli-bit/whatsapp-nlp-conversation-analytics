"""
Day 2, Milestone 2: TF-IDF over the analysis corpus (design: docs/tfidf_design.md).

What is measured: terms that are DISTINCTIVE within this small corpus. A high
score does not mean a word is important in general.

Design (see docs/tfidf_design.md):
- Document = one message. Preprocessing is NOT re-implemented: documents come
  from ngram_analysis.build_analysis_corpus() (forwarded-marker removal,
  phone/URL masking, English stopwords via `tokens_no_stopwords`).
- Vocabulary = unigrams; the <URL> and <PHONE> placeholders are excluded from the
  ranked terms and kept only as per-message flags (has_url, has_phone).
- Two variants:
    "all"    PRIMARY     all conversational messages, repeats kept
    "unique" SENSITIVITY exact duplicate texts collapsed to one copy
- N = total number of documents in the selected corpus. A document with no
  retained terms ("empty") stays in N but contributes no tf and no df.
- Formula (smoothed IDF, L2 row normalisation):
      tf(t,d)    = raw count of t in d
      df(t)      = number of documents containing t
      idf(t)     = ln((1 + N) / (1 + df(t))) + 1
      tfidf(t,d) = tf * idf, then divided by the L2 norm of d's vector
  L2 normalisation is applied only to non-empty documents.
- scikit-learn is used ONLY as an independent reference in tests/metadata,
  never for the production numbers.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from csv_io import read_csv_typed  # noqa: E402
from ngram_analysis import (  # noqa: E402  (existing, tested preprocessing layer)
    PHONE_TOKEN,
    PLACEHOLDERS,
    PROCESSED_CSV,
    RESULTS_DIR,
    URL_TOKEN,
    build_analysis_corpus,
    token_script,
)

VARIANTS = ("all", "unique")  # "all" is primary, "unique" is sensitivity
TOP_K = 10                    # size of the top-term lists in stability diagnostics
LOO_FULL_MAX_DOCS = 200       # up to this many documents: full leave-one-out (every document left out once)
LOO_SAMPLE_RUNS = 60          # above it: leave out this many evenly spaced documents (deterministic)
_ROUND = 12                   # scores rounded before ranking, so float noise cannot reorder ties


# --------------------------------------------------------------- documents ---
def build_documents(corpus):
    """One row per conversational message with its retained term list.

    terms = English-stopword-filtered tokens minus placeholders (no new
    preprocessing). has_url / has_phone record that a placeholder occurred.
    """
    docs = pd.DataFrame({
        "line_start": corpus["line_start"].values,
        "sender_anon": corpus["sender_anon"].values,
        "is_forwarded": corpus["is_forwarded"].values,
        "is_repeat": corpus["is_repeat"].values,
        "has_url": [URL_TOKEN in t for t in corpus["tokens"]],
        "has_phone": [PHONE_TOKEN in t for t in corpus["tokens"]],
        "terms": [[w for w in t if w not in PLACEHOLDERS] for t in corpus["tokens_no_stopwords"]],
    })
    docs["n_terms"] = docs["terms"].apply(len)
    return docs.reset_index(drop=True)


def select_variant(docs, variant):
    """'all' keeps every message (primary). 'unique' keeps the first copy of each
    distinct text only (sensitivity); `is_repeat` marks later copies."""
    if variant == "all":
        return docs.reset_index(drop=True)
    if variant == "unique":
        return docs.loc[~docs["is_repeat"]].reset_index(drop=True)
    raise ValueError(f"unknown variant: {variant!r}")


# ------------------------------------------------------------- TF-IDF core ---
def compute_tfidf(term_lists):
    """Explicit TF-IDF with numpy. Returns a dict:
    vocab (sorted list), tf, raw, norm (docs x vocab arrays), df, idf, n_docs,
    empty_mask. N counts EVERY document, including empty ones."""
    term_lists = [list(t) for t in term_lists]
    n_docs = len(term_lists)
    vocab = sorted({w for terms in term_lists for w in terms})
    index = {w: i for i, w in enumerate(vocab)}
    tf = np.zeros((n_docs, len(vocab)), dtype=float)
    for d, terms in enumerate(term_lists):
        for w in terms:
            tf[d, index[w]] += 1.0
    df = (tf > 0).sum(axis=0).astype(float)                # empty docs add nothing
    idf = np.log((1.0 + n_docs) / (1.0 + df)) + 1.0
    raw = tf * idf
    norms = np.sqrt((raw ** 2).sum(axis=1))
    empty_mask = norms == 0
    safe = np.where(empty_mask, 1.0, norms)                # avoid 0/0; empty rows stay all-zero
    norm = raw / safe[:, None]
    return {"vocab": vocab, "tf": tf, "raw": raw, "norm": norm, "df": df,
            "idf": idf, "n_docs": n_docs, "empty_mask": empty_mask}


def long_table(docs, res, variant):
    """One row per message x term with tf > 0 (empty documents have no rows)."""
    rows = []
    vocab = res["vocab"]
    for d in range(res["n_docs"]):
        for j in np.nonzero(res["tf"][d])[0]:
            rows.append({
                "variant": variant,
                "line_start": docs.at[d, "line_start"],
                "sender_anon": docs.at[d, "sender_anon"],
                "is_forwarded": docs.at[d, "is_forwarded"],
                "is_repeat": docs.at[d, "is_repeat"],
                "has_url": docs.at[d, "has_url"],
                "has_phone": docs.at[d, "has_phone"],
                "term": vocab[j],
                "script": token_script(vocab[j]),
                "tf": int(res["tf"][d, j]),
                "df": int(res["df"][j]),
                "idf": res["idf"][j],
                "tfidf_raw": res["raw"][d, j],
                "tfidf_norm": res["norm"][d, j],
            })
    cols = ["variant", "line_start", "sender_anon", "is_forwarded", "is_repeat", "has_url",
            "has_phone", "term", "script", "tf", "df", "idf", "tfidf_raw", "tfidf_norm"]
    out = pd.DataFrame(rows, columns=cols)
    if out.empty:
        out["rank_in_message"] = pd.Series(dtype=int)
        return out
    out["_score"] = out["tfidf_norm"].round(_ROUND)
    out = out.sort_values(["line_start", "_score", "term"], ascending=[True, False, True])
    out["rank_in_message"] = out.groupby("line_start").cumcount() + 1
    return out.drop(columns="_score").reset_index(drop=True)


def top_terms_table(long_df, variant):
    """Aggregate across messages. total_tfidf = sum of tfidf_norm over messages
    (favours frequent terms); mean_tfidf_in_docs = mean over only the messages
    containing the term (favours rare terms). n_docs_top3 = messages in which
    the term is in that message's top 3."""
    cols = ["variant", "term", "script", "df", "idf", "total_tfidf",
            "mean_tfidf_in_docs", "n_docs_top3"]
    if long_df.empty:
        return pd.DataFrame(columns=cols)
    g = long_df.groupby("term")
    out = pd.DataFrame({
        "script": g["script"].first(),
        "df": g["df"].first(),
        "idf": g["idf"].first(),
        "total_tfidf": g["tfidf_norm"].sum(),
        "mean_tfidf_in_docs": g["tfidf_norm"].mean(),
        "n_docs_top3": g["rank_in_message"].apply(lambda r: int((r <= 3).sum())),
    }).reset_index()
    out.insert(0, "variant", variant)
    out["_s"] = out["total_tfidf"].round(_ROUND)
    out = out.sort_values(["_s", "term"], ascending=[False, True]).drop(columns="_s")
    return out[cols].reset_index(drop=True)


def variant_comparison(top_all, top_unique, ngram_unigrams=None):
    """Rank of each term under the primary (all) and sensitivity (unique)
    variant. Rank 1 = highest total_tfidf; ties share the lowest rank.
    rank_change = rank_unique - rank_all (positive: term ranks lower when
    repeats are collapsed). count_all / count_unique come from the existing
    n-gram unigram table when supplied."""
    a = top_all[["term", "total_tfidf"]].copy()
    u = top_unique[["term", "total_tfidf"]].copy()
    a["rank_all"] = a["total_tfidf"].round(_ROUND).rank(ascending=False, method="min").astype(int)
    u["rank_unique"] = u["total_tfidf"].round(_ROUND).rank(ascending=False, method="min").astype(int)
    m = a.merge(u, on="term", how="outer", suffixes=("_all", "_unique"))
    m["rank_change"] = m["rank_unique"] - m["rank_all"]
    if ngram_unigrams is not None:
        m = m.merge(ngram_unigrams[["ngram", "count_all", "count_unique"]]
                    .rename(columns={"ngram": "term"}), on="term", how="left")
    m["_r"] = m["rank_all"].fillna(m["rank_all"].max() + 1 if m["rank_all"].notna().any() else 1)
    m = m.sort_values(["_r", "term"]).drop(columns="_r").reset_index(drop=True)
    return m


# -------------------------------------------------- stability diagnostics ---
def top_term_list(term_lists, k=TOP_K):
    """Top-k terms by total L2-normalised TF-IDF (ties broken alphabetically)."""
    res = compute_tfidf(term_lists)
    if not res["vocab"]:
        return []
    total = res["norm"].sum(axis=0).round(_ROUND)
    order = sorted(range(len(res["vocab"])), key=lambda j: (-total[j], res["vocab"][j]))
    return [res["vocab"][j] for j in order[:k]]


def stability_indices(n_docs, full_max=LOO_FULL_MAX_DOCS, sample_runs=LOO_SAMPLE_RUNS):
    """Which documents to leave out. Small corpora: every document ("full_leave_one_out").
    Larger corpora: `sample_runs` evenly spaced documents ("sampled_leave_one_out"); the cost of the full
    diagnostic grows roughly with N squared. Deterministic: no randomness is used."""
    if n_docs <= full_max:
        return list(range(n_docs)), "full_leave_one_out"
    picks = sorted({int(round(x)) for x in np.linspace(0, n_docs - 1, sample_runs)})
    return picks, "sampled_leave_one_out"


def leave_one_out_stability(term_lists, k=TOP_K, full_max=LOO_FULL_MAX_DOCS, sample_runs=LOO_SAMPLE_RUNS):
    """Recompute the top-k with a document left out (N-1 documents; IDF is
    recomputed). Overlap = |top-k full ∩ top-k without doc| / k. Low values mean
    the ranking depends heavily on single messages. Every document is left out once for
    small corpora; larger corpora use evenly spaced documents (mode recorded in the result).
    This diagnostic never affects the TF-IDF scores themselves."""
    term_lists = [list(t) for t in term_lists]
    indices, mode = stability_indices(len(term_lists), full_max, sample_runs)
    full = top_term_list(term_lists, k)
    overlaps = []
    for i in indices:
        rest = term_lists[:i] + term_lists[i + 1:]
        without = top_term_list(rest, k)
        overlaps.append(len(set(full) & set(without)) / k)
    if not overlaps:
        return {"k": k, "mode": mode, "n_documents": len(term_lists), "n_runs": 0, "mean_overlap": None,
                "min_overlap": None, "argmin_doc_index": None}
    arr = np.array(overlaps)
    return {"k": k, "mode": mode, "n_documents": len(term_lists), "n_runs": len(overlaps),
            "mean_overlap": round(float(arr.mean()), 4), "min_overlap": round(float(arr.min()), 4),
            "argmin_doc_index": int(indices[int(arr.argmin())])}


# ------------------------------------------------- scikit-learn reference ---
def sklearn_reference(term_lists):
    """Independent TF-IDF via TfidfVectorizer (identity analyzer, smooth idf,
    L2). Returns (vocab list, dense matrix) or None if scikit-learn is not
    installed. Reference only; never used for production output."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError:
        return None
    vec = TfidfVectorizer(analyzer=lambda x: x, smooth_idf=True, norm="l2", sublinear_tf=False)
    matrix = vec.fit_transform([list(t) for t in term_lists])
    return list(vec.get_feature_names_out()), matrix.toarray(), vec.idf_


def sklearn_max_abs_diff(term_lists, res):
    """Largest |difference| between our normalised matrix / idf and sklearn's.
    None if scikit-learn is unavailable or the vocabulary is empty."""
    if not res["vocab"]:
        return None
    ref = sklearn_reference(term_lists)
    if ref is None:
        return None
    vocab, matrix, idf = ref
    assert vocab == res["vocab"], "vocabulary mismatch with reference"
    return float(max(np.abs(matrix - res["norm"]).max(), np.abs(idf - res["idf"]).max()))


# ------------------------------------------------------------------ driver ---
def _library_versions():
    versions = {"numpy": np.__version__, "pandas": pd.__version__}
    try:
        import sklearn
        versions["scikit-learn (reference only)"] = sklearn.__version__
    except ImportError:
        versions["scikit-learn (reference only)"] = "not installed"
    return versions


def run_tfidf(processed_csv=PROCESSED_CSV, results_dir=RESULTS_DIR, ngram_dir=RESULTS_DIR):
    """Compute both variants and write the four approved outputs to results_dir.
    Existing files (processed_chat.csv, n-gram outputs) are only read."""
    df = read_csv_typed(processed_csv)
    docs = build_documents(build_analysis_corpus(df))

    longs, tops, meta_variants, results = [], {}, {}, {}
    for variant in VARIANTS:
        sel = select_variant(docs, variant)
        terms = sel["terms"].tolist()
        res = compute_tfidf(terms)
        long_df = long_table(sel, res, variant)
        top = top_terms_table(long_df, variant)
        longs.append(long_df)
        tops[variant] = top
        results[variant] = (sel, res)
        empty_lines = [int(x) for x in sel.loc[res["empty_mask"], "line_start"]]
        meta_variants[variant] = {
            "role": "primary" if variant == "all" else "sensitivity",
            "n_documents_N": res["n_docs"],
            "n_empty_documents": len(empty_lines),
            "empty_document_line_start": empty_lines,
            "n_non_empty_documents": res["n_docs"] - len(empty_lines),
            "vocabulary_size": len(res["vocab"]),
            "n_repeat_documents_in_variant": int(sel["is_repeat"].sum()),
            "n_forwarded_documents": int(sel["is_forwarded"].sum()),
            "n_documents_with_url": int(sel["has_url"].sum()),
            "n_documents_with_phone": int(sel["has_phone"].sum()),
            "sklearn_reference_max_abs_diff": sklearn_max_abs_diff(terms, res),
            "leave_one_out_top_k": leave_one_out_stability(terms),
            "top10_terms_by_total_tfidf": top_term_list(terms),
        }

    ngram_path = Path(ngram_dir) / "ngram_unigrams.csv"
    ngram_uni = read_csv_typed(ngram_path) if ngram_path.exists() else None
    comparison = variant_comparison(tops["all"], tops["unique"], ngram_uni)

    a10, u10 = set(meta_variants["all"]["top10_terms_by_total_tfidf"]), \
        set(meta_variants["unique"]["top10_terms_by_total_tfidf"])
    metadata = {
        "design": "docs/tfidf_design.md",
        "interpretation": "terms distinctive within this chat; descriptive, not generalisable",
        "unit_of_document": "one message",
        "formula": {"tf": "raw count", "idf": "ln((1+N)/(1+df)) + 1", "tfidf": "tf * idf",
                    "normalisation": "L2 per non-empty document",
                    "total_tfidf": "sum of L2-normalised tfidf over documents"},
        "vocabulary": "unigrams; English stopwords (Day 1 list) removed; <URL>/<PHONE> excluded; "
                      "no Marathi/Hindi stopword list",
        "N_definition": "total documents in selected corpus, empty documents included",
        "variants": meta_variants,
        "top10_overlap_between_variants": round(len(a10 & u10) / TOP_K, 4),
        "libraries": _library_versions(),
    }

    results_dir = Path(results_dir)
    pd.concat(longs, ignore_index=True).to_csv(
        results_dir / "tfidf_terms_by_message.csv", index=False, encoding="utf-8")
    pd.concat([tops["all"], tops["unique"]], ignore_index=True).to_csv(
        results_dir / "tfidf_top_terms.csv", index=False, encoding="utf-8")
    comparison.to_csv(results_dir / "tfidf_variant_comparison.csv", index=False, encoding="utf-8")
    (results_dir / "tfidf_run_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return docs, results, pd.concat(longs, ignore_index=True), tops, comparison, metadata


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    _, _, long_all, tops, comp, meta = run_tfidf()
    for v in VARIANTS:
        m = meta["variants"][v]
        print(f"\n== variant {v} ({m['role']}): N={m['n_documents_N']} "
              f"empty={m['n_empty_documents']} vocab={m['vocabulary_size']} "
              f"sklearn_diff={m['sklearn_reference_max_abs_diff']} ==")
        print(tops[v].head(15).to_string(index=False))
    print("\n== comparison (top 15 by primary rank) ==")
    print(comp.head(15).to_string(index=False))
    print("\nleave-one-out:", {v: meta["variants"][v]["leave_one_out_top_k"] for v in VARIANTS})
    print("top-10 overlap all vs unique:", meta["top10_overlap_between_variants"])
