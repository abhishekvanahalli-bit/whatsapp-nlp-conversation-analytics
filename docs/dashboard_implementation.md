# Dashboard Implementation Summary (Milestone 5)

Implements the approved design in `docs/dashboard_design.md` (Streamlit + Plotly). The application is a
reusable front end for the validated pipeline: it contains no results of any particular chat. Descriptive
results only; nothing here is a statistical claim about any group.

## Run it

```
pip install -r requirements.txt          # streamlit, plotly, pandas, numpy (scikit-learn optional)
streamlit run app/streamlit_app.py       # from the project root
python -m pytest tests                   # full test suite (needs requirements-dev.txt for pytest)
python scripts/benchmark_pipeline.py     # re-measure pipeline timings on your machine
```

Limits and display settings are configurable by environment variable (`WA_MAX_UPLOAD_MB`,
`WA_MAX_PARSED_ROWS`, `WA_MAX_TEXT_MESSAGES`, `WA_TINY_CHAT_TEXT_MESSAGES`,
`WA_SMALL_CHAT_TEXT_MESSAGES`, `WA_MIN_TERM_MESSAGES`, `WA_TOP_K_DEFAULT`); see `src/app_config.py`.

## Structure

| File | Role |
|---|---|
| `app/streamlit_app.py` | Entry point: sidebar (navigation, upload, demo, current run, download), progress panel, error display |
| `app/views.py` | The four pages: Overview, Conversation, NLP Insights, Patterns |
| `app/charts.py` | Plotly figure builders (pure functions) |
| `app/ui.py` | Styling, metric cards, explainability panels, empty state |
| `src/run_pipeline.py` | Validation + per-upload temporary-directory adapter + result loading |
| `src/run_manager.py` | Session run management (replace on success, keep on failure); no Streamlit dependency |
| `src/display_privacy.py` | Display-layer filter for terms (single-message terms hidden by default) |
| `src/results_bundle.py` | In-memory anonymised results zip |
| `src/demo_data.py` | Synthetic demo chat and scalable synthetic chats (tests and benchmarks) |
| `src/app_config.py` | Configurable limits |
| `scripts/benchmark_pipeline.py` | Pipeline timing measurements |
| `.streamlit/config.toml`, `requirements*.txt` | Light theme, no usage statistics, dependency declarations (runtime and development requirements are separate) |

Existing validated modules are reused unchanged, except `src/conversation_analytics.py`, which was
hardened for zero-text and unreadable-date input (below).

## Runtime flow (as approved)

Upload → validate → temporary run directory → parse → preprocess → n-grams → TF-IDF → conversation
analytics → privacy filtering → load anonymised results → render → delete the temporary directory.

- The temporary directory is created outside the project `results/` folder (checked in code) and deleted
  in a `finally` block, so it is removed after success and after failure.
- Only a whitelist of anonymised outputs is loaded. `processed_chat.csv`, `analysis_corpus.csv` and the
  message-level TF-IDF table are never loaded, displayed or offered for download; loading fails if a
  table has a column such as sender or message text. Term lists in the TF-IDF metadata are dropped.
- Session memory holds only the current successful run. A successful new upload replaces it; a failed new
  upload leaves the previous run visible with the error above it. Re-running the script with the same file
  does not reprocess it. No server-side history and no process-wide cache exist.
- The upload's raw bytes are not kept after the run; the file name is shown as the current-run label.

## Validation and errors

| Situation | Behaviour |
|---|---|
| Not `.txt` | Rejected: "Please upload the exported chat as a .txt file." |
| Empty or whitespace only | Rejected: "The file is empty." |
| Not UTF-8 | Rejected with a plain message (a UTF-8 BOM is tolerated) |
| Not the supported bracketed export format (other export styles, free text) | Rejected as unsupported format, showing the expected line shape |
| Timestamps present but none readable (for example day-first with days above 12) | Rejected with a hint that dates are read as Month/Day/Year, 12-hour clock |
| Above configured upload / row / text-message limits | Rejected, naming the configured limit |
| Some unreadable timestamps, skipped lines | Warning with counts only (line content is never shown) |
| Very small chat | Not rejected; limited-data warning (fewer than 3 text messages: rankings and stability not meaningful; fewer than 50: illustrative) |
| No text messages | Not rejected; overview and composition shown, warning that text analyses are empty |
| Unexpected analysis error | Generic message naming the stage; no internals or file content |
| Privacy check failure on loaded tables | Outputs withheld |

The parser never fails on non-chat text (it always labels line 1 a header), so validation is done by the
application on the parser output.

**Dates:** the parser's Month/Day/Year interpretation is unchanged and shown with the parsed date range,
plus evidence about the date order (day values above 12 are consistent with Month/Day/Year; when all
values are 12 or below the order cannot be confirmed, and the warning says so). Timestamps are as recorded
in the export; no time zone is claimed and the interface says it is unverified.

**Media placeholders:** the types listed in `supported_formats.md` (bracketed and bare wording) are counted as media; other placeholder styles are counted as text.
Messages that look like other placeholders (for example an audio placeholder) are counted as text and
produce a warning; they are not silently treated as confirmed media.

## Zero-text hardening (`src/conversation_analytics.py`)

The module previously crashed on zero text messages (`int()` of an empty maximum), on a chat with no valid
timestamps, and on reconciliation when some rows had unreadable dates. It now returns empty/zero tables
(empty daily table, NaN length statistics with n = 0), reconciles daily counts against the rows that have
valid timestamps, and adds `limited_result` and `limitation_reasons` to the metadata **only when limited**.
For the project chat the ten outputs regenerate byte-identically to the existing result files (test
`test_hardening_leaves_existing_outputs_byte_identical`), and all 58 earlier tests still pass.

## Privacy

- Nothing shown or downloadable contains raw phone numbers, sender identifiers, personal names from
  system messages, invite URLs or message text: tables carry counts, dates, `Participant_N`, generic
  system categories and anonymous template ids.
- `Participant_N` is assigned per run by first appearance across all user rows; the mapping is not kept,
  and existing NLP `Sender_N` labels are neither loaded nor shown.
- Term display filter: terms occurring in only one message are hidden by default (n-gram tables by
  messages-containing count; TF-IDF tables by document frequency in the primary variant), plus a defensive
  drop of terms that look like links, addresses or long digit runs. A toggle can reveal single-message
  terms. This changes only what is displayed or downloaded, never the analysis. It is a precaution
  against exposing low-frequency identifying terms, not complete PII detection: a name used in several
  messages is still shown.
- Demo mode uses a synthetic chat (invented names, `example.com` links); a test checks that no line of the
  real project chat appears in it (WhatsApp's standard header notice aside).
- Tests load sensitive values (fake phone-number senders and text numbers, a fake personal name in a
  sender, in text and in a system row, invite URLs, a single-use rare term, full message text) from a
  synthetic chat at test time and assert none appears in the display-ready tables, run metadata, warnings,
  download bundle, or in the text rendered on any of the four pages (headless UI test), including after a
  real file upload through the UI.

## Pages

| Page | Contents |
|---|---|
| Overview | Eight metric cards (parsed, user, text, unique text, media, deleted, forwarded, system rows), consistency-check badge, small-chat badge, composition chart, date range with the assumed format and date-order evidence, current-run and privacy status, explainability panel |
| Conversation | Daily activity timeline (zero-filled calendar), composition, metadata summary table, descriptive participant counts (no ranking; caution note), collapsed hour histogram and weekday table |
| NLP Insights | Toggle for single-message terms, top-k slider, tabs: Unigrams (stopword toggle, rank by all/unique, script note), Bigrams, Trigrams, TF-IDF (primary/sensitivity variant, total/mean metric) |
| Patterns | Repetition metrics, unique versus repeated, repeated templates (anonymous ids), explanation of how repetition affects n-gram and TF-IDF reading, repetition-effect table (all versus unique counts, TF-IDF rank change). No fuzzy similarity |

Participants are a section of the Conversation page, not a page. No sentiment, reply network, fuzzy
duplicates or unsupported formats were added.

Visual design (superseded by the final redesign below): light theme, restrained palette (one fixed colour per row kind, drawn from the validated
categorical slots in fixed order), metric cards, interactive Plotly charts with tooltips and legends, a
stage-by-stage progress panel, empty states, collapsed "What am I looking at?" panels giving what is
measured, how it is calculated, why it is shown and the limitation. No animation.

## Measured pipeline timings (this machine; not guarantees)

Synthetic chats from `scripts/benchmark_pipeline.py`, one run each after a warm-up, all stages (Windows,
Python 3.12, single process):

| Text messages | File size | Total | TF-IDF stage | Analytics stage | N-gram stage |
|---|---|---|---|---|---|
| 25 | 3 KB | 0.78 s | 0.30 s | 0.27 s | 0.10 s |
| 100 | 10 KB | 0.98 s | 0.58 s | 0.22 s | 0.10 s |
| 300 | 28 KB | 2.63 s | 1.93 s | 0.55 s | 0.08 s |
| 1,000 | 95 KB | 15.30 s | 14.36 s | 0.69 s | 0.15 s |
| 2,000 | 190 KB | 54.09 s | 51.56 s | 1.90 s | 0.46 s |
| 3,000 | 286 KB | 115.61 s | 111.85 s | 2.91 s | 0.62 s |

The TF-IDF stage dominates and grows roughly with the square of the message count (its leave-one-out
stability diagnostic recomputes TF-IDF once per message). The default limits follow from this: 1,000
text messages (about 15 s here), 10,000 parsed rows, 10 MB upload (file size is a weak cost driver).
They are protective settings, configurable, and should be re-measured on the deployment machine.

## Tests

At the time of this milestone the full suite was 109 tests (58 existing + 51 new), all passing. **Current
status after the final audit and completion pass: 304 tests** (see `docs/final_verification.md` and
`docs/project_freeze.md`).
New: `tests/test_dashboard_core.py` (validation and error handling, empty and invalid input, zero-text and
no-timestamp analytics, hardening regression against the existing outputs, temporary-directory cleanup on
success/failure/crash, run replacement, failed second upload, no reprocessing on rerun, pseudonym
generation, privacy filter, no sensitive values in display-ready data and the download, demo data, oracle
comparison against the development results) and `tests/test_dashboard_app.py` (headless Streamlit UI:
empty state, demo end to end, four pages, upload flows, failed second upload, zero-text pages, temp
cleanup through the UI, sensitive values never rendered).

## Limitations and known issues

- **Format:** only the bracketed `[M/D/YY, H:MM:SS AM/PM]` export validated on the project chat is
  supported. Other export styles are rejected, not guessed. English-only patterns (system messages,
  deleted/forwarded markers, media placeholders) are only confirmed for that export.
- **Ambiguous date order:** a day-first export whose values are all 12 or below is read as Month/Day/Year
  and cannot be told apart; the interface shows the range and a warning so it can be checked.
- **Terms and names:** words shown in the NLP views come from the chat. Names used in more than one
  message are still displayed; the filter is a precaution, not PII detection.
- **Scale:** the TF-IDF stage is roughly quadratic; the configured 1,000-message limit reflects it.
- **Hosting:** a hosted deployment uploads chats to the server. Local use gives the strongest privacy.
  Streamlit's own request handling is outside this project's control.
- **Verification scope:** interface behaviour was verified with Streamlit's headless test harness
  (including simulated file uploads) and by starting the real server (health endpoint and root page
  responded). A browser was not available in this environment, so charts were not inspected visually
  and real drag-and-drop uploads were not exercised.
- **Cost of the first run:** the first analysis in a process is slower because of library imports.
- **Unrecognised placeholders** are counted as text (with a warning), so they can appear in the NLP
  tables.
- **Existing validated modules:** n-gram, TF-IDF and preprocessing behaviour is unchanged; sentiment is
  excluded, as before.


## Final redesign, theme image and generalisation (2026-10-05, light design)

* **Light, soft analytics design.** One design system defined by CSS variables (`app/ui.py`): a soft grey page, white sidebar, cards and chart
  panels with a subtle border and shadow, dark text (`#172033`, contrast above 14:1) and muted text (`#5b6678`, above 5:1), one blue accent and one
  teal accent (both above 4.5:1 on the cards and on the page). Charts use transparent backgrounds so they follow their white panel; the four row kinds
  keep fixed, distinguishable colours (text blue, media orange, deleted green, system amber) and bar labels switch between white and dark text by contrast.
* **Sidebar.** Compact: app identity, four navigation items with small line icons (CSS masks, no emoji or icon font, so no broken glyphs), upload,
  current run, theme controls, privacy note. The selected item has an accent background and accent text.
* **Overview.** Five KPI cards (Total Messages, Participants, Text Messages, Media / Deleted, Active Days; all from existing tables), Daily Activity and
  Message Composition, Key Findings (at most four) and the methods checklist, then Top Key Terms and Script Mix panels that reuse the already
  privacy-filtered tables. **Conversation** has its own KPI row (Participants, Forwarded Messages, Messages With Links, Repeat Messages). **NLP Insights**
  shows chart, then explanation, then the supporting table in a collapsed expander. **Patterns** shows the repetition summary, a repetition-detail card and the
  10 most repeated templates (the table lists all).
* **Theme image** (`app/theme.py`). An optional PNG/JPEG/WEBP (at most 8 MB and 36 megapixels) is decoded with Pillow. A saturation-weighted hue histogram of a
  48x48 thumbnail gives a primary and a secondary accent that are darkened until they reach 4.5:1 on both the card surface and the tinted page; the page, upload
  box and borders get faint tints of the main hue; text colours never change. A pale, washed strip of the image decorates the page header (its mean brightness is
  at least 0.88 whatever the image, so dark text stays readable). Dark, grey, near-white and colourless images fall back to the default palette. The theme lives in
  `st.session_state` only and is never saved, analysed or placed in the download. Apply/Reset use callbacks so a quick click elsewhere cannot lose the action.
  Failures show "Theme image could not be applied." with a hint and never affect the analysis.
* **Generalisation.** Every page was rendered for a one-to-one chat, 12- and 30-participant groups, a single sender, a zero-text chat and system-event and
  media-heavy chats (`tests/test_dashboard_app.py`, `scripts/browser_smoke_test.py` at 1366 and 1440 px). No chart plots participants, so the participant
  count does not change any chart; participant counts appear only as a number and as pseudonymised rows in a table.
* **Wording.** Script Mix text says "characters from more than one writing system"; no Hindi/Marathi language claim is made.
