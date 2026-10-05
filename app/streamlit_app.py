"""
WhatsApp NLP & Conversation Analytics dashboard (Streamlit).

Run from the project root:   streamlit run app/streamlit_app.py

The app is a reusable front end for the validated pipeline: it holds no results
of any particular chat. A user uploads a compatible export (or loads the
synthetic demo chat); the pipeline runs in a temporary directory that is
deleted afterwards; only the current successful run is kept, in this session's
memory.
"""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import theme  # noqa: E402
import ui  # noqa: E402
import views  # noqa: E402
from app_config import AppConfig  # noqa: E402
from demo_data import DEMO_FILENAME, build_demo_chat  # noqa: E402
from results_bundle import build_bundle  # noqa: E402
from run_manager import RunManager  # noqa: E402
from run_pipeline import STAGES  # noqa: E402

PAGES = {
    "Overview": views.render_overview,
    "Conversation": views.render_conversation,
    "NLP Insights": views.render_nlp,
    "Patterns": views.render_patterns,
}

st.set_page_config(page_title=ui.PROJECT_TITLE, page_icon=None, layout="wide")
ui.inject_css()

if "run_manager" not in st.session_state:                    # one manager per browser session
    st.session_state["run_manager"] = RunManager(AppConfig.from_env())
manager = st.session_state["run_manager"]
config = manager.config


def submit(data, name):
    """Run the pipeline with a visible progress panel; keep the old run on failure."""
    labels = [ui.STAGE_LABELS.get(stage, stage) for stage in STAGES]
    with st.status("Analysing the chat…", expanded=True) as status:
        board, position = st.empty(), [0]

        def progress(index, label):                          # real pipeline stages only, no fake percentages
            position[0] = index
            board.markdown(ui.stage_list(labels, index), unsafe_allow_html=True)
        outcome = manager.submit(data, name, progress=progress)
        if outcome == "failed":
            board.markdown(ui.stage_list(labels, position[0], failed=True), unsafe_allow_html=True)
            status.update(label="The chat could not be analysed", state="error", expanded=False)
        elif outcome == "replaced":
            board.markdown(ui.stage_list(labels, len(labels)), unsafe_allow_html=True)
            status.update(label="Analysis complete", state="complete", expanded=False)
        else:
            status.update(label="Already analysed", state="complete", expanded=False)


def apply_theme():
    pending = st.session_state.get("theme_pending")
    if pending is not None:
        st.session_state["theme"] = pending


def reset_theme():
    st.session_state.pop("theme", None)
    st.session_state["theme_n"] = st.session_state.get("theme_n", 0) + 1       # new key: clears the uploader


# ----------------------------------------------------------------- sidebar ---
with st.sidebar:
    ui.brand()
    page = st.radio("Navigate", list(PAGES), label_visibility="collapsed")
    st.divider()

    ui.sidebar_label("Upload chat")
    upload = st.file_uploader("Exported chat (.txt)", type=["txt"], label_visibility="collapsed",
                              help=f"Bracketed WhatsApp .txt export. Limit {config.max_upload_mb:g} MB.")
    st.caption("A WhatsApp export as a .txt file. Processed for this session only.")
    if st.button("Load synthetic demo", help="Invented sample data; no real chat is used.",
                 use_container_width=True):
        submit(build_demo_chat().encode("utf-8"), DEMO_FILENAME)
    upload = upload or st.session_state.get("main_upload")            # the call-to-action uploader of the empty dashboard
    if upload is not None and upload.file_id != st.session_state.get("last_upload_id"):
        st.session_state["last_upload_id"] = upload.file_id     # process each uploaded file once, not on every rerun
        submit(upload.getvalue(), upload.name)

    st.divider()
    run = manager.current
    ui.sidebar_label("Current run")
    if run is None:
        st.caption("No chat loaded")
    else:
        st.markdown(ui.badge("Analysis ready", "ok"), unsafe_allow_html=True)
        st.markdown(f"`{run.filename}`")
        st.caption(f"{run.info['n_rows']:,} parsed rows · {run.info['n_text_messages']:,} text messages")
        st.caption(f"{run.info['first_timestamp'][:10]} → {run.info['last_timestamp'][:10]} "
                   "(as recorded; time zone unverified)")
        st.download_button(
            "Download anonymised results (zip)",
            data=build_bundle(run, config.min_term_messages, False),
            file_name="anonymised_results.zip", mime="application/zip",
            help="Counts, dates, pseudonyms and aggregate word tables (single-message terms hidden). "
                 "No raw text, senders or links.", use_container_width=True)
        if st.button("Clear current run", use_container_width=True):
            manager.clear()
            st.rerun()
    # ---- optional theme image: presentation only, session memory only, never part of any download ----
    st.divider()
    ui.sidebar_label("Dashboard theme")
    theme_file = st.file_uploader(
        "Theme image", label_visibility="collapsed", key=f"theme_file_{st.session_state.get('theme_n', 0)}",
        help="Optional. A PNG, JPG, JPEG or WEBP image whose colours style the dashboard header and accents. "
             "It is kept in this session only and is never stored, analysed or downloaded.")
    pending = None
    st.session_state.pop("theme_pending", None)
    if theme_file is not None:
        try:
            pending = theme.build_theme(theme_file.getvalue())
            st.session_state["theme_pending"] = pending              # read by the Apply callback on the next run
            st.image(pending.preview, width=150)
        except theme.ThemeError:
            st.warning(theme.FRIENDLY_ERROR)
            st.caption(f"What to do: {theme.FRIENDLY_HINT}")
        except Exception:                                   # a theme problem must never break the analysis
            st.warning(theme.FRIENDLY_ERROR)
            st.caption(f"What to do: {theme.FRIENDLY_HINT}")
    t1, t2 = st.columns(2)
    # callbacks run before the script on the next run, so a quick click elsewhere cannot lose the action
    t1.button("Apply Theme", type="primary", disabled=pending is None, use_container_width=True,
              on_click=apply_theme)
    t2.button("Reset Theme", disabled="theme" not in st.session_state, use_container_width=True,
              on_click=reset_theme)
    try:
        st.markdown(theme.theme_css(st.session_state.get("theme")), unsafe_allow_html=True)
    except Exception:
        pass                                                # fall back to the default theme
    with st.expander("Privacy and limits"):
        st.caption("The raw upload is not stored after the run. Only anonymised aggregate tables are held "
                   "in this session. Sender names, phone numbers, links and message text are not shown. "
                   "Words in the NLP tab may include names; single-message terms are hidden by default "
                   "(a precaution, not complete PII detection). Only the bracketed WhatsApp .txt export "
                   "format is supported; other export styles are not.")

# -------------------------------------------------------------------- main ---
if manager.last_error is not None:
    st.error(manager.last_error.message)
    hint = ui.error_help(manager.last_error.code)
    if hint:
        st.caption(f"What to do: {hint}")
    if manager.current is not None:
        st.info(f"The previous successful run (`{manager.current.filename}`) is still shown below.")

def upload_cta():
    st.file_uploader("Upload a WhatsApp .txt export", type=["txt"], key="main_upload", label_visibility="collapsed",
                     help=f"Bracketed WhatsApp .txt export. Limit {config.max_upload_mb:g} MB.")
    if st.button("Load synthetic demo", key="main_demo", use_container_width=True,
                 help="Invented sample data; no real chat is used."):
        submit(build_demo_chat().encode("utf-8"), DEMO_FILENAME)
        st.rerun()


if manager.current is None:
    ui.empty_dashboard(upload_cta)
else:
    for warning in manager.current.warnings:
        st.warning(warning)
    PAGES[page](manager.current, config)
