"""
Day 2, Milestone 1: reusable n-gram analysis over the Day 1 processed dataset.

Design decisions:
- processed_chat.csv is READ ONLY. All analysis-specific preprocessing lives in
  this module and is written to separate files under results/.
- Corpus = user rows only, excluding media placeholders and deletion tombstones
  (system/header rows are never "conversation" in the first place).
- The leading "[Forwarded]" marker is removed from the NLP text only; the
  `is_forwarded` flag is preserved as metadata (never in the vocabulary).
- URLs -> "<URL>" and phone numbers -> "<PHONE>" placeholders (not deletion), so
  the fact that a URL / phone number occurred stays visible to the analysis
  while the identifying string does not.
- Repeated messages are NOT removed. Every n-gram is counted two ways:
    count_all    : over every message, repetitions included
    count_unique : over unique message texts only (each distinct text once)
  count_all / count_unique = how much repetition inflates an n-gram.
- N-grams are generated PER MESSAGE, never across message boundaries.
- Bigrams/trigrams use the raw token sequence (stopwords kept) to preserve true
  adjacency; only the unigram "content" view drops stopwords.
- Stopwords: the Day 1 English list only. No Marathi list is added on purpose;
  script_diagnostics() measures the resulting mixed-language effect.
"""

import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from csv_io import read_csv_typed  # noqa: E402
from preprocessor import STOPWORDS, normalise_punctuation, strip_token_edges  # noqa: E402  (Day 1 helpers)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_CSV = PROJECT_ROOT / "results" / "processed_chat.csv"
RESULTS_DIR = PROJECT_ROOT / "results"

URL_TOKEN, PHONE_TOKEN = "<URL>", "<PHONE>"
PLACEHOLDERS = frozenset({URL_TOKEN, PHONE_TOKEN})

# Links: explicit URLs, WhatsApp / short-link domains written without "https://", e-mail addresses and
# bare web addresses ending in a common top-level domain. All become the <URL> placeholder.
_URL_RE = re.compile(
    r"(?:https?://|www\.)\S+"
    r"|\b(?:chat\.whatsapp\.com|api\.whatsapp\.com|whatsapp\.com|wa\.me|youtu\.be|bit\.ly|t\.me)/\S*"
    r"|\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"
    r"|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|org|net|edu|gov|in|co|io|app|me|ly|info|biz|us|uk)\b(?:/\S*)?",
    re.IGNORECASE)
# Phone numbers: international "+CC ..." numbers (8-15 digits, spaces/hyphens/dots/brackets allowed between
# digits) and local numbers written as 9-15 digits optionally separated by single spaces or hyphens
# (e.g. 9876543210, 098765-43210, 022 2345 6789). Date-like strings (10-03-2025 14:30) are left alone.
_INTL_PHONE_RE = re.compile(r"\+\d(?:[\s\-().]?\d){7,14}")
_LOCAL_PHONE_RE = re.compile(r"(?<!\d)\d(?:[ \-]?\d){8,14}(?!\d)")
_DATE_START_RE = re.compile(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{2,4}")
_FORWARDED_RE = re.compile(r"^\s*\[forwarded\]\s*", re.IGNORECASE)
_EDITED_RE = re.compile(r"\s*<this message was edited>\s*$", re.IGNORECASE)
_DEVANAGARI_RE =re.compile(r"[ऀ-ॿ]")


# ----------------------------------------------------------------- corpus ---
def get_conversational_rows(df):
    """User-authored rows with real text: excludes system/header rows and
    media/deleted placeholder rows (they carry no organic language content).
    """
    mask = (df["message_type"] == "user") & (~df["is_media"]) & (~df["is_deleted"])
    return df.loc[mask].copy()


# ------------------------------------------------- analysis preprocessing ---
def mask_urls(text):
    """Replace each URL with <URL>. Keeps 'a link was shared here' as a signal
    (deleting it would make 'join this group' look like a complete sentence
    with no link, and would glue neighbouring words together)."""
    return _URL_RE.sub(f" {URL_TOKEN} ", text)


def _mask_local_number(match):
    text = match.group(0)
    return text if _DATE_START_RE.match(text) else f" {PHONE_TOKEN} "


def mask_phones(text):
    """Replace phone numbers (international and local formats) with <PHONE> so raw numbers never
    reach outputs. Precautionary pattern masking, not complete PII detection."""
    return _LOCAL_PHONE_RE.sub(_mask_local_number, _INTL_PHONE_RE.sub(f" {PHONE_TOKEN} ", text))


def strip_forwarded_marker(text):
    """Remove the leading "[Forwarded]" marker. It is added by the Day 1 parser
    / WhatsApp export, not written by the sender, so it is metadata rather than
    vocabulary. The fact is kept in the `is_forwarded` column; only the NLP
    text loses the marker. Only a marker at the start of the message is removed
    (a user typing "[forwarded]" mid-sentence is real language)."""
    return _FORWARDED_RE.sub("", text, count=1)


def strip_edited_marker(text):
    """Remove the trailing "<This message was edited>" marker that WhatsApp appends (metadata, not words)."""
    return _EDITED_RE.sub("", text, count=1)


def analysis_tokenize(clean_message):
    """Strip the forwarded/edited markers, mask URLs then phones, normalise curly quotes, then
    whitespace-tokenize with punctuation (ASCII and Unicode, incl. the Devanagari danda) stripped at
    token edges (same rule as Day 1). Placeholders are preserved verbatim."""
    if not clean_message:
        return []
    text = mask_phones(mask_urls(strip_edited_marker(strip_forwarded_marker(clean_message))))
    tokens = []
    for tok in normalise_punctuation(text).split():
        if tok in PLACEHOLDERS:
            tokens.append(tok)
            continue
        tok = strip_token_edges(tok)
        if tok:
            tokens.append(tok)
    return tokens


def remove_stopwords(tokens):
    """Set-membership filtering with the Day 1 English list (placeholders are
    never in it, so they survive)."""
    return [t for t in tokens if t not in STOPWORDS]


def anonymize_senders(senders):
    """Map each distinct sender (phone number or name) to Sender_1, Sender_2...
    in order of first appearance. Nothing identifying is kept."""
    mapping = {}
    for s in senders:
        if s not in mapping:
            mapping[s] = f"Sender_{len(mapping) + 1}"
    return [mapping[s] for s in senders]


def build_analysis_corpus(df):
    """Analysis-only view of the conversational rows. Does not modify df."""
    rows = get_conversational_rows(df)
    out = pd.DataFrame({"line_start": rows["line_start"].values})
    out["sender_anon"] = anonymize_senders(rows["sender"].tolist())
    out["is_forwarded"] = rows["is_forwarded"].values  # metadata kept, marker not in text
    out["tokens"] = [analysis_tokenize(m) for m in rows["clean_message"]]
    out["tokens_no_stopwords"] = out["tokens"].apply(remove_stopwords)
    out["text_masked"] = out["tokens"].apply(" ".join)
    # identical masked text == same message text (e.g. the six invite messages
    # differ only in link id, which masking removes)
    out["is_repeat"] = out["text_masked"].duplicated(keep="first")
    return out


# ------------------------------------------------------------ n-gram core ---
def generate_ngrams(tokens, n):
    """N-grams from a single token list, preserving original word order."""
    if n < 1:
        raise ValueError("n must be >= 1")
    if len(tokens) < n:
        return []
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def ngram_frequencies(token_lists, n):
    """Aggregate n-gram counts across many messages (token_lists), one
    message's tokens at a time so n-grams never cross message boundaries."""
    counter = Counter()
    for tokens in token_lists:
        counter.update(generate_ngrams(tokens, n))
    return counter


def document_frequencies(token_lists, n):
    """In how many messages does each n-gram appear (once per message)?"""
    counter = Counter()
    for tokens in token_lists:
        counter.update(set(generate_ngrams(tokens, n)))
    return counter


def unique_token_lists(token_lists):
    """Distinct token sequences, first occurrence kept, order preserved."""
    seen, out = set(), []
    for tokens in token_lists:
        key = tuple(tokens)
        if key not in seen:
            seen.add(key)
            out.append(tokens)
    return out


def ngram_table(token_lists, n):
    """One row per n-gram: count_all, count_unique, msgs_all, repetition_ratio.
    Sorted by count_all desc, then alphabetically (deterministic ties)."""
    token_lists = list(token_lists)
    uniq = unique_token_lists(token_lists)
    c_all = ngram_frequencies(token_lists, n)
    c_uni = ngram_frequencies(uniq, n)
    df_all = document_frequencies(token_lists, n)
    rows = [
        {
            "ngram": " ".join(g),
            "count_all": c,
            "count_unique": c_uni.get(g, 0),
            "msgs_all": df_all[g],
            "repetition_ratio": round(c / c_uni[g], 2) if c_uni.get(g) else None,
        }
        for g, c in c_all.items()
    ]
    table = pd.DataFrame(
        rows, columns=["ngram", "count_all", "count_unique", "msgs_all", "repetition_ratio"]
    )
    return table.sort_values(["count_all", "ngram"], ascending=[False, True]).reset_index(drop=True)


# ------------------------------------------------- mixed-language baseline ---
def token_script(token):
    if token in PLACEHOLDERS:
        return "placeholder"
    if _DEVANAGARI_RE.search(token):
        return "devanagari"
    if re.search(r"[A-Za-z]", token):
        return "latin"
    return "other"  # digits, emoji, symbols


def script_diagnostics(token_lists):
    """How much of each script does English stopword removal remove?
    Shows the mixed-language effect without inventing a Marathi list."""
    before, after = Counter(), Counter()
    for tokens in token_lists:
        before.update(token_script(t) for t in tokens)
        after.update(token_script(t) for t in remove_stopwords(tokens))
    rows = []
    for script in ("latin", "devanagari", "placeholder", "other"):
        b, a = before[script], after[script]
        rows.append({"script": script, "tokens_before": b, "tokens_after": a,
                     "pct_removed": round(100 * (b - a) / b, 1) if b else None})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ driver ---
def run_analysis(processed_csv=PROCESSED_CSV, results_dir=RESULTS_DIR):
    df = read_csv_typed(processed_csv)
    corpus = build_analysis_corpus(df)
    raw, content = corpus["tokens"].tolist(), corpus["tokens_no_stopwords"].tolist()

    tables = {
        "unigrams": ngram_table(content, 1),              # stopwords removed
        "unigrams_with_stopwords": ngram_table(raw, 1),   # baseline comparison
        "bigrams": ngram_table(raw, 2),
        "trigrams": ngram_table(raw, 3),
    }
    diag = script_diagnostics(raw)

    results_dir = Path(results_dir)
    corpus.assign(tokens=corpus["tokens"].apply(" ".join),
                  tokens_no_stopwords=corpus["tokens_no_stopwords"].apply(" ".join)
                  ).to_csv(results_dir / "analysis_corpus.csv", index=False, encoding="utf-8")
    for name, t in tables.items():
        t.to_csv(results_dir / f"ngram_{name}.csv", index=False, encoding="utf-8")
    diag.to_csv(results_dir / "ngram_script_diagnostics.csv", index=False, encoding="utf-8")
    return corpus, tables, diag


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    corpus, tables, diag = run_analysis()
    print(f"messages={len(corpus)} unique_texts={(~corpus.is_repeat).sum()}")
    for name, t in tables.items():
        print(f"\n== {name} (top 15 of {len(t)}) ==")
        print(t.head(15).to_string(index=False))
    print("\n== script diagnostics ==")
    print(diag.to_string(index=False))
