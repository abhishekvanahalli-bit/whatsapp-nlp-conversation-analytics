"""
Parsing and preprocessing foundation for the WhatsApp NLP project.
Parses a bracketed WhatsApp .txt export (default: the fictional data/sample_chat.txt) into a
validated pandas DataFrame, adds date/time features, and applies baseline
(non-aggressive) text cleaning + whitespace tokenization + stopword removal.

Supported export format (and ONLY this format):

    [M/D/YY, H:MM:SS AM/PM] Sender: message          (user rows)
    [M/D/YY, H:MM:SS AM/PM] - system text            (system rows, "- " style)
    [M/D/YY, H:MM:SS AM/PM] system text              (system rows without a sender)
    optional untimed first line (encryption notice), continuation lines

Dates are read as Month/Day/Year. The format assumptions were confirmed on the
development export and are exercised by synthetic fixtures in tests/fixtures/
(including iOS-style conventions such as invisible marks before the bracket and
sender-less system lines). Android "date, time - Sender: text" exports, 24-hour
clocks, timestamps without seconds, 4-digit years and Day/Month dates are NOT
supported (docs/supported_formats.md).
"""

import re
import string
import unicodedata
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHAT_PATH = PROJECT_ROOT / "data" / "sample_chat.txt"   # fictional; a private export is passed explicitly

# Confirmed format: [M/D/YY, H:MM:SS AM/PM] <rest>
# - Month/day are not zero-padded, year is 2-digit, plain ASCII space before AM/PM
#   (verified: no narrow no-break space / NBSP in this export).
LINE_START_RE = re.compile(
    r"^\[(\d{1,2})/(\d{1,2})/(\d{2}), (\d{1,2}):(\d{2}):(\d{2})\s?([AP]M)\] (.*)$"
)

# Confirmed: system/notification lines use "] - <text>" (space-hyphen-space),
# never "Sender: message". This must be checked BEFORE splitting on ": ",
# because at least one real system line ("...changed settings: only admins
# can send messages") contains a colon inside the system text itself.
SYSTEM_PREFIX = "- "

# Known non-text placeholders. Placeholder rows are kept as media rows and never enter the NLP corpus
# (a caption written on the same row is therefore not analysed either).
#   Bracketed placeholders  <image omitted>, <Media omitted>, <unknown message>, <album message>,
#       <attached: 0001-PHOTO.jpg> are unambiguous markers added by WhatsApp: a message CONTAINING one is media.
#   Bare placeholders       "image omitted", "sticker omitted", "Missed voice call" (iOS wording) are ordinary words
#       too, so a row is a placeholder only when the WHOLE message (after removing invisible marks and outer
#       whitespace) matches. Text that merely mentions them ("I said image omitted yesterday") stays text.
_KINDS = r"(?P<kind>image|photo|video|audio|sticker|gif|document|contact card|media|voice message|ptt)"
BRACKETED_PATTERNS = (
    (re.compile(r"<" + _KINDS + r" omitted>", re.IGNORECASE), None),     # kind taken from the match
    (re.compile(r"<unknown message>", re.IGNORECASE), "unknown"),
    (re.compile(r"<album message>", re.IGNORECASE), "album"),
    (re.compile(r"<attached: [^<>\n]{1,200}>", re.IGNORECASE), "attachment"),
)
BARE_PATTERNS = (
    (re.compile(_KINDS + r" omitted", re.IGNORECASE), None),
    (re.compile(r"(?:missed )?(?:voice|video) call(?:, [\w :.]{1,30})?", re.IGNORECASE), "call"),
)
MEDIA_PATTERNS = BRACKETED_PATTERNS + BARE_PATTERNS
_KIND_LABELS = {"photo": "image", "ptt": "audio", "voice message": "audio", "contact card": "contact"}
# Deleted-message placeholders (Android and iOS wording, optional leading symbol such as a prohibition sign).
_DELETED_RE = re.compile(r"^[^\w<\n]{0,3}\s*(this message was deleted|you deleted this message)", re.IGNORECASE)

# Invisible Unicode control marks WhatsApp inserts around some messages
# (confirmed: U+200E appears 5 times in this file, always before link text).
# U+200F is included defensively for other locales/exports but was NOT
# observed in this dataset.
INVISIBLE_MARKS = ("\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
                   "\u2066", "\u2067", "\u2068", "\u2069", "\ufeff")
_INVISIBLE_CHARS = "".join(INVISIBLE_MARKS)

# A hand-maintained standard English stopword list (comparable in coverage to
# NLTK's English stopword corpus), included directly as a literal set so Day 1
# has no external download dependency. This is deliberately English-only:
# the chat also contains Marathi/Hindi (Devanagari) text, and no validated
# Marathi stopword resource is used here — documented as a Day 1 limitation.
STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are aren't as at be
    because been before being below between both but by can't cannot could
    couldn't did didn't do does doesn't doing don't down during each few for
    from further had hadn't has hasn't have haven't having he he'd he'll
    he's her here here's hers herself him himself his how how's i i'd i'll
    i'm i've if in into is isn't it it's its itself let's me more most
    mustn't my myself no nor not of off on once only or other ought our ours
    ourselves out over own same shan't she she'd she'll she's should
    shouldn't so some such than that that's the their theirs them
    themselves then there there's these they they'd they'll they're they've
    this those through to too under until up very was wasn't we we'd we'll
    we're we've were weren't what what's when when's where where's which
    while who who's whom why why's with won't would wouldn't you you'd
    you'll you're you've your yours yourself yourselves
    """.split()
)


# A sender-less line is a system event. A "Name: text" shape is NOT a user message when the part before
# the colon reads like a system sentence (e.g. 'Asha changed the subject from "A: B" to ...').
_SYSTEM_VERB_RE = re.compile(
    r"\b(added|removed|left|joined|created|changed|deleted|turned|updated|pinned|unpinned|invited|reset)\b",
    re.IGNORECASE)


def looks_like_system_sentence(candidate_sender):
    """True when the text before ': ' is probably a system event, not a participant name.
    Conservative: needs a system verb AND (four or more words OR a quotation mark)."""
    return bool(_SYSTEM_VERB_RE.search(candidate_sender)) and (
        len(candidate_sender.split()) >= 4 or any(q in candidate_sender for q in "\u201c\u201d\"\u2018\u2019"))


def strip_invisible(text):
    return text.translate({ord(c): None for c in _INVISIBLE_CHARS})


def parse_chat(filepath=DEFAULT_CHAT_PATH):
    """Parse the raw WhatsApp export into (entries, parsing_failures).

    Every raw line is classified as exactly one of:
      - header : pre-timestamp WhatsApp notice at the very top of the file
      - system : timestamped lines "] - text" or "] text" (no sender): security-code
                 changes, member added/left, group changes, encryption notices
      - user   : "] Sender: message" lines
    Invisible direction marks before the bracket (U+200E and similar, common in iOS
    exports) are ignored when detecting a new row. Any line that does NOT start a
    new timestamp is treated as a continuation of the previous message (joined with
    "\n"), because real exports contain multi-line messages with internal blank lines.
    Lines before the first row that are not the first line are logged as parsing
    failures (never silently dropped).
    """
    with open(filepath, "r", encoding="utf-8") as f:
        raw_lines = f.read().replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while raw_lines and raw_lines[-1] == "":        # the file's final newline is not part of the last message
        raw_lines.pop()

    entries = []
    parsing_failures = []
    current = None

    for idx, raw_line in enumerate(raw_lines):
        match = LINE_START_RE.match(raw_line.lstrip(_INVISIBLE_CHARS))
        if match:
            if current is not None:
                entries.append(current)
            mm, dd, yy, hh, minute, ss, meridiem, rest = match.groups()
            rest = rest.lstrip(_INVISIBLE_CHARS)

            if rest.startswith(SYSTEM_PREFIX):
                sender = None
                message = rest[len(SYSTEM_PREFIX):]
                message_type = "system"
            elif ": " in rest and not looks_like_system_sentence(rest.split(": ", 1)[0]):
                sender, message = rest.split(": ", 1)
                message_type = "user"
            else:                                   # sender-less timestamped line = system event
                sender = None
                message = rest
                message_type = "system"

            current = {
                "line_start": idx + 1,
                "line_end": idx + 1,
                "date_str": f"{mm}/{dd}/{yy}",
                "time_str": f"{hh}:{minute}:{ss} {meridiem}",
                "sender": sender,
                "message_type": message_type,
                "message_lines": [message],
            }
        else:
            if current is None:
                if idx == 0:
                    # Standard WhatsApp encryption notice header — no timestamp.
                    entries.append(
                        {
                            "line_start": 1,
                            "line_end": 1,
                            "date_str": None,
                            "time_str": None,
                            "sender": None,
                            "message_type": "header",
                            "message_lines": [raw_line],
                        }
                    )
                else:
                    parsing_failures.append((idx + 1, raw_line))
                continue
            current["message_lines"].append(raw_line)
            current["line_end"] = idx + 1

    if current is not None:
        entries.append(current)

    for entry in entries:
        entry["message"] = "\n".join(entry.pop("message_lines"))

    return entries, parsing_failures


def add_datetime_features(df):
    """Parse date_str/time_str into a real datetime and derive requested features.

    period = hour-range bucket ("14-15"), the standard convention for
    hour-of-day activity heatmaps. Chosen over restating AM/PM (already
    implicit in `hour`) because a bare AM/PM column would just duplicate
    information already in `hour` without adding analytical value.
    """
    combined = df["date_str"].fillna("") + " " + df["time_str"].fillna("")
    df["datetime"] = pd.to_datetime(
        combined, format="%m/%d/%y %I:%M:%S %p", errors="coerce"
    )
    # Rows with no date_str (the header row) correctly become NaT, not an error.

    df["year"] = df["datetime"].dt.year
    df["month"] = df["datetime"].dt.month
    df["day"] = df["datetime"].dt.day
    df["day_name"] = df["datetime"].dt.day_name()
    df["hour"] = df["datetime"].dt.hour
    df["minute"] = df["datetime"].dt.minute
    df["period"] = df["hour"].apply(
        lambda h: f"{int(h):02d}-{(int(h) + 1) % 24:02d}" if pd.notna(h) else None
    )
    return df


def classify_media(message):
    """Media / non-text placeholder type, or None (see BRACKETED_PATTERNS and BARE_PATTERNS)."""
    stripped = strip_invisible(message).strip()
    if not stripped:
        return None
    candidates = [(pattern.search(stripped), label) for pattern, label in BRACKETED_PATTERNS]
    if "\n" not in stripped:
        candidates += [(pattern.fullmatch(stripped), label) for pattern, label in BARE_PATTERNS]
    for m, label in candidates:
        if m:
            if label is not None:
                return label
            kind = m.group("kind").lower()
            return _KIND_LABELS.get(kind, kind)
    return None


def is_deleted_placeholder(message):
    return bool(_DELETED_RE.match(strip_invisible(message).strip()))


def add_content_flags(df):
    """Flag media, deletions, and forwards (whole-message placeholder patterns, see MEDIA_PATTERNS)."""
    df["media_type"] = df["message"].apply(classify_media)
    df["is_media"] = df["media_type"].notna()
    df["is_deleted"] = df["message"].apply(is_deleted_placeholder)
    df["is_forwarded"] = df["message"].apply(
        lambda m: strip_invisible(m).strip().startswith("[Forwarded]"))
    return df


def clean_text(text):
    """Baseline, non-aggressive text normalization.

    - strips invisible bidi marks (not linguistic content)
    - collapses embedded newlines/multi-space into single spaces
      (multi-line paragraph structure is preserved separately in `message`)
    - lowercases
    Punctuation itself is NOT stripped here (kept for any future
    sentence/punctuation-aware analysis); punctuation trimming happens only
    at the token level in `tokenize`.
    """
    if not text:
        return ""
    text = strip_invisible(text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


_QUOTE_MAP = {ord(c): "'" for c in "\u2018\u2019\u201a\u201b\u02bc\u2032"}
_QUOTE_MAP.update({ord(c): '"' for c in "\u201c\u201d\u201e\u201f\u2033"})


def normalise_punctuation(text):
    """Curly apostrophes become ' and curly double quotes become " so that, for example,
    don\u2019t and don't are the same token (and the English stopword list applies)."""
    return text.translate(_QUOTE_MAP)


def _is_edge_punct(ch):
    return ch in string.punctuation or unicodedata.category(ch).startswith("P")


def strip_token_edges(token):
    """Remove punctuation (ASCII and any Unicode punctuation category, e.g. the Devanagari
    danda U+0964/U+0965, curly quotes, ellipsis, dashes) from both ends of a token. Letters,
    digits, emoji and symbols are kept; punctuation INSIDE a token (e.g. don't) is kept."""
    start, end = 0, len(token)
    while start < end and _is_edge_punct(token[start]):
        start += 1
    while end > start and _is_edge_punct(token[end - 1]):
        end -= 1
    return token[start:end]


def tokenize(clean_message):
    """Baseline whitespace tokenization: normalise curly quotes, then strip punctuation at token edges."""
    if not clean_message:
        return []
    tokens = []
    for tok in normalise_punctuation(clean_message).split():
        tok = strip_token_edges(tok)
        if tok:
            tokens.append(tok)
    return tokens


def remove_stopwords(tokens):
    """Actual set-membership filtering (O(1) per token), not substring matching."""
    return [t for t in tokens if t not in STOPWORDS]


def build_dataset(filepath=DEFAULT_CHAT_PATH):
    entries, parsing_failures = parse_chat(filepath)
    df = pd.DataFrame(entries)
    df = add_datetime_features(df)
    df = add_content_flags(df)
    df["clean_message"] = df["message"].apply(clean_text)
    df["tokens"] = df["clean_message"].apply(tokenize)
    df["tokens_no_stopwords"] = df["tokens"].apply(remove_stopwords)
    return df, parsing_failures


def run_quality_checks(df, parsing_failures):
    report = {}
    report["total_rows"] = len(df)
    report["missing_values"] = df.isna().sum().to_dict()
    # tokens / tokens_no_stopwords are list-valued (unhashable), so duplicate
    # detection runs on the substantive scalar columns instead.
    dedup_cols = ["date_str", "time_str", "sender", "message_type", "message"]
    report["duplicate_rows"] = int(df.duplicated(subset=dedup_cols).sum())
    report["empty_messages"] = int((df["message"].fillna("").str.strip() == "").sum())
    report["invalid_timestamps"] = int(df["datetime"].isna().sum())
    report["parsing_failures_count"] = len(parsing_failures)
    report["parsing_failures"] = parsing_failures

    user_senders = df.loc[df["message_type"] == "user", "sender"].value_counts()
    report["unique_senders"] = user_senders.to_dict()
    suspicious = [
        s
        for s in user_senders.index
        if (":" in s) or ("changed settings" in s) or (" added " in s)
    ]
    report["unexpected_users"] = suspicious

    lengths = df["message"].fillna("").str.len()
    threshold = float(lengths.mean() + 3 * lengths.std())
    long_mask = lengths > threshold
    report["long_message_threshold_chars"] = threshold
    report["unusually_long_messages_count"] = int(long_mask.sum())
    report["unusually_long_messages_examples"] = df.loc[
        long_mask, ["line_start", "sender", "message"]
    ].to_dict("records")

    return report


def save_processed_csv(df, out_path=PROJECT_ROOT / "results" / "processed_chat.csv"):
    out_df = df.copy()
    out_df["tokens"] = out_df["tokens"].apply(" ".join)
    out_df["tokens_no_stopwords"] = out_df["tokens_no_stopwords"].apply(" ".join)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    dataset, failures = build_dataset()
    quality_report = run_quality_checks(dataset, failures)
    saved_path = save_processed_csv(dataset)
    print(f"Parsed {len(dataset)} entries, saved to {saved_path}")
    print(f"Parsing failures: {quality_report['parsing_failures_count']}")
