"""
Runtime adapter for the dashboard: upload -> validate -> temporary run -> parse ->
preprocess -> n-grams -> TF-IDF -> conversation analytics -> load anonymised
results -> clean up.

The validated analysis modules are reused UNCHANGED. They are pointed at a fresh
per-upload temporary directory (never at the project's results/ folder); only
approved, anonymised outputs are loaded into memory and the directory is deleted
afterwards, whether the run succeeds or fails.

Supported input: the bracketed WhatsApp export format the parser was validated
on, "[M/D/YY, H:MM:SS AM/PM] Sender: message" (system lines "[...] - text" or
"[...] text" without a sender, optional untimed first line, continuation lines,
invisible marks before the bracket). Nothing else is claimed (docs/supported_formats.md).
Dates are read as Month/Day/Year (the parser's interpretation). When the date order
cannot be determined from the data a warning says so; Day/Month exports are rejected.
Timestamps are as recorded in the export and the time zone is unverified.
"""

import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conversation_analytics as ca  # noqa: E402
from csv_io import read_csv_typed  # noqa: E402
import key_terms as kt  # noqa: E402
import ngram_analysis as ng  # noqa: E402
import preprocessor as pp  # noqa: E402
import script_mix_analysis as sm  # noqa: E402
import tfidf_analysis as tf  # noqa: E402
from app_config import DEFAULT_CONFIG, AppConfig  # noqa: E402

PROJECT_RESULTS_DIR = ng.RESULTS_DIR.resolve()

DATE_FORMAT_NOTE = ("Dates are read as Month/Day/Year (M/D/YY), as recorded in the export. "
                    "The time zone is unverified: timestamps are shown as recorded.")

STAGES = (
    "Validate file",
    "Parse export",
    "Preprocess and quality checks",
    "N-gram analysis",
    "TF-IDF",
    "Script Mix",
    "Key Terms",
    "Conversation analytics",
    "Privacy filter and load results",
    "Clean up",
)

# Approved, anonymised outputs the dashboard may load. Everything else the
# modules write (processed_chat.csv, analysis_corpus.csv, message-level TF-IDF)
# contains message text or identifiers and is never loaded.
LOADABLE_CSV = tuple(n for n in ca.OUTPUT_FILES if n.endswith(".csv")) + (
    "ngram_unigrams.csv", "ngram_unigrams_with_stopwords.csv", "ngram_bigrams.csv",
    "ngram_trigrams.csv", "ngram_script_diagnostics.csv",
    "tfidf_top_terms.csv", "tfidf_variant_comparison.csv",
    "script_mix_summary.csv", "script_mixing_stats.csv", "key_terms.csv",
)
FORBIDDEN_COLUMNS = frozenset({"sender", "message", "clean_message", "text_masked", "tokens",
                               "tokens_no_stopwords", "line_start", "line_end"})
# tfidf metadata keys that hold terms (could contain low-frequency terms)
# (the empty-document line numbers are positions in the uploaded file; not needed by the dashboard)
TFIDF_META_DROP_KEYS = ("top10_terms_by_total_tfidf", "empty_document_line_start")

# a whole message of one to three words ending in "omitted" (Android "<x omitted>" or iOS "x omitted") that
# the parser did not recognise as a known placeholder: counted as text, with a warning
_UNRECOGNISED_PLACEHOLDER_RE = re.compile(r"^\s*<?\s*(?:[\w-]+ ){0,2}[\w-]+ omitted\s*>?\s*$", re.IGNORECASE)


class UserFacingError(Exception):
    """An error whose message is safe and useful to show to the user. It never
    contains file content."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class RunResult:
    filename: str
    content_sha256: str
    n_bytes: int
    info: dict
    warnings: list
    tables: dict
    analytics_meta: dict
    tfidf_meta: dict
    stage_seconds: dict = field(default_factory=dict)


# ------------------------------------------------------------- run directory ---
def make_run_dir():
    """Fresh temporary directory outside the project results folder."""
    run_dir = Path(tempfile.mkdtemp(prefix="wa_dashboard_run_")).resolve()
    if PROJECT_RESULTS_DIR == run_dir or PROJECT_RESULTS_DIR in run_dir.parents:
        shutil.rmtree(run_dir, ignore_errors=True)
        raise RuntimeError("run directory must not be inside the project results folder")
    return run_dir


def remove_run_dir(run_dir):
    shutil.rmtree(run_dir, ignore_errors=True)


# ---------------------------------------------------------------- validation ---
def pre_validate(data, filename, config):
    """Checks that need no parsing. Returns the decoded text."""
    if not str(filename).lower().endswith(".txt"):
        raise UserFacingError("wrong_type", "Please upload the exported chat as a .txt file.")
    if len(data) == 0:
        raise UserFacingError("empty", "The file is empty.")
    if len(data) > config.max_upload_bytes:
        raise UserFacingError(
            "too_large", f"The file is larger than the configured upload limit "
                         f"({config.max_upload_mb:g} MB).")
    try:
        text = data.decode("utf-8-sig")               # tolerates a leading BOM
    except UnicodeDecodeError:
        raise UserFacingError(
            "not_utf8", "This file could not be read as UTF-8 text. "
                        "Export the chat again as a text file.") from None
    if not text.strip():
        raise UserFacingError("empty", "The file is empty.")
    return text


def post_validate(df, failures, config):
    """Checks on the parser output. Raises UserFacingError for unusable input;
    otherwise returns (info, warnings). Failing lines are never included."""
    stamped_mask = df["date_str"].notna() if "date_str" in df else pd.Series(False, index=df.index)
    n_stamped = int(stamped_mask.sum())
    if n_stamped == 0:
        raise UserFacingError(
            "unsupported_format",
            "This does not look like a supported WhatsApp export. Expected lines such as "
            "'[M/D/YY, H:MM:SS AM/PM] Name: message'. Other export styles are not supported yet.")
    date_parts = df.loc[stamped_mask, "date_str"].astype(str).str.split("/", expand=True)
    max_first, max_second = int(date_parts[0].astype(int).max()), int(date_parts[1].astype(int).max())
    if max_first > 12 and max_second > 12:
        raise UserFacingError(
            "date_order_inconsistent",
            "The dates in this file are not consistent with Month/Day/Year: both the first and the "
            "second number exceed 12 in some rows. The export cannot be read safely.")
    if max_first > 12:
        raise UserFacingError(
            "date_order_unsupported",
            "This export appears to use Day/Month/Year dates (a first value above 12 occurs). Only "
            "Month/Day/Year dates are supported, so the file was not analysed to avoid misreading dates.")
    valid = int(df["datetime"].notna().sum())
    if valid == 0:
        raise UserFacingError(
            "dates_invalid",
            "Timestamps were found but none could be read. This app reads dates as Month/Day/Year "
            "with a 12-hour clock (AM/PM).")
    if len(df) > config.max_parsed_rows:
        raise UserFacingError(
            "too_many_rows", f"The chat has more parsed rows than the configured limit "
                             f"({config.max_parsed_rows:,}).")

    user = df[df["message_type"] == "user"]
    text_mask = (~user["is_media"]) & (~user["is_deleted"])
    n_text = int(text_mask.sum())
    if n_text > config.max_text_messages:
        raise UserFacingError(
            "too_many_messages", f"The chat has more text messages than the configured analysis "
                                 f"limit ({config.max_text_messages:,}).")

    warnings = []
    invalid = n_stamped - valid
    if invalid:
        warnings.append(f"{invalid} timestamped row(s) had a date or time that could not be read; "
                        "they are left out of the timeline.")
    if len(failures):
        warnings.append(f"{len(failures)} line(s) could not be interpreted and were skipped.")
    unrecognised = sum(1 for m in user.loc[text_mask, "message"].astype(str)
                       if _UNRECOGNISED_PLACEHOLDER_RE.match(m))
    if unrecognised:
        warnings.append(
            f"{unrecognised} message(s) look like media placeholders of a type this app does not "
            "recognise (see docs/supported_formats.md for the placeholders that are recognised). "
            "They are counted as text messages.")
    if n_text == 0:
        warnings.append("No text messages were found (only media, system or deleted rows). "
                        "Text analyses are empty; the conversation overview is still shown.")
    elif n_text < config.tiny_chat_text_messages:
        warnings.append(f"Only {n_text} text message(s): term rankings and stability checks are "
                        "not meaningful at this size.")
    elif n_text < config.small_chat_text_messages:
        warnings.append(f"Small chat ({n_text} text messages): treat all rankings as illustrative, "
                        "not as general findings.")

    dts = df["datetime"].dropna()
    if max_second > 12:
        order_note = "Day values above 12 occur, which is consistent with Month/Day/Year."
    else:
        order_note = ("All month/day values are 12 or below, so the export's date order cannot be "
                      "confirmed from the data. If this export uses Day/Month dates, every date, the "
                      "timeline and the weekday table are wrong. Check the date range below.")
        warnings.append(order_note)

    info = {
        "n_rows": len(df),
        "n_text_messages": n_text,
        "first_timestamp": dts.min().strftime("%Y-%m-%d %H:%M:%S"),
        "last_timestamp": dts.max().strftime("%Y-%m-%d %H:%M:%S"),
        "date_format_note": DATE_FORMAT_NOTE,
        "date_order_evidence": order_note,
        "parse_failures": len(failures),
        "unrecognised_placeholders": unrecognised,
    }
    return info, warnings


# ------------------------------------------------------------ result loading ---
def _read_csv(path):
    """Typed read: term/text columns stay strings (007 stays 007), only empty fields are missing."""
    try:
        return read_csv_typed(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def load_approved_outputs(run_dir):
    """Load only the whitelisted anonymised outputs. Raises if any loaded table
    has a column that could hold identifiers or message text."""
    run_dir = Path(run_dir)
    tables = {}
    for name in LOADABLE_CSV:
        frame = _read_csv(run_dir / name)
        leaked = FORBIDDEN_COLUMNS & set(frame.columns)
        if leaked:
            raise UserFacingError(
                "privacy_check_failed",
                "Outputs were withheld because a privacy check failed.")
        tables[Path(name).stem] = frame
    analytics_meta = json.loads((run_dir / "analytics_run_metadata.json").read_text(encoding="utf-8"))
    tfidf_meta = json.loads((run_dir / "tfidf_run_metadata.json").read_text(encoding="utf-8"))
    for variant in tfidf_meta.get("variants", {}).values():
        for key in TFIDF_META_DROP_KEYS:
            variant.pop(key, None)
    return tables, analytics_meta, tfidf_meta


# ------------------------------------------------------------------ pipeline ---
def run_pipeline(data, filename, config=DEFAULT_CONFIG, progress=None, run_dir_factory=None):
    """Run the validated pipeline on uploaded bytes and return a RunResult.

    progress(stage_index, stage_label) is called before each stage.
    Raises UserFacingError for invalid input. The temporary directory is
    always removed."""
    say = progress or (lambda i, label: None)
    make = run_dir_factory or make_run_dir
    seconds = {}

    def stage(i):
        say(i, STAGES[i])
        return time.perf_counter()

    t = stage(0)
    text = pre_validate(data, filename, config)
    seconds[STAGES[0]] = time.perf_counter() - t

    run_dir = make()
    try:
        upload_path = run_dir / "upload.txt"
        upload_path.write_text(text, encoding="utf-8", newline="")

        t = stage(1)
        try:
            df, failures = pp.build_dataset(upload_path)
        except UserFacingError:
            raise
        except Exception:
            raise UserFacingError("parse_failed",
                                  "The file could not be parsed. It may not be a supported "
                                  "WhatsApp export.") from None
        info, warnings = post_validate(df, failures, config)
        seconds[STAGES[1]] = time.perf_counter() - t

        t = stage(2)
        processed = run_dir / "processed_chat.csv"
        pp.save_processed_csv(df, processed)
        seconds[STAGES[2]] = time.perf_counter() - t

        steps = (
            (3, lambda: ng.run_analysis(processed, run_dir)),
            (4, lambda: tf.run_tfidf(processed, run_dir, run_dir)),
            (5, lambda: sm.run_script_mix(processed, run_dir, run_dir)),
            (6, lambda: kt.run_key_terms(processed, run_dir, run_dir)),
            (7, lambda: ca.run_analytics(processed, run_dir, run_dir)),
        )
        for i, fn in steps:
            t = stage(i)
            try:
                fn()
            except UserFacingError:
                raise
            except AssertionError:                          # a built-in consistency check failed
                raise UserFacingError(
                    "consistency_check_failed",
                    f"A consistency check failed during '{STAGES[i]}', so no results were produced. "
                    "Your file was not stored.") from None
            except Exception:
                raise UserFacingError(
                    "analysis_failed",
                    f"The analysis stopped unexpectedly during '{STAGES[i]}'. "
                    "Your file was not stored.") from None
            seconds[STAGES[i]] = time.perf_counter() - t

        t = stage(8)
        tables, analytics_meta, tfidf_meta = load_approved_outputs(run_dir)
        seconds[STAGES[8]] = time.perf_counter() - t
    finally:
        say(9, STAGES[9])
        remove_run_dir(run_dir)

    if analytics_meta.get("limited_result"):
        warnings.append("Some analyses are limited for this file: "
                        + ", ".join(r.replace("_", " ") for r in analytics_meta["limitation_reasons"])
                        + ".")
    return RunResult(
        filename=str(filename),
        content_sha256=hashlib.sha256(data).hexdigest(),
        n_bytes=len(data),
        info=info,
        warnings=warnings,
        tables=tables,
        analytics_meta=analytics_meta,
        tfidf_meta=tfidf_meta,
        stage_seconds=seconds,
    )
