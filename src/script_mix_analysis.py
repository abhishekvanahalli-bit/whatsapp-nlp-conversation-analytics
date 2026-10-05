"""
Script Mix: deterministic, script-level description of the text messages.

THIS IS NOT LANGUAGE IDENTIFICATION. Script is a property of characters;
language is an inference that needs a validated model. Devanagari script is not
automatically Marathi (it is also used for Hindi, Nepali, Sanskrit, ...), and
Latin script is not automatically English (it is also used for romanised
Marathi or Hindi). Nothing here claims a language, and "mixed-script" is an
observation about characters, not proof of code-switching.

Design: docs/language_and_keyword_design.md (Part A, LIMITED / descriptive).

Definitions (standard library only)
- A letter's script comes from its Unicode name: LATIN..., DEVANAGARI..., any
  other alphabetic character is "other". Only characters that are letters
  (str.isalpha) count, so digits (including Devanagari digits), danda
  punctuation, emoji and combining marks are not letters.
- Placeholders (<URL>, <PHONE>) are not text and are skipped.
- A token is *alphabetic* if it contains at least one letter. Its label is
  latin, devanagari or other when all its letters share one script, and
  "mixed_token" when letters of several scripts are glued in one token.
- Message class (over the alphabetic tokens of the message):
    no_alphabetic      no alphabetic token (link-only, digits/emoji only, empty)
    latin_only         all alphabetic tokens are latin
    devanagari_only    all are devanagari
    other_script_only  all are "other" script
    mixed_script       otherwise (two or more scripts, or any mixed_token)
- Devanagari share = devanagari alphabetic tokens / alphabetic tokens.
- Script alternation = number of adjacent alphabetic-token pairs whose labels
  differ. It is an observed alternation, not a count of code-switch points.
- Short message = 3 alphabetic tokens or fewer.

Two variants, like TF-IDF: "all" (every text message, repeats kept; primary)
and "unique" (first copy of each distinct masked text; sensitivity).

Privacy: outputs are aggregate counts only. No per-message rows, sender, text,
URL or phone number is written. Tokens come from the existing analysis layer
(URLs/phones already masked, forwarded marker already removed).
"""

import json
import statistics
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from csv_io import read_csv_typed  # noqa: E402
from ngram_analysis import (  # noqa: E402  (existing, tested analysis layer)
    PLACEHOLDERS,
    PROCESSED_CSV,
    RESULTS_DIR,
    analysis_tokenize,
    build_analysis_corpus,
)

LATIN, DEVANAGARI, OTHER, MIXED_TOKEN = "latin", "devanagari", "other", "mixed_token"
CLASSES = ("latin_only", "devanagari_only", "mixed_script", "other_script_only", "no_alphabetic")
VARIANTS = ("all", "unique")            # "all" is primary, "unique" is sensitivity
SHORT_MAX_TOKENS = 3
SHARE_BANDS = ((0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.0))   # (low, high]; 1.0 shown as its own band
OUTPUT_FILES = ("script_mix_summary.csv", "script_mixing_stats.csv", "script_mix_metadata.json")


# ------------------------------------------------------------ token / message ---
def letter_script(ch):
    """'latin', 'devanagari', 'other', or None when ch is not a letter."""
    if not ch.isalpha():
        return None
    name = unicodedata.name(ch, "")
    if name.startswith("LATIN"):
        return LATIN
    if name.startswith("DEVANAGARI"):
        return DEVANAGARI
    return OTHER


def token_profile(token):
    """(label, latin_letters, devanagari_letters, other_letters) for one token.
    label is None for placeholders and tokens without letters."""
    if token in PLACEHOLDERS:
        return None, 0, 0, 0
    counts = {LATIN: 0, DEVANAGARI: 0, OTHER: 0}
    for ch in token:
        script = letter_script(ch)
        if script:
            counts[script] += 1
    scripts = [s for s, n in counts.items() if n]
    if not scripts:
        return None, 0, 0, 0
    label = scripts[0] if len(scripts) == 1 else MIXED_TOKEN
    return label, counts[LATIN], counts[DEVANAGARI], counts[OTHER]


@dataclass(frozen=True)
class MessageProfile:
    message_class: str
    n_tokens: int                 # all tokens (incl. placeholders and non-alphabetic)
    n_alphabetic: int
    latin_tokens: int
    devanagari_tokens: int
    other_tokens: int
    mixed_tokens: int
    latin_letters: int
    devanagari_letters: int
    other_letters: int
    alternations: int
    devanagari_share: float       # NaN when there is no alphabetic token
    is_short: bool


def message_profile(tokens):
    """Deterministic script profile of one message given its token list."""
    labels, letters = [], [0, 0, 0]
    for token in tokens:
        label, lat, dev, oth = token_profile(token)
        if label is None:
            continue
        labels.append(label)
        letters[0] += lat
        letters[1] += dev
        letters[2] += oth
    n = len(labels)
    present = set(labels)
    if n == 0:
        cls = "no_alphabetic"
    elif present == {LATIN}:
        cls = "latin_only"
    elif present == {DEVANAGARI}:
        cls = "devanagari_only"
    elif present == {OTHER}:
        cls = "other_script_only"
    else:
        cls = "mixed_script"
    alternations = sum(1 for a, b in zip(labels, labels[1:]) if a != b)
    dev = labels.count(DEVANAGARI)
    return MessageProfile(
        message_class=cls, n_tokens=len(tokens), n_alphabetic=n,
        latin_tokens=labels.count(LATIN), devanagari_tokens=dev, other_tokens=labels.count(OTHER),
        mixed_tokens=labels.count(MIXED_TOKEN), latin_letters=letters[0], devanagari_letters=letters[1],
        other_letters=letters[2], alternations=alternations,
        devanagari_share=(dev / n) if n else float("nan"), is_short=n <= SHORT_MAX_TOKENS)


def profile_text(text):
    """Convenience: profile a raw message using the project's analysis tokenizer
    (URLs/phones masked to placeholders, which are then ignored)."""
    return message_profile(analysis_tokenize(text.lower() if text else ""))


# ------------------------------------------------------------------ variants ---
def profiles_by_variant(corpus):
    """{'all': [...], 'unique': [...]} of MessageProfile, from the analysis corpus
    (tokens before stopword removal, so script class does not depend on the English
    stopword list). Nothing is dropped from 'all'."""
    profiles = [message_profile(tokens) for tokens in corpus["tokens"]]
    repeat = corpus["is_repeat"].tolist()
    return {"all": profiles, "unique": [p for p, r in zip(profiles, repeat) if not r]}


# ----------------------------------------------------------------- aggregates ---
def summary_table(by_variant):
    rows = []
    for variant in VARIANTS:
        profiles = by_variant[variant]
        for cls in CLASSES:
            members = [p for p in profiles if p.message_class == cls]
            rows.append({"variant": variant, "message_class": cls, "messages": len(members),
                         "denominator": len(profiles),
                         "short_messages": sum(1 for p in members if p.is_short)})
    return pd.DataFrame(rows, columns=["variant", "message_class", "messages", "denominator",
                                       "short_messages"])


def _band_label(low, high):
    return f"share_{low:g}_to_{high:g}"


def stats_table(by_variant):
    """Long table of script-mixing statistics: variant, metric, value, denominator."""
    rows = []

    def add(variant, metric, value, denominator):
        rows.append({"variant": variant, "metric": metric, "value": value, "denominator": denominator})

    for variant in VARIANTS:
        profiles = by_variant[variant]
        n = len(profiles)
        mixed = [p for p in profiles if p.message_class == "mixed_script"]
        alts = [p.alternations for p in mixed]
        shares = [p.devanagari_share for p in mixed]
        add(variant, "mixed_script_messages", len(mixed), n)
        add(variant, "mixed_messages_with_alternation", sum(1 for a in alts if a > 0), len(mixed))
        add(variant, "total_alternations", sum(p.alternations for p in profiles), "")
        add(variant, "median_alternations_mixed", statistics.median(alts) if alts else "", len(mixed))
        add(variant, "max_alternations_mixed", max(alts) if alts else "", len(mixed))
        add(variant, "min_devanagari_share_mixed", round(min(shares), 4) if shares else "", len(mixed))
        add(variant, "median_devanagari_share_mixed", round(statistics.median(shares), 4) if shares else "", len(mixed))
        add(variant, "max_devanagari_share_mixed", round(max(shares), 4) if shares else "", len(mixed))
        for low, high in SHARE_BANDS:
            in_band = sum(1 for s in shares if (s > low and s <= high) and s < 1.0)
            add(variant, _band_label(low, high), in_band, len(mixed))
        add(variant, "mixed_messages_devanagari_share_0", sum(1 for s in shares if s == 0.0), len(mixed))
        add(variant, "mixed_messages_devanagari_share_1", sum(1 for s in shares if s == 1.0), len(mixed))
        add(variant, "no_alphabetic_messages", sum(1 for p in profiles if p.message_class == "no_alphabetic"), n)
        add(variant, "short_messages_all_classes", sum(1 for p in profiles if p.is_short), n)
        for name in ("latin", "devanagari", "other", "mixed"):
            add(variant, f"alphabetic_tokens_{name}", sum(getattr(p, f"{name}_tokens") for p in profiles),
                sum(p.n_alphabetic for p in profiles))
        for name in ("latin", "devanagari", "other"):
            add(variant, f"letters_{name}", sum(getattr(p, f"{name}_letters") for p in profiles), "")
    # object dtype keeps counts as integers ("7") and shares as decimals ("0.4615") in the CSV
    return pd.DataFrame(rows, columns=["variant", "metric", "value", "denominator"], dtype=object)


# ------------------------------------------------------------- reconciliation ---
def reconciliation_checks(by_variant, summary, stats, corpus, diagnostics=None):
    """Hard invariants (all must pass) plus an informational comparison with the
    existing token-level script diagnostics."""
    checks = []

    def add(name, left, right):
        checks.append({"check": name, "left": int(left), "right": int(right), "passed": bool(left == right)})

    n_all, n_unique = len(by_variant["all"]), len(by_variant["unique"])
    for variant in VARIANTS:
        sub = summary[summary["variant"] == variant]
        add(f"{variant}: class counts sum == messages", sub["messages"].sum(), len(by_variant[variant]))
        add(f"{variant}: short messages <= messages", int(sub["short_messages"].sum() <= sub["messages"].sum()), 1)
    add("all == number of text messages in corpus", n_all, len(corpus))
    add("unique + repeats == all", n_unique + int(corpus["is_repeat"].sum()), n_all)
    for variant in VARIANTS:
        st = stats[stats["variant"] == variant].set_index("metric")["value"]
        banded = sum(int(v) for k, v in st.items() if k.startswith("share_"))             + int(st["mixed_messages_devanagari_share_0"]) + int(st["mixed_messages_devanagari_share_1"])
        add(f"{variant}: share bands sum == mixed messages", banded, int(st["mixed_script_messages"]))
    add("alternations are zero outside mixed_script",
        sum(p.alternations for p in by_variant["all"] if p.message_class != "mixed_script"), 0)
    add("no mixed_script message lacks a second script",
        sum(1 for p in by_variant["all"] if p.message_class == "mixed_script"
            and p.n_alphabetic > 0 and p.latin_tokens == p.n_alphabetic), 0)
    agreement = None
    if diagnostics is not None and not diagnostics.empty:
        d = diagnostics.set_index("script")["tokens_before"]
        s = stats[stats["variant"] == "all"].set_index("metric")["value"]
        agreement = {
            "latin_tokens": [int(s["alphabetic_tokens_latin"]), int(d.get("latin", 0))],
            "devanagari_tokens_incl_mixed_tokens": [int(s["alphabetic_tokens_devanagari"] + s["alphabetic_tokens_mixed"]),
                                                    int(d.get("devanagari", 0))],
        }
        agreement["agrees"] = all(v[0] == v[1] for v in agreement.values() if isinstance(v, list))
    return checks, agreement


# --------------------------------------------------------------------- driver ---
def run_script_mix(processed_csv=PROCESSED_CSV, results_dir=RESULTS_DIR, ngram_dir=None):
    """Compute and write the aggregate Script Mix outputs. Raises AssertionError
    (writing nothing) if a hard invariant fails. Existing files are only read."""
    df = read_csv_typed(processed_csv)
    corpus = build_analysis_corpus(df)
    by_variant = profiles_by_variant(corpus)
    summary = summary_table(by_variant)
    stats = stats_table(by_variant)

    diag_path = Path(ngram_dir if ngram_dir is not None else results_dir) / "ngram_script_diagnostics.csv"
    diagnostics = read_csv_typed(diag_path) if diag_path.exists() else None
    checks, agreement = reconciliation_checks(by_variant, summary, stats, corpus, diagnostics)
    failed = [c for c in checks if not c["passed"]]
    if failed:
        raise AssertionError(f"script mix reconciliation failed: {failed}")

    metadata = {
        "design": "docs/language_and_keyword_design.md",
        "what_this_is": "script composition (deterministic, from Unicode letter names); "
                        "NOT language identification and NOT proof of code-switching",
        "variants": {"all": "every text message, repeats kept (primary)",
                     "unique": "first copy of each distinct masked text (sensitivity)"},
        "n_messages": {v: len(by_variant[v]) for v in VARIANTS},
        "definitions": {
            "alphabetic_token": "contains at least one letter; placeholders, digits, emoji, punctuation excluded",
            "message_class": list(CLASSES),
            "devanagari_share": "devanagari alphabetic tokens / alphabetic tokens (mixed tokens not counted as devanagari)",
            "alternation": "adjacent alphabetic-token pairs with different script label",
            "short_message": f"{SHORT_MAX_TOKENS} alphabetic tokens or fewer",
        },
        "privacy": "aggregate counts only; no per-message rows, text, senders, URLs or phone numbers",
        "n_reconciliation_checks": len(checks),
        "all_reconciliation_checks_passed": True,
        "reconciliation_checks": checks,
        "agreement_with_existing_script_diagnostics": agreement,
    }
    out = Path(results_dir)
    summary.to_csv(out / "script_mix_summary.csv", index=False, encoding="utf-8")
    stats.to_csv(out / "script_mixing_stats.csv", index=False, encoding="utf-8")
    (out / "script_mix_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return summary, stats, metadata


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    summary, stats, meta = run_script_mix()
    print(summary.to_string(index=False))
    print(stats.to_string(index=False))
    print("checks:", meta["n_reconciliation_checks"], "agreement:", meta["agreement_with_existing_script_diagnostics"])
