"""The four dashboard pages. Every number comes from the current run's tables; nothing is hard-coded."""

import html

import pandas as pd
import streamlit as st

import charts
import ui
from display_privacy import prepare_display_tables

METADATA_LABELS = {
    "forwarded_user_rows": "Forwarded user rows",
    "forwarded_text_messages": "Forwarded text messages",
    "forwarded_media_rows": "Forwarded media rows",
    "forwarded_deleted_rows": "Forwarded deleted rows",
    "non_forwarded_text_messages": "Text messages that are not forwarded",
    "deleted_rows": "Deleted rows",
    "deleted_by_admin_rows": "Deleted by an admin",
    "dates_with_deleted_rows": "Dates with deleted rows",
    "max_deleted_rows_on_one_date": "Most deleted rows on one date",
    "max_deleted_rows_in_one_second": "Most deleted rows within one second",
    "media_rows": "Media rows",
    "album_rows": "Album rows",
    "text_messages_with_url": "Text messages containing a URL",
    "text_messages_with_phone_pattern": "Text messages containing a phone-number pattern",
}


# ------------------------------------------------------------------ small helpers ---
def _value(table, key_col, key, value_col="count", default=0):
    if table.empty or key not in set(table[key_col]):
        return default
    return int(table.loc[table[key_col] == key, value_col].iloc[0])


def _comp(run, group, category):
    t = run.tables["analytics_row_composition"]
    if t.empty:
        return 0
    m = t[(t["group"] == group) & (t["category"] == category)]
    return int(m["count"].iloc[0]) if len(m) else 0


def _parsed_rows(run):
    t = run.tables["analytics_row_composition"]
    m = t[t["group"] == "parsed_rows"]
    return int(m["denominator"].iloc[0]) if len(m) else 0


def _chart(fig, key, title=None, note=None, height=None):
    """Card: optional heading and note, then a Plotly chart, inside one white panel. The key must be unique
    (identical empty-state figures would otherwise collide)."""
    with ui.panel("chart-" + key):
        if title:
            ui.section(title, note)
        if height:
            fig.update_layout(height=height)
        st.plotly_chart(fig, key=key, theme=None, config={"displayModeBar": False})


def _show(frame, **kwargs):
    st.dataframe(frame, hide_index=True, **kwargs)


def _plain_number(value):
    """Counts read back from CSV may be floats (7.0); show whole numbers without the decimal."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _note(text):
    """One-line plain-English explanation placed directly under a heading or chart."""
    st.markdown(f"<div class='wa-section-note'>{html.escape(text)}</div>", unsafe_allow_html=True)


def _no_text_info(run):
    if run.info["n_text_messages"] == 0:
        st.info("This chat has no text messages (only media, system or deleted rows), so the text analyses "
                "are empty. The composition and activity views below still work.")


# ==================================================================== Overview ==
def _key_findings(run, display):
    """Plain sentences built only from this run's verified tables. Returns a list of strings."""
    findings = []
    n_user = _comp(run, "parsed_rows", "user")
    n_text, n_media, n_del = (_comp(run, "user_rows", k) for k in ("text", "media", "deleted"))
    if n_user:
        findings.append(f"Of {n_user:,} messages written by participants, {n_text:,} contain text, "
                        f"{n_media:,} are media and {n_del:,} are deleted.")
    daily = run.tables["analytics_daily_activity"]
    if not daily.empty and int(daily["total_rows"].sum()) > 0:
        top = daily.sort_values(["total_rows", "date"], ascending=[False, True]).iloc[0]
        findings.append(f"The busiest date ({top['date']}) has {int(top['total_rows']):,} of "
                        f"{int(daily['total_rows'].sum()):,} dated rows; {int(daily['is_active'].sum())} of "
                        f"{len(daily)} calendar day(s) have any activity.")
    rep = run.tables["analytics_repetition_summary"]
    if _value(rep, "metric", "text_messages") > 0:
        repeats = _value(rep, "metric", "repeat_messages_after_masking")
        groups = _value(rep, "metric", "template_groups")
        sentence = (f"{repeats:,} of {n_text:,} text messages repeat an earlier text, forming {groups} "
                    f"repeated template(s)." if repeats else "No text message repeats an earlier text.")
        uni = display.get("ngram_unigrams")
        if uni is not None and not uni.empty:
            top = uni.sort_values(["count_all", "ngram"], ascending=[False, True]).head(15)
            inflated = int((top["count_all"] > top["count_unique"]).sum())
            if inflated:
                sentence += (f" {inflated} of the {len(top)} most frequent terms occur more often in total than "
                             f"across distinct texts, so repeated messages raise their counts.")
        findings.append(sentence)
    mix = run.tables.get("script_mix_summary")
    if mix is not None and not mix.empty:
        m = mix[mix["variant"] == "all"].set_index("message_class")
        total = int(m["denominator"].iloc[0])
        if total:
            findings.append(f"Script Mix: {int(m.loc['latin_only', 'messages'])} of {total} text messages use Latin "
                            f"script only, {int(m.loc['devanagari_only', 'messages'])} use Devanagari only and "
                            f"{int(m.loc['mixed_script', 'messages'])} contain characters from more than one writing "
                            f"system. This describes writing systems, not languages.")
    kt = display.get("key_terms")
    if kt is not None and not kt.empty:
        top = kt.sort_values(["unique_texts_containing", "term"], ascending=[False, True]).iloc[0]
        unique = _value(rep, "metric", "unique_texts_after_masking")
        findings.append(f"The term found in the most distinct messages is “{top['term']}” "
                        f"({int(top['unique_texts_containing'])} of {unique} unique texts).")
    return findings[:4]                                         # short: four bullets at most


def _status_html(run):
    return ui.badge("Current run: " + run.filename, "ok")


def _status_badges(run, extra=()):
    """Header badge row: analysis state plus the run's size, from the run's own tables."""
    daily = run.tables["analytics_daily_activity"]
    active = int(daily["is_active"].sum()) if not daily.empty else 0
    chips = [ui.badge("Analysis ready", "ok"),
             ui.badge(f"{run.info['n_rows']:,} parsed rows"),
             ui.badge(f"{run.info['n_text_messages']:,} text messages"),
             ui.badge(f"{active} active calendar day(s)")]
    return " ".join(chips + list(extra))


def render_overview(run, config):
    info = run.info
    rep = run.tables["analytics_repetition_summary"]
    n_text = info["n_text_messages"]
    daily = run.tables["analytics_daily_activity"]
    active = int(daily["is_active"].sum()) if not daily.empty else 0

    n_checks = run.analytics_meta.get("n_reconciliation_checks", 0)
    extra = [ui.badge(f"All {n_checks} consistency checks passed", "ok")
             if run.analytics_meta.get("all_reconciliation_checks_passed")
             else ui.badge("Consistency checks did not all pass", "warn")]
    if n_text < config.small_chat_text_messages:
        extra.append(ui.badge(f"Small dataset: {n_text} text messages", "warn"))
    ui.page_header(ui.PROJECT_TITLE, ui.PROJECT_DESCRIPTION, _status_badges(run, extra), _status_html(run))
    _no_text_info(run)

    ui.kpi_cards([
        ("Total Messages", _comp(run, "parsed_rows", "user"), "Written by participants (text, media, deleted)"),
        ("Participants", len(run.tables["analytics_sender_counts"]), "Pseudonymised; counts only"),
        ("Text Messages", _comp(run, "user_rows", "text"), "Messages with text: the base for NLP"),
        ("Media / Deleted", f"{_comp(run, 'user_rows', 'media'):,} / {_comp(run, 'user_rows', 'deleted'):,}",
         "Media placeholders / deleted messages"),
        ("Active Days", active, f"of {len(daily)} calendar day(s) in the export"),
    ])

    display, _ = prepare_display_tables(run.tables, config.min_term_messages, False)
    left, right = st.columns([2, 1])
    with left:
        _chart(charts.daily_timeline_figure(daily), "ov_daily", "Daily Activity",
               "Rows per calendar date; empty dates show as gaps.", height=300)
    with right:
        _chart(charts.composition_figure(run.tables["analytics_row_composition"]), "ov_composition",
               "Message Composition", "What the exported rows consist of, before any text analysis.", height=300)

    c1, c2, c3 = st.columns(3)
    with c1:
        _chart(charts.key_terms_compact_figure(display["key_terms"], 6), "ov_keyterms", "Top Key Terms",
               "Terms in the most distinct messages (privacy filter applied).", height=260)
    with c2:
        _chart(charts.script_mix_figure(display["script_mix_summary"], "all"), "ov_script", "Script Mix",
               "Writing systems used; not language identification.", height=260)
    with c3:
        with ui.panel("ov-patterns"):
            ui.section("Conversation Patterns", "How much of the text repeats an earlier text.")
            if _value(rep, "metric", "text_messages") == 0:
                st.caption("No text messages, so there is no repetition to show.")
            else:
                ui.mini_stats([("Unique texts", _value(rep, "metric", "unique_texts_after_masking")),
                               ("Repeats", _value(rep, "metric", "repeat_messages_after_masking")),
                               ("Templates", _value(rep, "metric", "template_groups"))])
                fig = charts.unique_vs_repeated_figure(rep)
                fig.update_layout(height=190)
                st.plotly_chart(fig, key="ov_patterns_chart", theme=None, config={"displayModeBar": False})

    left, right = st.columns([2, 1])
    with left:
        ui.findings_card(_key_findings(run, display))
    with right:
        ui.checklist_card("About This Analysis", [
            "Parsing & preprocessing", "N-gram analysis", "TF-IDF", "Conversation analytics", "Script Mix",
            "Key Terms", "Privacy-aware display"])

    with st.expander("Data, methods and limits"):
        left, right = st.columns(2)
        with left:
            st.markdown("**Data**")
            st.markdown(f"- File: `{run.filename}`\n"
                        f"- Parsed rows: {_parsed_rows(run):,} ({_comp(run, 'parsed_rows', 'system'):,} system, "
                        f"{_comp(run, 'parsed_rows', 'user'):,} user)\n"
                        f"- Unique text messages: {_value(rep, 'metric', 'unique_texts_after_masking'):,} "
                        f"(of {n_text:,} text messages)\n"
                        f"- Date range: {info['first_timestamp'][:10]} to {info['last_timestamp'][:10]}")
            st.caption(info["date_format_note"])
            st.caption(info["date_order_evidence"])
        with right:
            st.markdown("**Methods and limits**")
            st.markdown("- Parsing and preprocessing, then unigram, bigram and trigram counts, TF-IDF, Script Mix, "
                        "Key Terms and conversation analytics.\n"
                        "- Script Mix describes writing systems, not languages. No sentiment, emotion, entity or "
                        "language detection is performed.\n"
                        "- Participants appear as `Participant_N`; phone numbers, names, links and message text "
                        "are not shown. The uploaded file was processed in a temporary folder that has been deleted.")
    ui.footer_note()


# ================================================================= Conversation ==
def render_conversation(run, config):
    ui.page_header("Conversation", "Activity, composition and repetition patterns.", _status_badges(run),
                   _status_html(run))
    daily = run.tables["analytics_daily_activity"]
    summary = run.tables["analytics_repetition_summary"]
    _no_text_info(run)

    meta_counts = run.tables["analytics_metadata_counts"]
    ui.kpi_cards([
        ("Total Messages", _comp(run, "parsed_rows", "user"), "Written by participants"),
        ("Participants", len(run.tables["analytics_sender_counts"]), "Pseudonymised; counts only"),
        ("Forwarded Messages", _value(meta_counts, "metric", "forwarded_user_rows"), "User rows marked as forwarded"),
        ("Messages With Links", _value(meta_counts, "metric", "text_messages_with_url"), "Text messages containing a link"),
        ("Repeat Messages", _value(summary, "metric", "repeat_messages_after_masking"), "Repeat an earlier text"),
    ])

    _chart(charts.daily_timeline_figure(daily), "cv_daily", "Conversation Activity",
           "Rows per calendar date, stacked by kind. Times are as recorded in the export (time zone unverified).",
           height=300)
    ui.explain(
        "Rows per calendar date, stacked by kind (text, media, deleted, system).",
        "Each row's recorded date is counted on a calendar that runs from the first to the last date, so "
        "dates with no rows appear as gaps.",
        "It shows when activity happened and whether it was concentrated on a few dates.",
        "Timestamps are as recorded in the export and the time zone is unverified. A few dates can "
        "dominate the scale, and no trend or cause can be inferred.")

    left, right = st.columns(2)
    with left:
        _chart(charts.composition_figure(run.tables["analytics_row_composition"]), "cv_composition",
               "Message Composition", "Each exported row is counted once as header, system or user, and user "
                                      "rows as text, media or deleted.", height=240)
    with right:
        with ui.panel("cv-repetition"):
            ui.section("Repetition Analysis", "How many text messages repeat an earlier text (details: Patterns page).")
            if _value(summary, "metric", "text_messages") == 0:
                st.caption("No text messages, so there is no repetition to show.")
            else:
                ui.mini_stats([("Text messages", _value(summary, "metric", "text_messages")),
                               ("Unique texts", _value(summary, "metric", "unique_texts_after_masking")),
                               ("Repeat messages", _value(summary, "metric", "repeat_messages_after_masking"))])
                fig = charts.unique_vs_repeated_figure(summary)
                fig.update_layout(height=170)
                st.plotly_chart(fig, key="cv_repetition", theme=None, config={"displayModeBar": False})

    ui.section("Secondary Statistics", "Smaller tables and charts that describe sample coverage, not habits.")
    t_hour, t_week, t_len = st.tabs(["Hour of day", "Weekday", "Text length"])
    with t_hour:
        _note("Rows by hour as recorded in the export (time zone unverified). Bursts drive the shape.")
        _chart(charts.hour_histogram_figure(run.tables["analytics_hour_histogram"], height=240), "cv_hours")
    with t_week:
        _note("Each weekday occurs only a few times in a short export, so this is coverage, not a weekly pattern.")
        _chart(charts.weekday_figure(run.tables["analytics_weekday_table"]), "cv_weekday")
        _show(run.tables["analytics_weekday_table"].rename(columns={
            "weekday": "Weekday", "calendar_days_in_range": "Calendar days in range",
            "active_dates": "Active dates", "user_rows": "User rows", "system_rows": "System rows"}))
    with t_len:
        _note("Length of text messages after masking links and numbers. A few long messages can skew the mean.")
        length = run.tables["analytics_text_length_summary"]
        if length.empty or int(length["n"].iloc[0]) == 0:
            st.caption("No text messages.")
        else:
            _show(length.rename(columns={"measure": "Measure", "n": "Messages", "min": "Min", "q25": "25%",
                                         "median": "Median", "q75": "75%", "max": "Max", "mean": "Mean"}))

    with st.expander("Additional descriptive tables: metadata summary and participants"):
        st.subheader("Metadata summary")
        meta = run.tables["analytics_metadata_counts"]
        comp = run.tables["analytics_row_composition"]
        rows = [(METADATA_LABELS.get(r.metric, r.metric), int(r.count), f"{int(r.denominator):,} {r.denominator_label}")
                for r in meta.itertuples()]
        for r in comp[comp["group"].isin(["media_type", "system_category"])].itertuples():
            kind = "Media type" if r.group == "media_type" else "System category"
            rows.append((f"{kind}: {r.category.replace('_', ' ')}", int(r.count),
                         f"{int(r.denominator):,} {r.denominator_label}"))
        _show(pd.DataFrame(rows, columns=["Item", "Count", "Out of"]))
        st.caption("Flags come from the parser or simple patterns (English-only). Only known whole-message "
                   "placeholders (for example image omitted, sticker omitted, deleted message) are recognised as "
                   "media or deleted; system-message text is never displayed.")

        st.subheader("Participants (descriptive counts only)")
        senders = run.tables["analytics_sender_counts"]
        if senders.empty:
            st.caption("No user rows.")
        else:
            _show(senders.rename(columns={
                "participant_id": "Participant", "user_rows": "User rows", "text_messages": "Text messages",
                "media_rows": "Media rows", "deleted_rows": "Deleted rows", "forwarded_rows": "Forwarded rows",
                "of_user_rows": "Total user rows"}))
        st.caption("Counts only, in order of first appearance. Participants are pseudonymised and labelled "
                   "per run. These counts are not a measure of engagement or participation and are not "
                   "compared between participants.")
    ui.footer_note()


# ================================================================ NLP Insights ==
def _notice_text(notice):
    parts = []
    if notice["rows_hidden_single_message"]:
        parts.append("Terms that occur in only one message are hidden.")
    if notice["rows_hidden_sensitive_pattern"]:
        parts.append("Terms that look like links, addresses or long numbers are hidden.")
    return " ".join(parts)


SCRIPT_STAT_LABELS = (
    ("mixed_script_messages", "Mixed-script messages"),
    ("total_alternations", "Script alternations (total)"),
    ("median_alternations_mixed", "Median alternations per mixed-script message"),
    ("short_messages_all_classes", "Very short messages (3 words or fewer)"),
    ("alphabetic_tokens_latin", "Latin-script words"),
    ("alphabetic_tokens_devanagari", "Devanagari-script words"),
)


def render_nlp(run, config):
    ui.page_header("NLP Insights", "Words, phrases, writing systems and important terms.", _status_badges(run),
                   _status_html(run))
    ctl_a, ctl_b = st.columns([3, 2])
    show_single = ctl_a.toggle(
        "Show terms that occur in only one message (may include names)", value=False,
        help="By default, terms occurring in only one message are hidden as a precaution against "
             "showing low-frequency terms that could identify someone. This is not complete PII "
             "detection: names used in several messages are still shown.")
    display, notice = prepare_display_tables(run.tables, config.min_term_messages, show_single)
    note = _notice_text(notice)
    st.caption(("Privacy filter: " + note + " " if note else "") +
               "It only affects what is shown and downloaded; the analysis itself is unchanged.")
    _no_text_info(run)

    top_k = ctl_b.slider("Terms to show", 5, 30, config.top_k_default, key="top_k")
    tab_uni, tab_bi, tab_tri, tab_tfidf, tab_script, tab_key = st.tabs(
        ["Unigrams", "Bigrams", "Trigrams", "TF-IDF", "Script Mix", "Key Terms"])

    with tab_uni:
        _note("Unigrams are individual tokens (words). The chart compares total occurrences across all messages "
              "with occurrences when each distinct text is counted once.")
        u1, u2 = st.columns([1, 2])
        with_stop = u1.toggle("Include English stopwords", value=False, key="uni_stop")
        rank_by = u2.radio("Rank by", ["all", "unique"], horizontal=True, key="uni_rank",
                           format_func=lambda v: "All messages" if v == "all" else "Unique texts only")
        table = display["ngram_unigrams_with_stopwords" if with_stop else "ngram_unigrams"]
        _chart(charts.ngram_bars_figure(table, top_k, rank_by), "nlp_uni")
        ui.interpret("Where the blue bar (all messages) is much longer than the orange bar (unique texts), "
                     "repeated messages are raising the count.")
        ui.explain(
            "How often each word occurs in the text messages.",
            "Each message is split into words; counts are added over all messages (repeats included) and "
            "again over unique texts only. Placeholders for links and phone numbers are counted as tokens, "
            "and English stopwords are removed unless switched on.",
            "It shows the vocabulary and how much of it comes from repeated messages.",
            "Small samples give unstable rankings. Only English stopwords are removed, so Devanagari function "
            "words can rank highly (see the script note below).")
        _script_note(display)

    with tab_bi:
        _note("Bigrams show frequently occurring two-word sequences inside a message.")
        _chart(charts.ngram_bars_figure(display["ngram_bigrams"], top_k, st.session_state.get("uni_rank", "all")), "nlp_bi")
        ui.interpret("Where the blue bar (all messages) is longer than the orange bar (unique texts), the phrase "
                     "comes partly from repeated messages.")
        ui.explain(
            "How often each pair of neighbouring words occurs.",
            "Pairs are formed inside each message only (never across messages), keeping stopwords so "
            "adjacency is as written.",
            "It shows common phrasing and templates.",
            "Most pairs occur once or twice in small chats; repeated messages inflate counts.")

    with tab_tri:
        _note("Trigrams show frequently occurring three-word sequences inside a message.")
        _chart(charts.ngram_bars_figure(display["ngram_trigrams"], top_k, st.session_state.get("uni_rank", "all")), "nlp_tri")
        ui.interpret("Three-word runs are sparse in short chats; a run that appears many times usually marks a "
                     "repeated or copied message.")
        ui.explain(
            "How often each run of three words occurs.",
            "Same method as bigrams, with three-word windows inside each message.",
            "Repeated three-word runs are the clearest sign of copied text.",
            "Very sparse in small chats; interpret repeats, not rankings.")

    with tab_tfidf:
        _note("TF-IDF highlights terms that are relatively prominent within the message corpus: frequent in a "
              "message but not found in every message.")
        c1, c2 = st.columns(2)
        variant = c1.radio("Variant", ["all", "unique"], horizontal=True,
                           format_func=lambda v: "All messages (primary)" if v == "all"
                           else "Unique texts (sensitivity)")
        metric = c2.radio("Metric", ["total_tfidf", "mean_tfidf_in_docs"], horizontal=True,
                          format_func=lambda v: "Total over messages" if v == "total_tfidf"
                          else "Mean in messages containing the term")
        _chart(charts.tfidf_bars_figure(display["tfidf_top_terms"], variant, metric, top_k), "nlp_tfidf")
        ui.interpret("A higher score means the term is more distinctive within this chat, not more important in "
                     "general. Only top terms are shown; message-level scores are not displayed.")
        sub = display["tfidf_top_terms"]
        sub = sub[sub["variant"] == variant] if not sub.empty else sub
        if not sub.empty:
            with st.expander("Scores table (top terms)"):
                _show(sub.sort_values([metric, "term"], ascending=[False, True]).head(top_k)
                      [["term", "script", "df", "idf", "total_tfidf", "mean_tfidf_in_docs", "n_docs_top3"]]
                      .rename(columns={"term": "Term", "script": "Script", "df": "Messages containing term", "idf": "IDF",
                                        "total_tfidf": "Total TF-IDF", "mean_tfidf_in_docs": "Mean TF-IDF (messages containing term)",
                                        "n_docs_top3": "Messages where term is in the top 3"}))
        ui.explain(
            "Which terms are distinctive within this chat: frequent in a message and rare across messages.",
            "TF-IDF = term count in a message × smoothed inverse document frequency "
            "ln((1+N)/(1+df))+1, then L2-normalised per message. N is the number of messages in the "
            "variant, including empty ones. 'Total' sums the normalised scores over messages; 'mean' "
            "averages over only the messages containing the term.",
            "It separates prominent terms from terms that distinguish particular messages. The primary "
            "variant keeps repeated messages; the sensitivity variant counts each distinct text once.",
            "A high score means distinctive within this chat, not important in general. Rankings are "
            "unstable for small N, many terms share the same IDF, and no accuracy is claimed.")
        meta = run.tfidf_meta.get("variants", {})
        if meta:
            st.caption(" · ".join(f"{('Primary' if v == 'all' else 'Sensitivity')}: N = "
                                  f"{meta[v]['n_documents_N']}, empty documents = {meta[v]['n_empty_documents']}"
                                  for v in ("all", "unique") if v in meta))

    with tab_script:
        _note("Script Mix describes the writing systems that appear in messages (for example Latin, Devanagari or "
              "several scripts in one message). It does not identify languages.")
        script_variant = st.radio("Messages counted", ["all", "unique"], horizontal=True, key="script_variant",
                                  format_func=lambda v: "All messages (primary)" if v == "all"
                                  else "Unique texts (sensitivity)")
        summary = display["script_mix_summary"]
        _chart(charts.script_mix_figure(summary, script_variant), "nlp_script")
        ui.interpret("Bars count messages by the writing systems used in them. Mixed-script messages contain "
                     "characters from more than one detected writing system. This is script composition only: it "
                     "does not tell which language was written.")
        stats = display["script_mixing_stats"]
        if not stats.empty:
            s = stats[stats["variant"] == script_variant].set_index("metric")["value"]
            rows = [(label, s[key]) for key, label in SCRIPT_STAT_LABELS if key in s.index and s[key] != ""]
            if "min_devanagari_share_mixed" in s.index and s["min_devanagari_share_mixed"] != "":
                rows.append(("Devanagari share of words in mixed-script messages (min to max)",
                             f"{float(s['min_devanagari_share_mixed']):.2f} to {float(s['max_devanagari_share_mixed']):.2f}"))
            if rows:
                with st.expander("Script statistics"):
                    _show(pd.DataFrame([(a, _plain_number(b)) for a, b in rows], columns=["Measure", "Value"]))
        ui.explain(
            "How many text messages use Latin script only, Devanagari only, another script only, more than one "
            "writing system, or no letters at all (for example a message that is only a link), and how often the "
            "script changes inside a message.",
            "Each word is classed by the Unicode names of its letters; links and phone numbers are masked first "
            "and ignored. A message is classed by the scripts of its words. A script alternation is a place where "
            "neighbouring words use different scripts.",
            "It shows how mixed the writing systems are, which matters for interpreting the word counts and for "
            "English-only stopword removal.",
            "Script is not language: Devanagari may be Marathi or Hindi, and Latin may be English or romanised text. "
            "No language detection is performed. Counts are small and the mixed-script messages can be similar to one another.")

    with tab_key:
        _note("Key-term coverage measures how many distinct messages contain a term. Coverage = number of "
              "distinct messages containing the term; Frequency = total number of occurrences.")
        kt = display["key_terms"]
        _chart(charts.key_terms_figure(kt, top_k), "nlp_keyterms")
        ui.interpret("Where the frequency bar is much longer than the coverage bar, the term repeats inside the "
                     "same messages or comes from a repeated message rather than being spread widely.")
        if not kt.empty:
            with st.expander("Key terms table"):
                show = kt.sort_values(["unique_texts_containing", "term"], ascending=[False, True]).head(top_k)
                _show(show[["term", "script", "unique_texts_containing", "messages_containing", "occurrences_all",
                            "repetition_ratio"]].rename(columns={
                                "term": "Term", "script": "Script", "unique_texts_containing": "Distinct messages (coverage)",
                                "messages_containing": "Messages incl. repeats", "occurrences_all": "Total occurrences",
                                "repetition_ratio": "Repetition ratio"}))
        ui.explain(
            "The number of distinct (unique) messages that contain each term, next to how often the term occurs in total.",
            "For each term, messages are counted once however many times the term appears in them, and identical "
            "messages are counted once. Terms are ranked by this coverage, then alphabetically. The terms are the "
            "same ones used for TF-IDF: English stopwords, links and phone numbers are excluded.",
            "A term can be frequent only because one message was repeated or because a word recurs inside one "
            "message; coverage shows whether it is spread across different messages.",
            "Small samples; only English stopwords are removed; terms in only one message are hidden by the privacy "
            "filter; this is a ranking of existing counts, not a topic model.")
    ui.footer_note()


def _script_note(display):
    diag = display.get("ngram_script_diagnostics")
    if diag is None or diag.empty:
        return
    with st.expander("Script note: effect of English-only stopword removal"):
        _show(diag.rename(columns={"script": "Script", "tokens_before": "Tokens before",
                                   "tokens_after": "Tokens after", "pct_removed": "% removed"}))
        st.caption("Only English stopwords are removed. Words in other scripts (for example Devanagari) "
                   "are left in, so they can rank highly. No Marathi or Hindi stopword handling exists.")


# ==================================================================== Patterns ==
def render_patterns(run, config):
    ui.page_header("Patterns", "How much of the text is repeated, and which repeated templates exist.",
                   _status_badges(run), _status_html(run))
    summary = run.tables["analytics_repetition_summary"]
    groups = run.tables["analytics_repetition_groups"]
    if summary.empty or _value(summary, "metric", "text_messages") == 0:
        st.warning("No text messages, so there is no repetition to show.")
        ui.footer_note()
        return

    ui.section("Repetition Summary", "Messages are compared after links and phone numbers are masked, so messages "
                                     "that differ only by a link count as the same template.")
    ui.kpi_cards([
        ("Text Messages", _value(summary, "metric", "text_messages"), "Real text messages"),
        ("Unique Texts", _value(summary, "metric", "unique_texts_after_masking"), "Distinct after masking"),
        ("Repeat Messages", _value(summary, "metric", "repeat_messages_after_masking"),
         "First copy not counted as a repeat"),
        ("Repeated Templates", _value(summary, "metric", "template_groups"), "Texts that occur more than once"),
    ])
    left, right = st.columns(2)
    with left:
        _chart(charts.unique_vs_repeated_figure(summary), "pt_unique_repeated", "Unique vs Repeated",
               "Text messages split into unique texts and repeats.")
        with ui.panel("repeat-detail"):
            st.markdown("<div class='wa-card-title'>Repetition detail</div>", unsafe_allow_html=True)
            ui.mini_stats([
                ("Exact raw repeats", _value(summary, "metric", "exact_raw_repeat_messages")),
                ("Visible only after masking", _value(summary, "metric", "repeats_visible_only_after_masking")),
                ("Largest template group", _value(summary, "metric", "largest_template_group_size"))])
            st.caption("Exact repeats have identical raw text; template repeats have identical text after links and "
                       "phone numbers are masked.")
    with right:
        top_groups = groups.sort_values(["occurrences", "template_id"], ascending=[False, True], kind="stable").head(10)
        _chart(charts.template_groups_figure(top_groups), "pt_templates", "Repeated Templates",
               "Each repeated text is an anonymous template; the message text is never shown.")
        if len(groups) > len(top_groups):
            _note(f"The chart shows the {len(top_groups)} most repeated of {len(groups)} templates; the table below "
                  "lists all of them.")
    if not groups.empty:
        with st.expander("Table of repeated templates"):
            shown = groups.copy()
            shown["template_id"] = "Template " + shown["template_id"].astype(str)
            _show(shown.rename(columns={
                "template_id": "Template", "occurrences": "Messages", "repeat_messages": "Repeats",
                "distinct_raw_texts": "Distinct raw texts", "exact_raw_identical": "Exact-identical",
                "contains_url": "Contains URL", "forwarded_messages": "Forwarded", "first_date": "First date",
                "last_date": "Last date", "active_dates": "Active dates"}))
    ui.explain(
        "How many text messages repeat an earlier text, counted two ways.",
        "Exact repeats have identical raw text. Template repeats have identical text after links and "
        "phone numbers are masked, so messages that differ only by a link become one template. Each "
        "template's first message is not counted as a repeat.",
        "Repetition drives what the word and phrase counts show, so it is measured separately.",
        "Only exact and masked-identical text is compared. Similar but not identical messages are not "
        "detected, and the data cannot show why a message was repeated.")

    ui.section("Interpretation", "Repeated messages inflate counts; comparing all messages with unique texts shows how much.")
    st.markdown(
        "- **Unigram, bigram and trigram counts:** repeated messages inflate counts; the unique-text column shows "
        "the count if each distinct text were counted once.\n"
        "- **TF-IDF:** repeated messages raise a term's document frequency, which lowers its IDF; the rank change "
        "between the primary and sensitivity variants shows how much repetition matters.\n"
        "- **Key terms:** coverage counts distinct messages, so a term that is frequent only because one message "
        "was repeated has low coverage.")
    with st.expander("Table: how repetition changes term counts and TF-IDF ranks"):
        display, _ = prepare_display_tables(run.tables, config.min_term_messages, False)
        comp = display["tfidf_variant_comparison"]
        if comp.empty:
            st.caption("No terms above the display threshold.")
        else:
            top = comp.sort_values(["rank_all", "term"]).head(15)
            cols = [c for c in ["term", "count_all", "count_unique", "rank_all", "rank_unique", "rank_change"]
                    if c in top.columns]
            _show(top[cols].rename(columns={
                "term": "Term", "count_all": "Occurrences (all messages)", "count_unique": "Occurrences (unique texts)",
                "rank_all": "TF-IDF rank (primary)", "rank_unique": "TF-IDF rank (sensitivity)",
                "rank_change": "Rank change"}))
    ui.footer_note()
