"""Shared Streamlit UI helpers: styling, page headers, KPI cards, explanations, error guidance.

Design brief: a clean, light, academic dashboard. Simple bordered cards, restrained colours, no
animation. Cards are plain HTML produced here from numbers and strings we control (escaped), so the
layout does not depend on Streamlit's internal element names.
"""

import html

import streamlit as st

CSS = """
<style>
  :root { --wa-bg: #edf1f7; --wa-sidebar: #e4eaf3; --wa-surface: #ffffff; --wa-elev: #f6f8fc;
          --wa-border: #cdd6e4; --wa-text: #172033; --wa-muted: #525d70; --wa-accent: #1e5ae0;
          --wa-accent2: #08766a; --wa-accent-soft: rgba(30,90,224,0.10); --wa-on-accent: #ffffff;
          --wa-shadow: 0 1px 2px rgba(16,24,40,0.08), 0 4px 12px rgba(16,24,40,0.06); }
  .stApp { background: var(--wa-bg); color: var(--wa-text); }
  [data-testid="stHeader"] { background: transparent; }
  .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1560px;
                     padding-left: 1.6rem; padding-right: 1.6rem; }
  [data-testid="stSidebar"][aria-expanded="true"] { width: 248px !important; min-width: 248px !important; }
  h1, [data-testid="stHeading"] h1 { font-weight: 780 !important; font-size: 1.75rem !important;
                                      letter-spacing: -0.015em; margin: 0; padding: 0; color: var(--wa-text); }
  h2, h3 { font-weight: 650; letter-spacing: -0.005em; color: var(--wa-text); }
  h3, [data-testid="stHeading"] h3 { font-size: 1.02rem !important; margin: 0; padding: 0.15rem 0 0.1rem 0;
                                      color: var(--wa-text); }
  p, li, label, [data-testid="stMarkdownContainer"] { color: var(--wa-text); }
  /* sidebar */
  [data-testid="stSidebar"] { background: var(--wa-sidebar); border-right: 1px solid var(--wa-border); }
  [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 1rem; }
  [data-testid="stSidebar"] [role="radiogroup"] { gap: 0.2rem; }
  [data-testid="stSidebar"] label[data-testid="stRadioOption"] { padding: 0.45rem 0.7rem; border-radius: 10px;
        border: 1px solid transparent; width: 100%; transition: background 0.12s; }
  [data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:first-child { display: none; }
  [data-testid="stSidebar"] label[data-testid="stRadioOption"]:hover { background: var(--wa-elev); }
  [data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"] {
        background: var(--wa-accent-soft); border-color: var(--wa-accent); box-shadow: inset 3px 0 0 var(--wa-accent); }
  [data-testid="stSidebar"] label[data-testid="stRadioOption"] p { color: var(--wa-text); font-weight: 560; }
  [data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"] p { color: var(--wa-accent) !important;
        font-weight: 680; }
  [data-testid="stSidebar"] label[data-testid="stRadioOption"] p::before { content: ""; display: inline-block;
        width: 16px; height: 16px; margin-right: 0.6rem; vertical-align: -3px; background-color: currentColor;
        -webkit-mask: var(--wa-nav-icon) center / contain no-repeat; mask: var(--wa-nav-icon) center / contain no-repeat; }
  [data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input[value="0"]) { --wa-nav-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='3' width='7' height='7'/%3E%3Crect x='14' y='3' width='7' height='7'/%3E%3Crect x='14' y='14' width='7' height='7'/%3E%3Crect x='3' y='14' width='7' height='7'/%3E%3C/svg%3E"); }
  [data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input[value="1"]) { --wa-nav-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'/%3E%3C/svg%3E"); }
  [data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input[value="2"]) { --wa-nav-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 7V4h16v3M9 20h6M12 4v16'/%3E%3C/svg%3E"); }
  [data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input[value="3"]) { --wa-nav-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M17 1l4 4-4 4'/%3E%3Cpath d='M3 11V9a4 4 0 0 1 4-4h14'/%3E%3Cpath d='M7 23l-4-4 4-4'/%3E%3Cpath d='M21 13v2a4 4 0 0 1-4 4H3'/%3E%3C/svg%3E"); }
  .wa-brand { display: flex; align-items: center; gap: 0.65rem; margin-bottom: 0.5rem; }
  .wa-brand-mark { width: 36px; height: 36px; border-radius: 10px; background: var(--wa-accent); color: #ffffff;
                   display: inline-flex; align-items: center; justify-content: center; flex: none; }
  .wa-brand-mark svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 2;
                       stroke-linecap: round; stroke-linejoin: round; }
  .wa-brand-name { font-size: 1.02rem; font-weight: 720; line-height: 1.15; color: var(--wa-text); }
  .wa-brand-sub { font-size: 0.8rem; color: var(--wa-muted); line-height: 1.2; }
  .wa-skel { position: relative; display: flex; align-items: flex-end; gap: 6%; padding: 1.1rem 1.2rem 0.6rem 1.2rem;
             background: var(--wa-elev); border: 1px dashed #b4c0d2; border-radius: 10px; }
  .wa-skel span { flex: 1; background: #cbd6e6; border-radius: 4px 4px 0 0; }
  .wa-skel-msg { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
                 color: var(--wa-muted); font-size: 0.86rem; font-weight: 600; text-align: center; padding: 0 1rem; }
  .wa-header-status { text-align: right; padding-top: 0.35rem; }
  .wa-sidebar-title { font-size: 1.08rem; font-weight: 720; line-height: 1.25; margin-bottom: 0.3rem;
                      color: var(--wa-text); }
  .wa-sidebar-desc { color: var(--wa-muted); font-size: 0.82rem; line-height: 1.4; margin-bottom: 0.8rem; }
  .wa-sidebar-label { color: var(--wa-muted); font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
                      letter-spacing: 0.08em; margin: 0.1rem 0 0.35rem 0; }
  /* panels (keyed containers from ui.panel) */
  [class*="st-key-panel-"] { background: var(--wa-surface); border: 1px solid var(--wa-border) !important;
        border-radius: 14px; box-shadow: var(--wa-shadow); }
  /* header */
  .st-key-banner { padding: 0.2rem 0 0 0; }
  .wa-lede { color: var(--wa-muted); font-size: 0.95rem; margin: 0.2rem 0 0.6rem 0; }
  .wa-header { border-bottom: 1px solid var(--wa-border); margin: 0.6rem 0 1rem 0; }
  .wa-section-note { color: var(--wa-muted); font-size: 0.86rem; margin: 0 0 0.45rem 0; }
  .wa-interpret { color: var(--wa-muted); font-size: 0.86rem; margin: 0.1rem 0 0.4rem 0; }
  .wa-interpret b { color: var(--wa-text); font-weight: 650; }
  .wa-note { color: var(--wa-muted); font-size: 0.8rem; margin-top: 1rem; }
  /* KPI cards */
  .wa-kpi { background: var(--wa-surface); border: 1px solid var(--wa-border); border-radius: 14px;
            padding: 0.85rem 1rem 0.75rem 1rem; box-shadow: var(--wa-shadow); height: 100%; margin-bottom: 0.9rem; }
  .wa-kpi-top { display: flex; justify-content: space-between; align-items: center; }
  .wa-kpi-label { color: var(--wa-muted); font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
                  letter-spacing: 0.07em; }
  .wa-kpi-icon { color: var(--wa-ic, var(--wa-accent)); display: inline-flex; background: var(--wa-ic-bg, var(--wa-accent-soft));
                 border-radius: 9px; padding: 0.32rem; }
  .wa-kpi-icon svg { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 2;
                     stroke-linecap: round; stroke-linejoin: round; }
  .wa-kpi-value { color: var(--wa-text); font-size: 2rem; font-weight: 720; line-height: 1.2; margin: 0.3rem 0 0.1rem; }
  .wa-kpi-note { color: var(--wa-muted); font-size: 0.78rem; line-height: 1.3; }
  /* badges */
  .wa-badge { display: inline-block; padding: 0.1rem 0.6rem; border-radius: 999px; font-size: 0.76rem;
              font-weight: 600; border: 1px solid var(--wa-border); color: var(--wa-muted);
              background: var(--wa-surface); margin: 0 0.35rem 0.25rem 0; }
  .wa-badge.ok { color: #0b6b4f; border-color: #a8dcc8; background: #e6f6ef; }
  .wa-badge.warn { color: #7a4f00; border-color: #efd18a; background: #fff6dc; }
  .wa-badge.bad { color: #a12a22; border-color: #f0b5b0; background: #fdeceb; }
  .wa-badge.ok::before, .wa-badge.warn::before, .wa-badge.bad::before { content: "●  "; font-size: 0.7em; }
  /* findings and checklist */
  .wa-findings, .wa-checks { list-style: none; margin: 0.2rem 0 0.2rem 0; padding: 0; }
  .wa-findings li { position: relative; padding: 0.3rem 0 0.3rem 1.2rem; color: var(--wa-text); font-size: 0.93rem;
                    line-height: 1.45; }
  .wa-findings li::before { content: ""; position: absolute; left: 0.1rem; top: 0.82rem; width: 7px; height: 7px;
                            border-radius: 50%; background: var(--wa-accent); }
  .wa-findings li:nth-child(2n)::before { background: var(--wa-accent2); }
  .wa-checks li { color: var(--wa-text); font-size: 0.9rem; padding: 0.22rem 0; }
  .wa-checks li::before { content: "✓"; color: var(--wa-accent2); font-weight: 700; margin-right: 0.55rem; }
  .wa-card-title { color: var(--wa-muted); font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
                   letter-spacing: 0.08em; margin-bottom: 0.2rem; }
  .wa-stages { font-size: 0.88rem; line-height: 1.55; margin: 0; }
  .wa-stages .done { color: #0b6b4f; } .wa-stages .now { color: var(--wa-accent); font-weight: 600; }
  .wa-stages .fail { color: #a12a22; font-weight: 600; }
  .wa-mini { color: var(--wa-muted); font-size: 0.9rem; margin-bottom: 0.4rem; }
  .wa-mini b { font-size: 1.15rem; color: var(--wa-text); }
  /* controls */
  .stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid var(--wa-border); gap: 0.4rem; }
  .stTabs [data-baseweb="tab"] p { color: var(--wa-muted); font-weight: 600; }
  .stTabs [aria-selected="true"], .stTabs [aria-selected="true"] p { color: var(--wa-accent) !important; }
  .stTabs [data-baseweb="tab-highlight"] { background-color: var(--wa-accent) !important; }
  .stButton button, [data-testid="stDownloadButton"] button { background: var(--wa-surface); color: var(--wa-text);
        border: 1px solid var(--wa-border); border-radius: 10px; box-shadow: var(--wa-shadow);
        transition: border-color 0.12s, color 0.12s; }
  .stButton button:hover, [data-testid="stDownloadButton"] button:hover { border-color: var(--wa-accent);
        color: var(--wa-accent); }
  .stButton button[kind="primary"] { background: var(--wa-accent); color: var(--wa-on-accent); border-color: var(--wa-accent); }
  .stButton button[kind="primary"] p { color: var(--wa-on-accent); }
  .stButton button[kind="primary"]:hover { filter: brightness(1.08); color: var(--wa-on-accent); }
  .stButton button:disabled { opacity: 0.5; }
  [data-testid="stSidebar"] .stButton button { padding: 0.25rem 0.35rem; }
  [data-testid="stSidebar"] .stButton button p { font-size: 0.82rem; white-space: nowrap; }
  [data-testid="stFileUploaderDropzone"] { background: var(--wa-elev); border: 1px dashed #c3ccd9; border-radius: 12px; }
  [data-testid="stFileUploaderDropzone"] small, [data-testid="stFileUploaderDropzone"] span { color: var(--wa-muted); }
  [data-testid="stFileUploaderFile"] { color: var(--wa-text); }
  [data-testid="stExpander"] { background: var(--wa-surface); border: 1px solid var(--wa-border); border-radius: 12px;
        box-shadow: var(--wa-shadow); }
  [data-testid="stCaptionContainer"], .stCaption { color: var(--wa-muted); }
  [data-testid="stDataFrame"] { border: 1px solid var(--wa-border); border-radius: 10px; }
</style>
"""

LIMITED_NOTE = ("Descriptive results for this chat only; not generalisable. Timestamps are shown as "
                "recorded in the export and the time zone is unverified.")

PROJECT_TITLE = "WhatsApp NLP & Conversation Analytics"
PROJECT_DESCRIPTION = ("Explore message patterns, conversation activity and language structure from an "
                       "exported WhatsApp chat.")
SIDEBAR_DESCRIPTION = ("Explore conversation patterns, language structure and activity from an exported "
                       "WhatsApp chat.")

# Pipeline stage (run_pipeline.STAGES) -> wording shown while a chat is processed. Only real stages.
STAGE_LABELS = {
    "Validate file": "Validating chat file",
    "Parse export": "Parsing messages",
    "Preprocess and quality checks": "Preprocessing text and checking data quality",
    "N-gram analysis": "Running NLP analysis: unigrams, bigrams and trigrams",
    "TF-IDF": "Running NLP analysis: TF-IDF",
    "Script Mix": "Running NLP analysis: Script Mix",
    "Key Terms": "Running NLP analysis: Key Terms",
    "Conversation analytics": "Running conversation analytics",
    "Privacy filter and load results": "Applying the privacy filter and preparing the dashboard",
    "Clean up": "Deleting temporary files",
}

# UserFacingError.code -> what the user should do next (the error message itself comes from the pipeline).
ERROR_HELP = {
    "wrong_type": "Export the chat from WhatsApp as a text (.txt) file and upload that file.",
    "empty": "The file has no content. Export the chat again and check that the exported file is not empty.",
    "too_large": "Upload a smaller export, or raise the configured upload limit if you run the app yourself.",
    "not_utf8": "Export the chat again as a plain text file (UTF-8).",
    "unsupported_format": "Only the bracketed export style is supported, for example "
                          "`[3/10/25, 9:05:00 AM] Name: message`. Other export styles are not supported yet. "
                          "You can try the synthetic demo chat to see the expected format.",
    "dates_invalid": "Check that the export uses month/day/year dates and a 12-hour clock with AM/PM.",
    "too_many_rows": "This chat is larger than the configured analysis limit. Try a shorter export.",
    "too_many_messages": "This chat is larger than the configured analysis limit. Try a shorter export.",
    "parse_failed": "Try the synthetic demo chat to confirm the app works, then check the export format.",
    "date_order_unsupported": "Only Month/Day/Year dates are supported. Export the chat from a device or "
                              "language setting that writes dates as Month/Day/Year, or use a supported export.",
    "date_order_inconsistent": "Check that the file is a single, unmodified WhatsApp export.",
    "consistency_check_failed": "Nothing was stored. Try the synthetic demo chat to confirm the app works, then "
                                "check that the file is an unmodified export.",
    "analysis_failed": "Nothing was stored. Try the synthetic demo chat to confirm the app works, then try "
                       "the file again or a different export.",
    "privacy_check_failed": "No results were displayed. Nothing was stored.",
}


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title, lede, badges=None, status=None):
    """Compact header: title and subtitle on the left, a status badge (HTML) on the right, and an optional
    row of badges below."""
    with st.container(key="banner"):                         # carries the faded theme image when one is applied
        left, right = st.columns([5, 2])
        with left:
            st.title(title)
            st.markdown(f"<div class='wa-lede'>{html.escape(lede)}</div>", unsafe_allow_html=True)
        if status:
            right.markdown(f"<div class='wa-header-status'>{status}</div>", unsafe_allow_html=True)
        if badges:
            st.markdown(badges, unsafe_allow_html=True)
        st.markdown("<div class='wa-header'></div>", unsafe_allow_html=True)


BRAND_MARK = ('<svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'
              '<path d="M8 9h8M8 13h5"/></svg>')


def brand():
    st.markdown(f"<div class='wa-brand'><span class='wa-brand-mark'>{BRAND_MARK}</span><div>"
                "<div class='wa-brand-name'>WhatsApp NLP</div><div class='wa-brand-sub'>Conversation Analytics</div>"
                f"</div></div><div class='wa-sidebar-desc'>{html.escape(SIDEBAR_DESCRIPTION)}</div>",
                unsafe_allow_html=True)


def placeholder_chart(message, height=200, bars=(35, 60, 45, 80, 55, 70, 40)):
    """Empty-chart illustration for the no-chat dashboard: pale bars plus a message. It carries no data."""
    spans = "".join(f"<span style='height:{h}%'></span>" for h in bars)
    st.markdown(f"<div class='wa-skel' style='height:{height}px'>{spans}"
                f"<div class='wa-skel-msg'>{html.escape(message)}</div></div>", unsafe_allow_html=True)


def panel(key):
    """Bordered white container (keyed so the CSS can style it)."""
    return st.container(border=True, key=f"panel-{key}")


def interpret(text):
    """One-line reading guidance placed under a chart (generic, not a finding)."""
    st.markdown(f"<div class='wa-interpret'><b>How to read it.</b> {html.escape(text)}</div>",
                unsafe_allow_html=True)


def sidebar_label(text):
    st.markdown(f"<div class='wa-sidebar-label'>{html.escape(text)}</div>", unsafe_allow_html=True)


def mini_stats(items):
    """Compact one-line figures for half-width panels: [(label, value), ...]."""
    parts = " &nbsp;·&nbsp; ".join(f"{html.escape(label)} <b>{int(value):,}</b>" for label, value in items)
    st.markdown(f"<div class='wa-mini'>{parts}</div>", unsafe_allow_html=True)


def stage_list(stages, current, failed=False):
    """HTML list of the real pipeline stages: done / running / failed. No percentages."""
    rows = []
    for i, label in enumerate(stages):
        text = html.escape(label)
        if i < current:
            rows.append(f"<span class='done'>✓ {text}</span>")
        elif i == current:
            rows.append(f"<span class='fail'>✕ {text}</span>" if failed else f"<span class='now'>▸ {text}…</span>")
    return "<p class='wa-stages'>" + "<br>".join(rows) + "</p>"


def section(title, note=None):
    """Sub-heading with an optional one-line plain-English explanation underneath."""
    st.subheader(title)
    if note:
        st.markdown(f"<div class='wa-section-note'>{html.escape(note)}</div>", unsafe_allow_html=True)


def badge(text, kind=""):
    return f"<span class='wa-badge {kind}'>{html.escape(text)}</span>"


ICONS = {   # small line icons (inline SVG, no dependency)
    "chat": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "text": '<path d="M4 7h16M4 12h16M4 17h10"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "layers": '<path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/>',
    "repeat": '<path d="M17 1l4 4-4 4"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><path d="M7 23l-4-4 4-4"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>',
    "grid": '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
    "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    "forward": '<path d="M15 14l5-5-5-5"/><path d="M4 20v-7a4 4 0 0 1 4-4h12"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
}
KPI_ICON = {"Total Messages": "chat", "Text Messages": "text", "Media / Deleted": "image", "Active Days": "calendar",
            "Unique Texts": "layers", "Repeat Messages": "repeat", "Repeated Templates": "grid", "Participants": "users",
            "Forwarded Messages": "forward", "Messages With Links": "link"}


# icon -> (stroke colour, soft background): a restrained, fixed semantic palette (a theme image does not change it)
ICON_TINTS = {"chat": ("#2563eb", "#e1ebfd"), "users": ("#6240c8", "#ebe5fa"), "text": ("#0a7a6c", "#d9f1ed"),
              "image": ("#bf5410", "#fce6d4"), "calendar": ("#1d7a3b", "#dcf1e3"), "layers": ("#2563eb", "#e1ebfd"),
              "repeat": ("#bf5410", "#fce6d4"), "grid": ("#6240c8", "#ebe5fa"), "forward": ("#0a7a6c", "#d9f1ed"),
              "link": ("#2563eb", "#e1ebfd")}


def kpi_cards(items):
    """items: list of (label, value, note). One analytics card per figure, with a small line icon."""
    cols = st.columns(len(items))
    for col, (label, value, note) in zip(cols, items):
        shown = f"{value:,}" if isinstance(value, int) else str(value)
        icon = ICONS.get(KPI_ICON.get(label, ""), "")
        fg, bg = ICON_TINTS.get(KPI_ICON.get(label, ""), ("#2563eb", "#e1ebfd"))
        icon_html = (f"<span class='wa-kpi-icon' style='--wa-ic:{fg};--wa-ic-bg:{bg}'>"
                     f"<svg viewBox='0 0 24 24'>{icon}</svg></span>") if icon else ""
        col.markdown(
            f"<div class='wa-kpi'><div class='wa-kpi-top'><span class='wa-kpi-label'>{html.escape(label)}</span>"
            f"{icon_html}</div>"
            f"<div class='wa-kpi-value'>{html.escape(shown)}</div>"
            f"<div class='wa-kpi-note'>{html.escape(note)}</div></div>", unsafe_allow_html=True)


def findings_card(findings):
    """Compact card of short finding sentences (each built from verified results elsewhere)."""
    items = "".join(f"<li>{html.escape(f)}</li>" for f in findings) or "<li>No findings to show.</li>"
    with panel("findings"):
        st.markdown(f"<div class='wa-card-title'>Key Findings</div><ul class='wa-findings'>{items}</ul>",
                    unsafe_allow_html=True)


def checklist_card(title, items):
    """'About this analysis' style card: a tick list of the methods applied."""
    rows = "".join(f"<li>{html.escape(i)}</li>" for i in items)
    with panel("checklist"):
        st.markdown(f"<div class='wa-card-title'>{html.escape(title)}</div><ul class='wa-checks'>{rows}</ul>",
                    unsafe_allow_html=True)


def metric_cards(items):
    """Compact KPI row used on the Patterns page: (label, value, help) like before."""
    kpi_cards([(label, value, help_text) for label, value, help_text in items])


def explain(what, how, why, limitation, title="What am I looking at?"):
    """Collapsed explainability panel: measured / calculated / shown / limitation."""
    with st.expander(title):
        st.markdown(f"**What is measured.** {what}")
        st.markdown(f"**How it is calculated.** {how}")
        st.markdown(f"**Why it is shown.** {why}")
        st.markdown(f"**Limitation.** {limitation}")


def footer_note():
    st.markdown(f"<div class='wa-note'>{html.escape(LIMITED_NOTE)}</div>", unsafe_allow_html=True)


def error_help(code):
    """The short 'what to do' line for an error code (empty string if none)."""
    return ERROR_HELP.get(code, "")


def empty_dashboard(cta):
    """Dashboard shell shown before any chat is loaded: header, call to action, KPI placeholders, empty chart cards,
    and the format and privacy notes. `cta` renders the upload controls (it needs app state, so the app passes it)."""
    page_header(PROJECT_TITLE, PROJECT_DESCRIPTION, status=badge("No chat loaded"))
    with panel("cta"):
        left, right = st.columns([3, 2])
        with left:
            st.markdown("<div class='wa-card-title'>Get started</div>", unsafe_allow_html=True)
            st.subheader("Upload a WhatsApp .txt export")
            st.markdown("No chat loaded yet. Upload an exported chat to fill this dashboard, or load the synthetic "
                        "demo chat to see it with invented sample data.")
        with right:
            cta()
    kpi_cards([("Total Messages", "—", "Written by participants"), ("Participants", "—", "Pseudonymised; counts only"),
               ("Text Messages", "—", "The base for NLP"), ("Media / Deleted", "—", "Non-text placeholders"),
               ("Active Days", "—", "Days with any activity")])
    left, right = st.columns([2, 1])
    with left, panel("sk-daily"):
        section("Daily Activity", "Rows per calendar date.")
        placeholder_chart("Upload a chat to see daily activity", 260, (30, 55, 40, 75, 50, 65, 35, 60, 45, 70))
    with right, panel("sk-comp"):
        section("Message Composition", "What the exported rows consist of.")
        placeholder_chart("Upload a chat to see its composition", 260, (60, 40, 20))
    c1, c2, c3 = st.columns(3)
    for col, key, title, note, msg in (
            (c1, "sk-terms", "Top Key Terms", "Terms found in the most distinct messages.", "Upload a chat to view terms"),
            (c2, "sk-script", "Script Mix", "Writing systems used; not language identification.",
             "Upload a chat to view script patterns"),
            (c3, "sk-pat", "Conversation Patterns", "How much of the text repeats.", "Upload a chat to view patterns")):
        with col, panel(key):
            section(title, note)
            placeholder_chart(msg, 170, (70, 50, 60, 35))
    left, right = st.columns(2)
    with left, panel("empty-format"):
        st.subheader("Expected file format")
        st.code("[3/10/25, 9:05:00 AM] Alex Demo: Welcome everyone\n"
                "[3/10/25, 9:06:30 AM] Sam Sample: Thanks for adding me", language="text")
        st.caption("Only this bracketed .txt export is supported (dates read as Month/Day/Year, 12-hour clock). "
                   "Other export styles are not supported yet.")
    with right, panel("empty-privacy"):
        st.subheader("Privacy")
        st.markdown(
            "- The file is processed for this session only; the raw file is not stored after the run.\n"
            "- Phone numbers, senders, names, links and message text are not shown. Participants appear as "
            "`Participant_N`, assigned per run.\n"
            "- Words in the NLP tab come from the chat and could include names. Terms that occur in only one message "
            "are hidden by default. This is not complete PII detection.\n"
            "- If this app is hosted, the file is uploaded to the server running it. Only upload chats you are "
            "entitled to analyse.")
