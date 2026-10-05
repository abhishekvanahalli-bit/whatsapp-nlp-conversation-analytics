"""
Display-layer privacy filter for the NLP tables.

Words and phrases shown in the n-gram / TF-IDF views come from the uploaded
chat and can include names or other identifying terms. As a PRECAUTION against
exposing low-frequency identifying terms, terms that occur in only one message
are hidden by default. This filter acts only on what is displayed or offered
for download; it never alters the underlying analysis, and it is not complete
PII detection: terms that occur in several messages (for example a name used
repeatedly) are still shown.

A second, defensive pass drops any term that looks like a URL, an e-mail
address, a WhatsApp link or a long digit run (phone-like), in case masking
missed one. This is a precautionary display/download layer and is not a
complete PII detector.
"""

import re

import pandas as pd

_SENSITIVE_TERM_RE = re.compile(
    r"(https?://|www\.|@|chat\.whatsapp|wa\.me|whatsapp\.com"
    r"|\b[a-z0-9-]+\.(?:com|org|net|edu|gov|in|co|io|app|me|ly|info|biz|us|uk)\b)", re.IGNORECASE)
_MIN_PHONE_DIGITS = 7           # a term (or phrase) with this many digits in total looks like a phone number

NGRAM_TABLES = ("ngram_unigrams", "ngram_unigrams_with_stopwords", "ngram_bigrams", "ngram_trigrams")
TERM_COLUMN = {"ngram_unigrams": "ngram", "ngram_unigrams_with_stopwords": "ngram",
               "ngram_bigrams": "ngram", "ngram_trigrams": "ngram",
               "tfidf_top_terms": "term", "tfidf_variant_comparison": "term", "key_terms": "term"}


def looks_sensitive(term):
    """Precautionary pattern check (links, e-mail, WhatsApp domains, long digit runs). Not a PII detector."""
    text = str(term)
    return bool(_SENSITIVE_TERM_RE.search(text)) or sum(c.isdigit() for c in text) >= _MIN_PHONE_DIGITS


def _drop_sensitive(frame, column):
    if frame.empty or column not in frame:
        return frame, 0
    mask = frame[column].astype(str).map(looks_sensitive)
    return frame.loc[~mask], int(mask.sum())


def single_message_terms(tfidf_top_terms, min_messages):
    """Terms whose document frequency in the primary (all-messages) variant is
    below min_messages."""
    if tfidf_top_terms.empty:
        return set()
    primary = tfidf_top_terms[tfidf_top_terms["variant"] == "all"]
    return set(primary.loc[primary["df"] < min_messages, "term"])


def prepare_display_tables(tables, min_messages=2, show_single_message_terms=False):
    """Return (display_tables, notice) for the NLP-related tables.

    display_tables holds filtered copies; `notice` reports how many rows were
    hidden per reason so the UI can say so. Non-NLP tables pass through
    unchanged (they contain no terms)."""
    out, hidden_single, hidden_pattern = dict(tables), 0, 0
    single_terms = single_message_terms(tables.get("tfidf_top_terms", pd.DataFrame()), min_messages)

    for name in NGRAM_TABLES:
        frame = tables.get(name)
        if frame is None or frame.empty:
            continue
        if not show_single_message_terms and "msgs_all" in frame:
            keep = frame["msgs_all"] >= min_messages
            hidden_single += int((~keep).sum())
            frame = frame.loc[keep]
        frame, dropped = _drop_sensitive(frame, TERM_COLUMN[name])
        hidden_pattern += dropped
        out[name] = frame.reset_index(drop=True)

    for name in ("tfidf_top_terms", "tfidf_variant_comparison"):
        frame = tables.get(name)
        if frame is None or frame.empty:
            continue
        if not show_single_message_terms:
            keep = ~frame["term"].isin(single_terms)
            hidden_single += int((~keep).sum())
            frame = frame.loc[keep]
        frame, dropped = _drop_sensitive(frame, TERM_COLUMN[name])
        hidden_pattern += dropped
        out[name] = frame.reset_index(drop=True)

    frame = tables.get("key_terms")                      # Key Terms: same single-message rule as the n-gram tables
    if frame is not None and not frame.empty:
        if not show_single_message_terms:
            keep = frame["messages_containing"] >= min_messages
            hidden_single += int((~keep).sum())
            frame = frame.loc[keep]
        frame, dropped = _drop_sensitive(frame, TERM_COLUMN["key_terms"])
        hidden_pattern += dropped
        out["key_terms"] = frame.reset_index(drop=True)

    notice = {"min_messages": min_messages, "shown_single_message_terms": show_single_message_terms,
              "rows_hidden_single_message": hidden_single, "rows_hidden_sensitive_pattern": hidden_pattern}
    return out, notice
