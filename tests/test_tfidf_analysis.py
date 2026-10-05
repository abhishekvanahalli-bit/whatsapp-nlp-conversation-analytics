import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import ngram_analysis as ng  # noqa: E402
import tfidf_analysis as tf  # noqa: E402
from helpers import SAMPLE_CHAT, SAMPLE_CSV, SAMPLE_DIR, corpus_counts  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROTECTED = [SAMPLE_CHAT, SAMPLE_CSV] + sorted(SAMPLE_DIR.glob("ngram_*.csv")) + [SAMPLE_DIR / "analysis_corpus.csv"]

needs_data = pytest.mark.skipif(not SAMPLE_CSV.exists(), reason="synthetic sample outputs missing")


# ------------------------------------------------------------ formula tests --
def test_hand_computed_tfidf():
    docs = [["a", "b", "b"], ["a", "c"], ["d"]]          # N = 3
    r = tf.compute_tfidf(docs)
    assert r["vocab"] == ["a", "b", "c", "d"]
    assert r["n_docs"] == 3
    assert list(r["df"]) == [2, 1, 1, 1]
    idf_a, idf_x = math.log(4 / 3) + 1, math.log(4 / 2) + 1
    assert r["idf"] == pytest.approx([idf_a, idf_x, idf_x, idf_x])
    assert r["tf"][0].tolist() == [1, 2, 0, 0]
    # doc 0 raw: a = 1*idf_a, b = 2*idf_x
    assert r["raw"][0] == pytest.approx([idf_a, 2 * idf_x, 0, 0])
    norm0 = math.sqrt(idf_a ** 2 + (2 * idf_x) ** 2)
    assert r["norm"][0] == pytest.approx([idf_a / norm0, 2 * idf_x / norm0, 0, 0])
    # doc 2 has one term: after L2 it is exactly 1
    assert r["norm"][2] == pytest.approx([0, 0, 0, 1.0])


def test_l2_norm_is_one_for_non_empty_documents():
    r = tf.compute_tfidf([["a", "b"], ["a"], [], ["c", "c", "a"]])
    norms = np.sqrt((r["norm"] ** 2).sum(axis=1))
    for i, empty in enumerate(r["empty_mask"]):
        assert norms[i] == pytest.approx(0.0 if empty else 1.0)


def test_empty_document_stays_in_N_and_adds_no_tf_or_df():
    with_empty = tf.compute_tfidf([["a"], [], ["a", "b"]])
    assert with_empty["n_docs"] == 3                     # N counts the empty document
    assert list(with_empty["empty_mask"]) == [False, True, False]
    assert list(with_empty["df"]) == [2, 1]              # empty doc contributed no df
    assert with_empty["tf"][1].sum() == 0 and with_empty["norm"][1].sum() == 0
    assert with_empty["idf"][0] == pytest.approx(math.log(4 / 3) + 1)   # uses N = 3, not 2
    without = tf.compute_tfidf([["a"], ["a", "b"]])
    assert without["idf"][0] == pytest.approx(math.log(3 / 3) + 1)      # N = 2 would differ
    assert with_empty["idf"][0] != pytest.approx(without["idf"][0])


def test_no_nan_or_inf_with_empty_documents():
    r = tf.compute_tfidf([[], ["a"], []])
    assert np.isfinite(r["norm"]).all() and np.isfinite(r["raw"]).all()


def test_idf_range_and_df_bounds():
    r = tf.compute_tfidf([["a", "b"], ["a"], ["a", "c"]])
    assert (r["idf"] >= 1.0).all()
    assert ((r["df"] >= 1) & (r["df"] <= r["n_docs"])).all()
    assert r["idf"][0] == pytest.approx(1.0)             # term in every document


def test_sklearn_cross_check_on_toy_corpus():
    pytest.importorskip("sklearn")
    docs = [["a", "b", "b"], ["a", "c"], [], ["d", "a"]]
    r = tf.compute_tfidf(docs)
    assert tf.sklearn_max_abs_diff(docs, r) < 1e-12


def test_variant_selection():
    docs = pd.DataFrame({"line_start": [1, 2, 3], "is_repeat": [False, True, False]})
    assert len(tf.select_variant(docs, "all")) == 3
    assert list(tf.select_variant(docs, "unique")["line_start"]) == [1, 3]
    with pytest.raises(ValueError):
        tf.select_variant(docs, "bogus")


def test_leave_one_out_stability_behaviour():
    same = [["a", "b"]] * 4
    s = tf.leave_one_out_stability(same, k=2)
    assert s["n_runs"] == 4 and s["mean_overlap"] == 1.0 and s["min_overlap"] == 1.0
    # every single-term document normalises to 1.0, so the full top-1 is "p"
    # (alphabetical tie-break). Removing the document containing "p" (index 1)
    # promotes "q" -> overlap 0; removing any other document keeps "p" -> overlap 1.
    docs = [["x", "x", "x", "y"], ["p"], ["q"], ["r"]]
    assert tf.top_term_list(docs, k=1) == ["p"]
    s = tf.leave_one_out_stability(docs, k=1)
    assert s["n_runs"] == 4 and s["min_overlap"] == 0.0 and s["argmin_doc_index"] == 1
    assert s["mean_overlap"] == 0.75
    assert tf.leave_one_out_stability([], k=2)["n_runs"] == 0


def test_top_term_tiebreak_is_alphabetical():
    assert tf.top_term_list([["b", "a"]], k=2) == ["a", "b"]


def test_long_table_ranks_and_columns():
    docs = pd.DataFrame({"line_start": [1, 2], "sender_anon": ["S", "S"],
                         "is_forwarded": [False, False], "is_repeat": [False, False],
                         "has_url": [False, True], "has_phone": [False, False]})
    r = tf.compute_tfidf([["a", "b", "b"], []])
    lt = tf.long_table(docs, r, "all")
    assert set(lt["line_start"]) == {1}                  # empty doc has no rows
    top = lt.sort_values("rank_in_message").iloc[0]
    assert top["term"] == "b" and top["rank_in_message"] == 1
    assert lt["tfidf_norm"].pow(2).sum() == pytest.approx(1.0)


# --------------------------------------------- real-data pipeline checks -----
@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("tfidf")
    before = {p: p.read_bytes() for p in PROTECTED if p.exists()}
    result = tf.run_tfidf(SAMPLE_CSV, out, SAMPLE_DIR)
    return out, before, result


@needs_data
def test_primary_and_sensitivity_N(run):
    _, _, (docs, results, long_df, tops, comp, meta) = run
    n_all, n_unique, _ = corpus_counts()
    assert meta["variants"]["all"]["n_documents_N"] == n_all
    assert meta["variants"]["unique"]["n_documents_N"] == n_unique
    assert results["all"][1]["n_docs"] == n_all and results["unique"][1]["n_docs"] == n_unique


@needs_data
def test_n_reconciliation_and_empty_documents(run):
    _, _, (docs, results, long_df, tops, comp, meta) = run
    for v in tf.VARIANTS:
        m = meta["variants"][v]
        assert m["n_non_empty_documents"] + m["n_empty_documents"] == m["n_documents_N"]
        assert m["n_empty_documents"] == len(m["empty_document_line_start"])
        sel, res = results[v]
        assert int(res["empty_mask"].sum()) == m["n_empty_documents"]
        # empty documents have no rows in the term table
        empty_lines = set(m["empty_document_line_start"])
        assert not (set(long_df.loc[long_df["variant"] == v, "line_start"]) & empty_lines)
        # df in the table matches an independent count from the term lists
        indep = {}
        for terms in sel["terms"]:
            for w in set(terms):
                indep[w] = indep.get(w, 0) + 1
        top = tops[v].set_index("term")
        assert {t: int(d) for t, d in top["df"].items()} == indep


@needs_data
def test_repeats_preserved_in_primary_and_collapsed_in_sensitivity(run):
    _, _, (docs, results, *_ ) = run
    n_all, n_unique, n_repeat = corpus_counts()
    assert n_repeat > 0, "the sample must contain repeated messages"
    assert results["all"][0]["is_repeat"].sum() == n_repeat      # repeated messages kept
    assert len(results["all"][0]) == n_all
    assert not results["unique"][0]["is_repeat"].any()
    assert len(results["unique"][0]) == n_unique


@needs_data
def test_identical_texts_get_identical_vectors(run):
    _, _, (docs, results, long_df, *_ ) = run
    sel, res = results["all"]
    texts = {}
    for i, terms in enumerate(sel["terms"]):
        texts.setdefault(tuple(terms), []).append(i)
    checked = 0
    for idxs in texts.values():
        if len(idxs) > 1 and len(idxs[0:1]) and sel.at[idxs[0], "n_terms"] > 0:
            for j in idxs[1:]:
                assert res["norm"][idxs[0]] == pytest.approx(res["norm"][j])
                checked += 1
    assert checked > 0


@needs_data
def test_sklearn_cross_check_real_data(run):
    pytest.importorskip("sklearn")
    _, _, (docs, results, *_ ) = run
    for v in tf.VARIANTS:
        sel, res = results[v]
        assert tf.sklearn_max_abs_diff(sel["terms"].tolist(), res) < 1e-12


@needs_data
def test_l2_and_ranges_real_data(run):
    _, _, (docs, results, long_df, *_ ) = run
    for v in tf.VARIANTS:
        _, res = results[v]
        norms = np.sqrt((res["norm"] ** 2).sum(axis=1))
        assert np.allclose(norms[~res["empty_mask"]], 1.0)
        assert (norms[res["empty_mask"]] == 0).all()
    assert (long_df["idf"] >= 1).all() and (long_df["tfidf_raw"] > 0).all()
    assert (long_df["tfidf_norm"] > 0).all()


@needs_data
def test_placeholders_forwarded_and_privacy(run):
    out, _, (_, _, long_df, *_ ) = run
    assert not long_df["term"].isin(list(ng.PLACEHOLDERS)).any()
    assert "forwarded" not in set(long_df["term"])          # marker is metadata
    assert long_df["is_forwarded"].any()                     # flag preserved
    assert long_df["has_url"].any()                          # URL presence kept as metadata
    blob = "".join(p.read_text(encoding="utf-8") for p in out.iterdir())
    # identifiers are derived from the raw data at test time (never hard-coded in the repository)
    raw = pd.read_csv(SAMPLE_CSV)
    phones = {m for t in raw["message"].astype(str) for m in re.findall(r"\+\d[\d ]{7,}\d", t)}
    phones |= {s for s in raw["sender"].dropna() if s.startswith("+")}
    groups = {g for p in phones for g in p.split()[1:] if len(g) >= 4}
    assert groups
    for leak in ["+91", "chat.whatsapp.com", "http"]:
        assert leak not in blob, leak
    # whole number groups only: a digit run inside a decimal score is not a leak
    assert not any(re.search(r"(?<![\d.])" + g + r"(?!\d)", blob) for g in groups), "phone number group leaked"
    # placeholders may be *described* in the metadata text but never appear as data
    csv_blob = "".join(p.read_text(encoding="utf-8") for p in out.glob("*.csv"))
    assert "<URL>" not in csv_blob and "<PHONE>" not in csv_blob


@needs_data
def test_approved_outputs_exist_and_metadata_valid(run):
    out, _, _ = run
    for name in ("tfidf_terms_by_message.csv", "tfidf_top_terms.csv",
                 "tfidf_variant_comparison.csv", "tfidf_run_metadata.json"):
        assert (out / name).exists()
    meta = json.loads((out / "tfidf_run_metadata.json").read_text(encoding="utf-8"))
    assert meta["N_definition"].startswith("total documents")
    for v in tf.VARIANTS:
        loo = meta["variants"][v]["leave_one_out_top_k"]
        assert loo["n_runs"] == meta["variants"][v]["n_documents_N"]
        assert 0 <= loo["min_overlap"] <= loo["mean_overlap"] <= 1


@needs_data
def test_comparison_rank_change_formula(run):
    _, _, (*_, comp, _) = run
    both = comp.dropna(subset=["rank_all", "rank_unique"])
    assert ((both["rank_unique"] - both["rank_all"]) == both["rank_change"]).all()
    assert comp["count_all"].notna().all()                   # joined from n-gram table


@needs_data
def test_deterministic_output(tmp_path, run):
    out, _, _ = run
    other = tmp_path / "second"
    other.mkdir()
    tf.run_tfidf(SAMPLE_CSV, other, SAMPLE_DIR)
    for p in out.iterdir():
        assert p.read_bytes() == (other / p.name).read_bytes(), p.name


@needs_data
def test_raw_and_existing_results_unchanged(run):
    _, before, _ = run
    for p, content in before.items():
        assert p.read_bytes() == content, f"{p.name} changed"


@needs_data
def test_output_names_do_not_overwrite_existing_results():
    existing = {p.name for p in SAMPLE_DIR.iterdir()}
    new = {"tfidf_terms_by_message.csv", "tfidf_top_terms.csv",
           "tfidf_variant_comparison.csv", "tfidf_run_metadata.json"}
    assert not (new & existing & {"processed_chat.csv", "analysis_corpus.csv"})
    assert all(not n.startswith("ngram_") for n in new)
