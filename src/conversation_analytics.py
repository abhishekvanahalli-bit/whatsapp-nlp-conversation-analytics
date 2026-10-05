"""
Day 2, Milestone 4: Conversation Analytics (design: docs/conversation_analytics_design.md).

Descriptive structure/activity counts over the parsed chat. Every output is a
count or a count with its denominator; nothing here is a statistical claim
about people or generalisable behaviour.

Approved scope
  IMPLEMENT : row composition, daily activity timeline, repetition analysis,
              forwarded metadata, media/deleted/URL counts, system-message
              categories (generic labels only)
  LIMITED   : sender counts, hour-of-day histogram, weekday table, text-length
              summary (small descriptive tables only)
  EXCLUDED  : morning/afternoon/evening/night periods, message length over time,
              per-sender comparisons, reply networks

Privacy rules (enforced by tests/test_conversation_analytics.py)
- processed_chat.csv and data/chat.txt are only READ.
- No raw sender, message text, system-message text, phone number, name or URL
  is written. Repeated messages appear only as anonymous template ids (T1..Tn).
- Senders become Participant_N (first appearance across ALL user rows). This
  scheme is independent of the NLP corpus' Sender_N labels; no crosswalk to
  real identities (or to Sender_N) is created or written.
- System-message text is reduced to four generic category labels.
- Timestamps are used exactly as written in the export; no time zone is
  claimed (it is unverified).
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from csv_io import read_csv_typed  # noqa: E402
from ngram_analysis import (  # noqa: E402  (existing, tested analysis layer)
    PHONE_TOKEN,
    PROCESSED_CSV,
    RESULTS_DIR,
    URL_TOKEN,
    build_analysis_corpus,
)

SYSTEM_CATEGORIES = ("security_code_changed", "member_added", "settings_changed",
                     "other_system_event")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
PARTICIPANT_PREFIX = "Participant_"
TIMEZONE_NOTE = "timestamps used as written in the export; time zone not verified"

OUTPUT_FILES = (
    "analytics_row_composition.csv",
    "analytics_metadata_counts.csv",
    "analytics_daily_activity.csv",
    "analytics_repetition_summary.csv",
    "analytics_repetition_groups.csv",
    "analytics_sender_counts.csv",
    "analytics_hour_histogram.csv",
    "analytics_weekday_table.csv",
    "analytics_text_length_summary.csv",
    "analytics_run_metadata.json",
)


# ------------------------------------------------------------ classification ---
def user_row_kind(df):
    """text / media / deleted for user rows, '' for all other rows.
    Media and deleted are mutually exclusive in the parsed data (checked in
    reconciliation); media wins if that ever changed."""
    kind = np.where(df["is_media"], "media", np.where(df["is_deleted"], "deleted", "text"))
    return pd.Series(np.where(df["message_type"] == "user", kind, ""), index=df.index)


def system_category(message):
    """Map a system message to one of four generic labels. The text itself is
    never stored (it can contain phone numbers and personal names)."""
    m = str(message).lower()
    if "security code changed" in m:
        return "security_code_changed"
    if re.search(r"\b(added|joined)\b", m):
        return "member_added"
    if ("changed settings" in m or "changed this group's settings" in m
            or re.search(r"changed (the|this) group('s)? (name|subject|description|icon)", m)
            or re.search(r"changed the subject", m)):
        return "settings_changed"
    return "other_system_event"


def assign_participants(senders):
    """Participant_1, Participant_2, ... in order of first appearance.
    Missing senders stay missing. Only the pseudonym list is returned: the
    sender->pseudonym mapping is deliberately not kept or written anywhere."""
    mapping, out = {}, []
    for s in senders:
        if pd.isna(s):
            out.append(None)
            continue
        if s not in mapping:
            mapping[s] = f"{PARTICIPANT_PREFIX}{len(mapping) + 1}"
        out.append(mapping[s])
    return out


def _clean_raw(text):
    """Raw text normalisation used only to compare messages for exact
    repetition (invisible LRM mark and outer whitespace ignored)."""
    return str(text).replace("‎", "").strip()


# ------------------------------------------------------------------ prepare ---
def prepare(df):
    """Working frame (never written) with derived columns."""
    d = df.copy()
    d["kind"] = user_row_kind(d)
    d["dt"] = pd.to_datetime(d["datetime"], errors="coerce")
    d["date"] = d["dt"].dt.normalize()
    d["participant"] = assign_participants(d["sender"].where(d["message_type"] == "user"))
    d["sys_cat"] = [system_category(m) if t == "system" else ""
                    for m, t in zip(d["message"], d["message_type"])]
    d["deleted_by_admin"] = d["is_deleted"] & d["message"].astype(str).str.contains(
        "deleted by admin", case=False, regex=False)
    return d


def _count_table(group, series, denominator, label, order=None):
    counts = series.value_counts()
    cats = list(order) if order is not None else sorted(counts.index, key=lambda c: (-counts[c], c))
    return pd.DataFrame({"group": group, "category": cats,
                         "count": [int(counts.get(c, 0)) for c in cats],
                         "denominator": denominator, "denominator_label": label})


# ------------------------------------------------------- IMPLEMENT: tables ---
def row_composition_table(d):
    user, media = d[d["message_type"] == "user"], d[d["kind"] == "media"]
    system = d[d["message_type"] == "system"]
    parts = [
        _count_table("parsed_rows", d["message_type"], len(d), "parsed rows",
                     order=["header", "system", "user"]),
        _count_table("user_rows", user["kind"], len(user), "user rows",
                     order=["text", "media", "deleted"]),
        _count_table("media_type", media["media_type"], len(media), "media rows"),
        _count_table("system_category", system["sys_cat"], len(system), "system rows",
                     order=SYSTEM_CATEGORIES),
    ]
    return pd.concat(parts, ignore_index=True)


def daily_activity_table(d):
    """Zero-filled calendar from first to last timestamp; one row per date."""
    stamped = d[d["date"].notna()]
    if stamped.empty:                                     # no valid timestamps: empty, not an error
        return pd.DataFrame(columns=["date", "weekday", "text_messages", "media_rows",
                                     "deleted_rows", "system_rows", "total_rows", "is_active"])
    calendar = pd.date_range(stamped["date"].min(), stamped["date"].max(), freq="D")
    label = np.where(stamped["message_type"] == "system", "system", stamped["kind"])
    counts = (pd.crosstab(stamped["date"], pd.Series(label, index=stamped.index))
              .reindex(calendar, fill_value=0)
              .reindex(columns=["text", "media", "deleted", "system"], fill_value=0))
    counts = counts.rename(columns={"text": "text_messages", "media": "media_rows",
                                    "deleted": "deleted_rows", "system": "system_rows"})
    out = counts.reset_index().rename(columns={"index": "date"})
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out.insert(1, "weekday", [WEEKDAYS[i] for i in calendar.dayofweek])
    out["total_rows"] = counts.sum(axis=1).values
    out["is_active"] = out["total_rows"] > 0
    return out


def repetition_tables(d, corpus):
    """Repetition over the conversational text messages. Nothing is removed.
    exact  = identical raw text
    template = identical text after URL/phone masking and marker removal
    Groups are anonymous ids T1..Tn (order of first occurrence); no text."""
    c = corpus.merge(d[["line_start", "message", "date"]], on="line_start", how="left")
    c["raw_norm"] = c["message"].map(_clean_raw)
    c["template"] = c["text_masked"]
    n = len(c)
    unique_texts = c["template"].nunique()

    exact_sizes = c["raw_norm"].value_counts()
    exact_groups = exact_sizes[exact_sizes > 1]
    tmpl_sizes = c["template"].value_counts()

    rows, tid = [], 0
    for tmpl in c["template"].drop_duplicates():          # first-occurrence order
        g = c[c["template"] == tmpl]
        if len(g) < 2:
            continue
        tid += 1
        rows.append({
            "template_id": f"T{tid}",
            "occurrences": len(g),
            "repeat_messages": len(g) - 1,
            "distinct_raw_texts": g["raw_norm"].nunique(),
            "exact_raw_identical": bool(g["raw_norm"].nunique() == 1),
            "contains_url": bool(g["tokens"].apply(lambda t: URL_TOKEN in t).all()),
            "forwarded_messages": int(g["is_forwarded"].sum()),
            "first_date": g["date"].min().strftime("%Y-%m-%d"),
            "last_date": g["date"].max().strftime("%Y-%m-%d"),
            "active_dates": g["date"].nunique(),
        })
    groups = pd.DataFrame(rows, columns=[
        "template_id", "occurrences", "repeat_messages", "distinct_raw_texts",
        "exact_raw_identical", "contains_url", "forwarded_messages", "first_date",
        "last_date", "active_dates"])

    exact_repeats = int((exact_groups - 1).sum())
    template_repeats = int((tmpl_sizes[tmpl_sizes > 1] - 1).sum())
    summary = pd.DataFrame([
        ("text_messages", n, n, "text messages"),
        ("unique_texts_after_masking", unique_texts, n, "text messages"),
        ("repeat_messages_after_masking", template_repeats, n, "text messages"),
        ("template_groups", len(groups), unique_texts, "unique texts"),
        ("largest_template_group_size", int(tmpl_sizes.max()) if n else 0, n, "text messages"),
        ("exact_raw_duplicate_groups", len(exact_groups), n, "text messages"),
        ("exact_raw_repeat_messages", exact_repeats, n, "text messages"),
        ("repeats_visible_only_after_masking", template_repeats - exact_repeats,
         template_repeats, "repeat messages after masking"),
    ], columns=["metric", "count", "denominator", "denominator_label"])
    return summary, groups, c


def metadata_counts_table(d, corpus):
    """Forwarded / deleted / media / URL counts, each with its denominator."""
    user = d[d["message_type"] == "user"]
    text, media, deleted = (user[user["kind"] == k] for k in ("text", "media", "deleted"))
    fwd = user[user["is_forwarded"]]
    dl_dates = deleted["date"].value_counts()
    dl_seconds = deleted["dt"].value_counts()
    rows = [
        ("forwarded_user_rows", len(fwd), len(user), "user rows"),
        ("forwarded_text_messages", int((fwd["kind"] == "text").sum()), len(text), "text messages"),
        ("forwarded_media_rows", int((fwd["kind"] == "media").sum()), len(media), "media rows"),
        ("forwarded_deleted_rows", int((fwd["kind"] == "deleted").sum()), len(deleted), "deleted rows"),
        ("non_forwarded_text_messages", int((text["is_forwarded"] == False).sum()),  # noqa: E712
         len(text), "text messages"),
        ("deleted_rows", len(deleted), len(user), "user rows"),
        ("deleted_by_admin_rows", int(deleted["deleted_by_admin"].sum()), len(deleted), "deleted rows"),
        ("dates_with_deleted_rows", int(len(dl_dates)), len(deleted), "deleted rows"),
        ("max_deleted_rows_on_one_date", int(dl_dates.max()) if len(dl_dates) else 0,
         len(deleted), "deleted rows"),
        ("max_deleted_rows_in_one_second", int(dl_seconds.max()) if len(dl_seconds) else 0,
         len(deleted), "deleted rows"),
        ("media_rows", len(media), len(user), "user rows"),
        ("album_rows", int((media["media_type"] == "album").sum()), len(media), "media rows"),
        ("text_messages_with_url", int(corpus["tokens"].apply(lambda t: URL_TOKEN in t).sum()),
         len(corpus), "text messages"),
        ("text_messages_with_phone_pattern",
         int(corpus["tokens"].apply(lambda t: PHONE_TOKEN in t).sum()), len(corpus), "text messages"),
    ]
    return pd.DataFrame(rows, columns=["metric", "count", "denominator", "denominator_label"])


# ------------------------------------------------- LIMITED: small tables ---
def sender_counts_table(d):
    """Descriptive counts per pseudonym. No shares, rankings or comparisons."""
    user = d[d["message_type"] == "user"]
    if user.empty:
        return pd.DataFrame(columns=["participant_id", "user_rows", "text_messages", "media_rows",
                                     "deleted_rows", "forwarded_rows", "of_user_rows"])
    g = user.groupby("participant")
    out = pd.DataFrame({
        "user_rows": g.size(),
        "text_messages": g["kind"].apply(lambda s: int((s == "text").sum())),
        "media_rows": g["kind"].apply(lambda s: int((s == "media").sum())),
        "deleted_rows": g["kind"].apply(lambda s: int((s == "deleted").sum())),
        "forwarded_rows": g["is_forwarded"].sum().astype(int),
    })
    out["of_user_rows"] = len(user)
    out = out.reset_index().rename(columns={"participant": "participant_id"})
    out["_n"] = out["participant_id"].str.replace(PARTICIPANT_PREFIX, "", regex=False).astype(int)
    return out.sort_values("_n").drop(columns="_n").reset_index(drop=True)


def hour_histogram_table(d):
    stamped = d[d["dt"].notna()]
    hours = stamped["dt"].dt.hour
    out = pd.DataFrame({"hour_as_exported": range(24)})
    for name, mask in (("user_rows", stamped["message_type"] == "user"),
                       ("system_rows", stamped["message_type"] == "system")):
        out[name] = out["hour_as_exported"].map(hours[mask].value_counts()).fillna(0).astype(int)
    return out


def weekday_table(d):
    """Per weekday: calendar days in the observed range, active dates, and row
    counts. Shows how few occurrences each weekday has; not a pattern claim."""
    stamped = d[d["dt"].notna()]
    if stamped.empty:
        calendar = pd.DatetimeIndex([])
    else:
        calendar = pd.date_range(stamped["date"].min(), stamped["date"].max(), freq="D")
    rows = []
    for i, name in enumerate(WEEKDAYS):
        sel = stamped[stamped["dt"].dt.dayofweek == i]
        rows.append({
            "weekday": name,
            "calendar_days_in_range": int((calendar.dayofweek == i).sum()),
            "active_dates": int(sel["date"].nunique()),
            "user_rows": int((sel["message_type"] == "user").sum()),
            "system_rows": int((sel["message_type"] == "system").sum()),
        })
    return pd.DataFrame(rows)


def text_length_summary_table(corpus):
    """Length of the masked text (characters) and token count (all tokens,
    stopwords and placeholders included). Summary statistics only."""
    if corpus.empty:                                      # zero text messages: NaN statistics, n = 0
        return pd.DataFrame([{"measure": m, "n": 0, "min": np.nan, "q25": np.nan, "median": np.nan,
                              "q75": np.nan, "max": np.nan, "mean": np.nan}
                             for m in ("characters_masked_text", "tokens")])
    measures = {"characters_masked_text": corpus["text_masked"].str.len(),
                "tokens": corpus["tokens"].apply(len)}
    rows = []
    for name, s in measures.items():
        rows.append({"measure": name, "n": int(s.count()), "min": float(s.min()),
                     "q25": float(s.quantile(0.25)), "median": float(s.median()),
                     "q75": float(s.quantile(0.75)), "max": float(s.max()),
                     "mean": round(float(s.mean()), 2)})
    return pd.DataFrame(rows)


# -------------------------------------------------------- reconciliation ---
def reconciliation_checks(d, tables, summary, groups, tfidf_meta=None):
    """Every check is (name, left, right, passed). All must pass before any
    output is written."""
    comp = tables["composition"].set_index(["group", "category"])["count"]
    user = d[d["message_type"] == "user"]
    stamped = d[d["dt"].notna()]
    sm = summary.set_index("metric")["count"]
    meta = tables["metadata"].set_index("metric")["count"]
    daily, senders = tables["daily"], tables["senders"]
    checks = []

    def add(name, left, right):
        checks.append({"check": name, "left": int(left), "right": int(right),
                       "passed": bool(left == right)})

    add("header+system+user == parsed rows",
        comp[("parsed_rows", "header")] + comp[("parsed_rows", "system")]
        + comp[("parsed_rows", "user")], len(d))
    add("text+media+deleted == user rows",
        comp[("user_rows", "text")] + comp[("user_rows", "media")]
        + comp[("user_rows", "deleted")], len(user))
    add("media and deleted are mutually exclusive", int((user["is_media"] & user["is_deleted"]).sum()), 0)
    add("media types sum == media rows",
        tables["composition"].query("group == 'media_type'")["count"].sum(),
        comp[("user_rows", "media")])
    add("system categories sum == system rows",
        tables["composition"].query("group == 'system_category'")["count"].sum(),
        comp[("parsed_rows", "system")])
    add("unique+repeat == text messages",
        sm["unique_texts_after_masking"] + sm["repeat_messages_after_masking"], sm["text_messages"])
    add("text messages agree with composition", sm["text_messages"], comp[("user_rows", "text")])
    add("template group sizes reproduce repeat count",
        groups["occurrences"].sum() - len(groups), sm["repeat_messages_after_masking"])
    add("sender user rows sum == user rows", senders["user_rows"].sum(), len(user))
    add("sender text messages sum == text messages", senders["text_messages"].sum(), comp[("user_rows", "text")])
    add("sender media rows sum == media rows", senders["media_rows"].sum(), comp[("user_rows", "media")])
    add("sender deleted rows sum == deleted rows", senders["deleted_rows"].sum(), comp[("user_rows", "deleted")])
    add("sender forwarded rows sum == forwarded rows", senders["forwarded_rows"].sum(),
        meta["forwarded_user_rows"])
    add("forwarded text+media+deleted == forwarded rows",
        meta["forwarded_text_messages"] + meta["forwarded_media_rows"] + meta["forwarded_deleted_rows"],
        meta["forwarded_user_rows"])
    add("forwarded+non-forwarded text == text messages",
        meta["forwarded_text_messages"] + meta["non_forwarded_text_messages"], comp[("user_rows", "text")])
    add("daily total rows == timestamped rows", daily["total_rows"].sum(), len(stamped))
    add("daily per-kind sums == kind totals",
        daily[["text_messages", "media_rows", "deleted_rows", "system_rows"]].sum().sum(), len(stamped))
    # rows with an unreadable timestamp cannot appear on the timeline; when every row has a valid
    # timestamp (the normal case) these expectations equal the overall totals
    def stamped_count(mask):
        return int((mask & d["dt"].notna()).sum())

    add("daily text == text messages", daily["text_messages"].sum(),
        stamped_count((d["message_type"] == "user") & (d["kind"] == "text")))
    add("daily media == media rows", daily["media_rows"].sum(),
        stamped_count((d["message_type"] == "user") & (d["kind"] == "media")))
    add("daily deleted == deleted rows", daily["deleted_rows"].sum(),
        stamped_count((d["message_type"] == "user") & (d["kind"] == "deleted")))
    add("daily system == system rows", daily["system_rows"].sum(),
        stamped_count(d["message_type"] == "system"))
    add("calendar days == active + empty dates",
        len(daily), int(daily["is_active"].sum()) + int((~daily["is_active"]).sum()))
    add("hour histogram sums == timestamped rows",
        tables["hour"][["user_rows", "system_rows"]].sum().sum(), len(stamped))
    add("weekday table sums == timestamped rows",
        tables["weekday"][["user_rows", "system_rows"]].sum().sum(), len(stamped))
    add("weekday calendar days == calendar length",
        tables["weekday"]["calendar_days_in_range"].sum(), len(daily))
    add("text length n == text messages", tables["length"]["n"].iloc[0], sm["text_messages"])
    if tfidf_meta is not None:
        v = tfidf_meta["variants"]
        add("TF-IDF primary N == text messages", v["all"]["n_documents_N"], sm["text_messages"])
        add("TF-IDF unique N == unique texts", v["unique"]["n_documents_N"], sm["unique_texts_after_masking"])
    return checks


# ------------------------------------------------------------------ driver ---
def _load_tfidf_meta(results_dir):
    p = Path(results_dir) / "tfidf_run_metadata.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def run_analytics(processed_csv=PROCESSED_CSV, results_dir=RESULTS_DIR, tfidf_dir=RESULTS_DIR):
    """Compute all approved tables, verify reconciliation, then write outputs.
    Raises AssertionError (and writes nothing) if any reconciliation fails.
    processed_chat.csv, n-gram and TF-IDF outputs are only read."""
    raw = read_csv_typed(processed_csv)
    d = prepare(raw)
    corpus = build_analysis_corpus(raw)
    summary, groups, _ = repetition_tables(d, corpus)
    tables = {
        "composition": row_composition_table(d),
        "metadata": metadata_counts_table(d, corpus),
        "daily": daily_activity_table(d),
        "senders": sender_counts_table(d),
        "hour": hour_histogram_table(d),
        "weekday": weekday_table(d),
        "length": text_length_summary_table(corpus),
    }
    checks = reconciliation_checks(d, tables, summary, groups, _load_tfidf_meta(tfidf_dir))
    failed = [c for c in checks if not c["passed"]]
    if failed:
        raise AssertionError(f"reconciliation failed: {failed}")

    stamped = d[d["dt"].notna()]
    limitations = []                                      # graceful limited results (zero-text / no dates)
    if len(corpus) == 0:
        limitations.append("no_text_messages")
    if stamped.empty:
        limitations.append("no_valid_timestamps")
    elif (d["message_type"].ne("header") & d["dt"].isna()).any():
        limitations.append("some_rows_have_unreadable_timestamps")
    metadata = {
        "design": "docs/conversation_analytics_design.md",
        "interpretation": "descriptive counts for this chat only; not generalisable",
        "timestamps": TIMEZONE_NOTE,
        "first_timestamp_as_exported": (None if stamped.empty
                                        else stamped["dt"].min().strftime("%Y-%m-%d %H:%M:%S")),
        "last_timestamp_as_exported": (None if stamped.empty
                                       else stamped["dt"].max().strftime("%Y-%m-%d %H:%M:%S")),
        "pseudonyms": "Participant_N by first appearance across all user rows; independent of "
                      "the pseudonyms used in the NLP outputs; no crosswalk created or written",
        "privacy": "no raw sender, message, system text, phone number, name or URL in outputs",
        "excluded_analyses": ["morning/afternoon/evening/night periods", "message length over time",
                              "per-sender comparisons", "reply network"],
        "n_reconciliation_checks": len(checks),
        "all_reconciliation_checks_passed": True,
        "reconciliation_checks": checks,
        "tfidf_cross_check": "included" if _load_tfidf_meta(tfidf_dir) else "skipped (no TF-IDF metadata)",
    }

    if limitations:                                       # keys only added when limited, so the
        metadata["limited_result"] = True                 # normal output is byte-identical to before
        metadata["limitation_reasons"] = limitations

    out = Path(results_dir)
    files = {
        "analytics_row_composition.csv": tables["composition"],
        "analytics_metadata_counts.csv": tables["metadata"],
        "analytics_daily_activity.csv": tables["daily"],
        "analytics_repetition_summary.csv": summary,
        "analytics_repetition_groups.csv": groups,
        "analytics_sender_counts.csv": tables["senders"],
        "analytics_hour_histogram.csv": tables["hour"],
        "analytics_weekday_table.csv": tables["weekday"],
        "analytics_text_length_summary.csv": tables["length"],
    }
    for name, frame in files.items():
        frame.to_csv(out / name, index=False, encoding="utf-8")
    (out / "analytics_run_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return {**tables, "repetition_summary": summary, "repetition_groups": groups}, metadata


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    res, meta = run_analytics()
    for name, frame in res.items():
        print(f"\n== {name} ==")
        print(frame.to_string(index=False))
    print(f"\nreconciliation checks passed: {meta['n_reconciliation_checks']}")
