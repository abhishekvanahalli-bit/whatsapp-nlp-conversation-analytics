"""
Reproducible command-line run of the whole analysis pipeline on one WhatsApp export.

    python scripts/run_full_pipeline.py --input data/sample_chat.txt --out results/sample
    python scripts/run_full_pipeline.py --input tests/fixtures/group_12.txt --out /tmp/wa_run --summary

Steps (the same modules the dashboard uses):
    parse -> preprocess -> n-grams -> TF-IDF -> Script Mix -> Key Terms -> conversation analytics

ALL outputs are written to --out, including the INTERNAL tables (processed_chat.csv, analysis_corpus.csv,
tfidf_terms_by_message.csv, key_terms.csv) that contain message text or terms and must never be shared for a
private chat. Run it on private data only with an output folder that Git ignores (for example
local_private/results; never results/sample, which is committed). The dashboard does not use this script; it runs the same steps in a temporary
folder and shows only the anonymised, display-filtered tables.
"""

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402
from pipeline_steps import run_all_steps  # noqa: E402

DEFAULT_INPUT = ROOT / "data" / "sample_chat.txt"
DEFAULT_OUT = ROOT / "results" / "latest"


def summarise(out_dir):
    comp = pd.read_csv(out_dir / "analytics_row_composition.csv").set_index(["group", "category"])["count"]
    tfidf = json.loads((out_dir / "tfidf_run_metadata.json").read_text(encoding="utf-8"))
    meta = json.loads((out_dir / "analytics_run_metadata.json").read_text(encoding="utf-8"))
    return {
        "parsed_rows": int(comp[("parsed_rows", "header")] + comp[("parsed_rows", "system")] + comp[("parsed_rows", "user")]),
        "system_rows": int(comp[("parsed_rows", "system")]),
        "user_rows": int(comp[("parsed_rows", "user")]),
        "text_messages": int(comp[("user_rows", "text")]),
        "media_rows": int(comp[("user_rows", "media")]),
        "deleted_rows": int(comp[("user_rows", "deleted")]),
        "participants": int(len(pd.read_csv(out_dir / "analytics_sender_counts.csv"))),
        "tfidf_documents": tfidf["variants"]["all"]["n_documents_N"],
        "tfidf_stability_mode": tfidf["variants"]["all"]["leave_one_out_top_k"]["mode"],
        "reconciliation_checks_passed": meta["n_reconciliation_checks"] if meta["all_reconciliation_checks_passed"] else "FAILED",
        "output_files": len([p for p in out_dir.iterdir() if p.is_file()]),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="WhatsApp .txt export (default: data/sample_chat.txt)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (default: results/latest, ignored by Git)")
    ap.add_argument("--summary", action="store_true", help="print aggregate counts when finished")
    args = ap.parse_args(argv)
    if not args.input.exists():
        ap.error(f"input file not found: {args.input}")
    args.out.mkdir(parents=True, exist_ok=True)
    df, failures, seconds = run_all_steps(args.input, args.out, progress=lambda name: print(f"  {name} ..."))
    print(f"done in {sum(seconds.values()):.1f}s; parsing failures: {len(failures)}; outputs in {args.out}")
    if args.summary:
        print(json.dumps(summarise(args.out), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
