# Dashboard Design Note (Milestone 5, design only)

> Status: **design only. No dashboard code, Streamlit files, charts or UI components were created; no
> packages were installed; no existing source, result, test or data file was modified.**
> Decision status: **APPROVED and IMPLEMENTED** (see `docs/dashboard_implementation.md`). The text below is the
> design as reviewed; updated status only (final audit 2026-10-01). Script Mix / Key Terms dashboard integration
> was completed in the final dashboard polish (NLP Insights tabs).
>
> Technology decision (given): **Streamlit**, using the existing Python analysis modules as the backend.
> Nothing about the current chat is hard-coded into the application: the current dataset is the
> validation/demo dataset, and the dashboard must run the same validated pipeline on any newly uploaded
> compatible export.
>
> CampusX WhatsApp Chat Analysis is inspiration/reference only for the idea of a descriptive chat
> dashboard. This design is independent.

## 0. Evidence used for this design

**Facts about the existing modules (read from the code):**

| Module | Entry point | Input | Writes | Notes relevant to the dashboard |
|---|---|---|---|---|
| `src/preprocessor.py` | `build_dataset(path)`, `run_quality_checks(df, failures)`, `save_processed_csv(df, out_path)` | a UTF-8 text file path | a CSV with **raw sender, message and tokens** | Never raises on unfamiliar text (see probe results); `save_processed_csv` output contains phone numbers and message text, so it is sensitive |
| `src/ngram_analysis.py` | `run_analysis(processed_csv, results_dir)` | processed CSV | `analysis_corpus.csv` (**contains masked message text**), `ngram_*.csv`, `ngram_script_diagnostics.csv` | `build_analysis_corpus`, `ngram_table`, etc. also accept DataFrames directly |
| `src/tfidf_analysis.py` | `run_tfidf(processed_csv, results_dir, ngram_dir)` | processed CSV | `tfidf_terms_by_message.csv`, `tfidf_top_terms.csv`, `tfidf_variant_comparison.csv`, `tfidf_run_metadata.json` | Optionally reads the n-gram unigram table from `ngram_dir` for the count comparison |
| `src/conversation_analytics.py` | `run_analytics(processed_csv, results_dir, tfidf_dir)` | processed CSV | 9 CSVs + `analytics_run_metadata.json` | Cross-checks against TF-IDF metadata if present in `tfidf_dir`, otherwise skips that check |

All entry points take **explicit paths**, so they can be run unchanged against a per-run temporary
directory. Their defaults point at the project's own `results/` folder, so a caller that forgot to pass
paths would overwrite development files. The application layer must never rely on defaults.

**Dependency order (from the code):** preprocess → n-gram → TF-IDF → analytics. (The requested flow lists
analytics before n-gram; the modules are independent apart from the two optional cross-reads above, and
this order keeps both cross-checks active.)

**Probing of the pipeline (read-only; temporary directories only, no project file touched).** I ran the
existing modules against small synthetic inputs to learn how they behave on uploads:

| Input | Parse result | N-gram / TF-IDF | Conversation Analytics |
|---|---|---|---|
| Current chat, unchanged / with CRLF line endings / with a UTF-8 BOM | same row count in each case | ok | ok |
| Empty file; whitespace only; free text that is not a chat | 1 "header" row (first line is always treated as a header), 0 to 2 "parsing failures", no exception | ok, but empty tables | **crashes** (`ValueError`, NaN to int, in the repetition step) |
| Other export style (`9/13/26, 2:11 PM - Ann: hi`) | 1 header row, 3 parsing failures, 0 messages | ok, empty | **crashes** (same) |
| 24-hour clock without AM/PM | 1 header row, 2 failures | ok, empty | **crashes** |
| Media-only chat (no text messages) | 2 user rows | ok, empty (N = 0) | **crashes** (`int(tmpl_sizes.max())` on zero text messages) |
| System-only chat | 1 system row | ok, empty | **crashes** |
| One text message | 1 user row | ok (TF-IDF N = 1) | ok |
| Two identical texts | 2 user rows | ok | ok |
| Day-first dates with a day above 12 (`25/09/26`) | rows parsed, every date invalid (NaT) | ok | **crashes** (`Neither start nor end can be NaT`) |
| Day-first dates with both numbers 12 or below (`05/09/26`) | parses **silently**, read as month/day | ok | ok, with dates silently swapped |

Consequences that drive the design: (1) the parser does not fail on non-chat input, so the application
must validate; (2) the analytics module fails on zero text messages or no valid timestamps, so the
application must guard it or the module must be hardened (open decision); (3) ambiguous day/month order
can be misread without any error.

## 1. Dashboard Goals

**Who it is for:** the MSc project author and assessors (demonstration and viva), and any person with their
own compatible WhatsApp export who wants a privacy-conscious, explainable descriptive summary.

**Questions it answers** (the project's RQ1 to RQ6, on whichever chat is loaded):
1. What is the chat made of? (user / system / text / media / deleted / forwarded) (RQ1)
2. When was it active, and were there bursts? (RQ2)
3. What kinds of rows and events occur, and who is present (descriptively)? (RQ1, RQ3)
4. Which words and phrases occur most, and how are they affected by repeated messages? (RQ4)
5. Which terms distinguish messages within this chat? (RQ6)
6. How much of the text is repeated, and how does that change the NLP reading? (RQ4)
7. How much can this chat support? (data-sufficiency and limitations) (RQ5 and the general limitations)

**How it differs from a CampusX-style descriptive dashboard** (described only as a reference approach:
message/word counts, word cloud, timelines, activity heatmaps):

| Aspect | Descriptive baseline (reference) | This dashboard |
|---|---|---|
| Input handling | Single assumed format | Format validation with explicit failure modes; assumptions shown |
| Method transparency | Charts only | Each section states what is measured, how, why, and the limitation |
| Repetition | Counted as usage | All-message vs unique-text views; a dedicated Patterns page |
| Language | English assumed | Script diagnostics; English-only stopword limitation shown |
| Privacy | Names/numbers in charts | Pseudonyms, masked links, no raw text; explicit privacy design |
| Claims | Rankings of people/words | Descriptive counts; no "most active" or engagement claims |
| Validation | None shown | Reconciliation checks surfaced from the run |
| Reuse | One chat | Runs the validated pipeline on any compatible upload |

**Why it suits an MSc Data Science project:** it exposes the validated methodology instead of hiding
it, demonstrates responsible handling of small, multilingual, privacy-sensitive data, and gives a live
way to show the pipeline during the viva.

## 2. Application Architecture

```
Upload (.txt)
  -> validation           [new application layer]
  -> parse + quality      [existing: preprocessor]
  -> preprocessing        [existing: preprocessor + analysis layer in ngram_analysis]
  -> N-gram analysis      [existing: ngram_analysis]
  -> TF-IDF               [existing: tfidf_analysis]
  -> Conversation Analytics [existing: conversation_analytics]
  -> runtime result set   [new application layer, in memory]
  -> visualisation        [new application layer: Streamlit pages]
```

| Layer | Contents | Status |
|---|---|---|
| Existing validated modules | `preprocessor`, `ngram_analysis`, `tfidf_analysis`, `conversation_analytics` (58 tests passing) | Reused as-is (any change needs separate approval and re-validation) |
| New application layer | upload validation, pipeline adapter (runs the modules against a per-run temporary directory and loads the anonymised outputs), runtime result container, privacy display filter, Streamlit pages | Not built |
| Development result files | `results/*.csv|json` for the current chat | Used for validation and as a **test oracle** for the adapter (see below); never read by the running app to display results |
| Runtime results | Tables produced for the uploaded file in a temporary location and held in session memory | Created per run, discarded per the runtime design (section 11) |

**No hard-coded values:** every number, label and chart is derived from the runtime result set. To verify
that, the adapter is tested by running it on the current chat and comparing the runtime tables with the
existing validated `results/` files (an equality test, not a display dependency). A second test runs it on
a different synthetic chat and checks that no value from the current chat appears.

**Proposed shape (not created yet):** `app/` (Streamlit entry point and page modules), a small adapter
module (for example `src/pipeline_runner.py`) and matching tests, all leaving the existing four modules
untouched.

**Two adapter options (open decision):**
- **A (recommended for the first implementation): temporary-directory adapter.** Runs the unchanged
  `run_*` functions against a fresh temporary directory, loads the outputs into memory, and deletes the
  directory immediately. Advantage: identical code path to the validated tests. Drawback: the sensitive
  processed CSV (raw sender and message text) exists on disk briefly.
- **B: in-memory adapter.** Refactor the modules to expose `compute_*` functions that return tables
  without writing files. Advantage: raw text never touches disk. Drawback: changes validated modules; needs
  new tests and re-validation.

## 3. Upload & Validation

The only format confirmed by this project is the one in the current export: lines of the form
`[M/D/YY, H:MM:SS AM/PM] Sender: message`, system lines of the form `[...] - text`, an optional first
line without a timestamp, and continuation lines for multi-line messages. No other format is claimed to be
supported, and none is guessed. Anything else is reported as unsupported.

| Stage | Check | On failure (user-facing outcome) |
|---|---|---|
| Type | Extension `.txt` | Reject: only `.txt` exports are accepted (zip archives or other files are not processed) |
| Size | Empty file, or only whitespace | Reject: "The file is empty." |
| Size limit | Upload size cap (configurable; value to be set after measurement) | Reject with the cap shown |
| Encoding | Decodes as UTF-8 (a BOM is tolerated in the probe on the current chat; a BOM ahead of a first-line timestamp is untested, so the adapter should decode with `utf-8-sig`) | Reject: "The file is not readable as UTF-8 text." (the parser raises on undecodable bytes, so this must be caught) |
| Format | At least one timestamped line parsed as a user or system message | Reject as **unsupported format** with a description of the expected line shape and an example with fake data |
| Timestamps | Share of timestamped rows whose date/time fails to parse (`invalid_timestamps` from `run_quality_checks`, minus the untimed header) | All invalid: reject with "dates are not month/day/year" hint. Some invalid: warning with counts |
| Date order | The parser reads dates as month/day/year; a day-first file whose values are all 12 or below is read silently as month/day | Always show "Dates were read as month/day/year; range: first to last date as exported" for confirmation, so a swapped reading is visible |
| Text content | At least one text message (not media/deleted/system) | Guard: show the parse summary only, and state that analysis needs at least one text message (the analytics module fails on zero text messages) |
| Parser failures | `parsing_failures` count from the parser | Warning with the count only. **Failing lines are never displayed** (they may contain personal content) |
| Unrecognised media placeholders | The parser recognises the placeholder types listed in `supported_formats.md` (Android and iOS wording). Other placeholder styles in a new export are treated as text (with a warning for omitted-style lines) | Known limitation, shown as a caveat; whether to add detection or extend the parser needs evidence from real exports and is an open decision |

**Privacy messaging on the upload screen (before any file is chosen):**
- The file is processed for this session only; its raw content is not stored beyond the run.
- Phone numbers, senders, names, links and message text are not shown; participants appear as
  `Participant_N`.
- Words and phrases shown in the NLP pages come from the chat and may include names; nothing is sent to
  third-party services.
- If the app is hosted (not local), the file is uploaded to the server running it. Only upload chats you
  are entitled to analyse.

## 4. Dashboard Navigation

Evaluated options: one long page (rejected: hard to explain in a viva, heavy to render); many small
pages (rejected: unnecessary); **four pages (recommended)**, matching the four validated result families:

| Page | Contents | Backed by |
|---|---|---|
| **A. Overview** | Upload, run status, data-sufficiency badge, headline metrics, integrity summary | parse + all three modules' metadata |
| **B. Conversation** | Composition, daily timeline, metadata summary, descriptive participant counts, limited hour/weekday | Conversation Analytics |
| **C. NLP Insights** | Tabs: unigram, bigram, trigram, TF-IDF; script/language note | n-gram and TF-IDF outputs |
| **D. Patterns** | Repetition: exact vs template, groups, unique vs repeated, effect on terms | Conversation Analytics + n-gram / TF-IDF comparison tables |

A persistent sidebar holds the upload control, current-run summary, and a "how to read this" link. No fifth
page: method notes are shown inside each page (section 15).

## 5. Overview Page

Purpose: orient the reader and state how much the chat can support, before any chart.

**Metrics chosen (each is a count with the denominator or context visible):**
- Parsed rows (the reconciliation anchor)
- User rows
- Text messages (the NLP base)
- Unique text messages (after URL masking)
- Media rows
- Deleted rows
- Forwarded rows
- Date range as exported and the number of active dates

**Rejected as headline metrics:** any percentage of behaviour, "average messages per day", participant
rankings (misleading at small sizes). System rows and header are shown in the composition breakdown on
the Conversation page, not as headline cards.

**Also on the page:**
- **Data-sufficiency badge** (for example "Very small chat: N text messages"). The thresholds are a design
  proposal (open decision), not a statistical claim.
- **Integrity strip:** "All reconciliation checks passed (n of n)", taken from the run metadata (28 for
  the current chat, computed for any run).
- **Assumptions strip:** dates read as month/day/year; time zone not verified; English-only stopwords.

## 6. Conversation Page

Uses only the approved Conversation Analytics scope.

| Component | Content | Priority |
|---|---|---|
| Row composition | Stacked bar: parsed rows (header / system / user) and user rows (text / media / deleted) | Prominent |
| Daily activity timeline | Zero-filled calendar, stacked by text / media / deleted / system | Prominent |
| Metadata summary table | Forwarded, deleted (with same-date and same-second clusters), media types, URL presence, system categories | Secondary (table) |
| Participant counts (descriptive) | `Participant_N` counts table with a caution note (section 9) | Secondary |
| Hour-of-day histogram, weekday table | Small, collapsed by default ("Limited descriptive detail") | Appendix-level |

Excluded (approved scope): morning/afternoon/evening/night grouping, message length over time,
per-sender comparisons, reply networks.

Standing captions: "Time zone of the export is not verified; timestamps are shown as written." and
"Descriptive of this chat only."

## 7. NLP Insights Page

A tabbed design (one clear chart per tab, controls at the top of the tab):

| Tab | View | Controls | What the visual means |
|---|---|---|---|
| Unigrams | Horizontal bars of the top terms (stopwords removed), with `count_all` and `count_unique` shown together | Top-k; with/without English stopwords (both tables exist) | How often a word occurs overall, and how much of that is repetition |
| Bigrams | Same layout, stopwords kept | Top-k | Adjacent word pairs as written |
| Trigrams | Same layout | Top-k | Three-word runs as written |
| TF-IDF | Bars of top terms by total normalised TF-IDF; table with document frequency, IDF and the script | Variant (all messages = primary, unique texts = sensitivity); metric (`total_tfidf` or `mean_tfidf_in_docs`); top-k | Distinctiveness within this chat: frequent in a message and rare across messages |

Persistent panels: (1) a script note from `ngram_script_diagnostics` showing that English-only stopword
removal affects Latin and Devanagari tokens differently; (2) the standing caption "Descriptive of this
chat; not generalisable; a high TF-IDF means distinctive within this chat, not important in general."

**Privacy for terms:** words and phrases necessarily come from the chat. Defaults: show terms and phrases
that occur in more than one message, and do not display message-level term tables (they can reconstruct
content). Both are open decisions (section 20).

## 8. Patterns Page

The differentiating page: what is repeated, and how repetition changes the NLP reading.

| Component | Content |
|---|---|
| Unique vs repeated | Text messages = unique texts + repeat messages (first copy not counted as a repeat) |
| Exact vs masked-template repetition | Exact raw duplicates vs repeats visible only after URL masking, as separate counts |
| Repeated templates | Anonymous ids (T1, T2, ...) with occurrences, distinct raw texts, whether exact-identical, whether they contain a URL, first and last date |
| Repetition effect on terms | Table from the existing comparison output: for the top terms, `count_all` vs `count_unique` and TF-IDF rank in the primary vs the sensitivity variant |

**How to read it (shown on the page):**
- *n-grams:* repeated messages inflate counts; `count_unique` shows the count if each distinct text were counted once.
- *TF-IDF:* repeated messages raise a term's document frequency and so lower its IDF; the primary variant keeps repeats, the sensitivity variant collapses them, and rank changes show how much repetition matters.
- Repetition is counted, not explained: the data cannot show why a message was sent again.

**Not included:** fuzzy or near-duplicate similarity (not implemented). Template text is never displayed;
groups are anonymous ids.

## 9. Participant Information

**Placement:** a small table on the **Conversation** page (secondary), under the metadata summary, with a
visible caution. Not on the Overview headline and not in a chart.

**Rules:**
- Columns: `Participant_N`, user rows, text messages, media rows, deleted rows, forwarded rows, and the
  total user rows as denominator (the existing output).
- No sorting by count in a way that implies a ranking (fixed order of first appearance), no bar chart, no
  leaderboard, no "most active", no percentages, no engagement wording.
- Caution text: "Counts only. Participants are pseudonymised. Counts are not a measure of engagement or
  participation and are not compared between participants."
- The Participant scheme is assigned per run by first appearance across all user rows; it has no meaning
  across runs (Participant_1 in one chat is unrelated to Participant_1 in another).

## 10. Privacy Design

**Never displayed or offered for download:**
- Raw phone numbers and raw sender identifiers (including sender names)
- Personal names (including those inside system messages such as security-code notices)
- Raw invite/access URLs
- Raw message text, raw system-message text, and lines that failed to parse
- `processed_chat.csv` and `analysis_corpus.csv` (the latter contains masked message text)
- Message-level TF-IDF tables (`tfidf_terms_by_message.csv`), which map terms to individual messages

**Allowed to display:** counts, dates, generic system categories, `Participant_N`, template ids,
aggregate term/phrase tables (subject to the term-display filter in section 7).

**How `Participant_N` is generated for a run:** by the existing analytics logic, in order of first
appearance across all user rows of the uploaded file. Only the list of pseudonyms is produced; the
mapping from real sender to pseudonym is not kept, displayed or written, and no crosswalk is created.
Because it is per run, pseudonyms cannot be linked across uploads.

**Retention:** raw uploaded files should **not** be retained. The upload is held in memory for the run;
with adapter A the sensitive processed CSV lives in a temporary directory only until outputs are loaded
and is then deleted (also on error). Only the anonymised aggregate tables stay in session memory.

**Safeguards to build and test at implementation time:**
- The adapter always passes explicit temporary paths and asserts they are outside the project `results/` directory (development files must never be overwritten).
- Runtime leak tests, extending the existing ones: sender values, phone numbers, system-row names, URLs and message text loaded from the uploaded file must not appear in anything the UI renders or offers for download.
- A test that the temporary directory is removed after success and after failure.

**Residual risks (to state in the app and report):** aggregate words can still include names; pseudonymised
counts can identify roles to group members; if hosted, the server receives the file. Privacy is an ongoing
requirement, not a solved property.

## 11. Runtime / Session Architecture

Scenario: Chat A uploaded → Chat A analysis; then Chat B uploaded → Chat B analysis.

| Option | Description | Assessment |
|---|---|---|
| **1. Current run only, in session memory (recommended)** | Results for the most recent upload live in the user's session; a new upload replaces them after the pipeline succeeds | Simplest, strongest privacy, easy to explain |
| 2. Temporary server-side storage | Runs saved for a limited time | More risk for no clear benefit here |
| 3. Persistent previous runs | History of chats | Stores sensitive derived data; needs accounts, retention policy; out of scope |
| 4. Download of results | User saves an anonymised results bundle | Useful; compatible with option 1 |

**Recommendation:** option 1 plus a user-initiated **download of anonymised outputs** (generated in memory).
Behaviour:
- Session state holds one run: file fingerprint (hash), run metadata, and the anonymised tables.
- A new upload computes to a new result set; only when it succeeds does it replace the old one (a failed
  Chat B upload leaves Chat A visible with a clear error, or is cleared, per review).
- A visible "Current file" label shows the file name and hash prefix so a viewer never confuses runs.
  (The file name may contain personal information; showing only the hash prefix is an open decision.)
- **Caching:** cache within the session, keyed by the content hash, so re-rendering or changing widgets
  never re-runs the pipeline. No process-wide cache that could outlive the session with chat-derived
  data. Nothing is cached to disk.
- **Download bundle** (open decision on contents): the anonymised analytics tables and run metadata, and
  the aggregate n-gram/TF-IDF tables after the display filter; never the excluded files in section 10.

## 12. Error Handling

User-facing messages are plain language, state what happened and what to do, and never echo file content.

| Situation | Message (intent) |
|---|---|
| Wrong file type | "Please upload the exported chat as a .txt file." |
| Empty file | "The file is empty." |
| Not UTF-8 | "This file could not be read as UTF-8 text. Export the chat again as text." |
| Unsupported format | "This does not look like a supported export. Expected lines like `[M/D/YY, H:MM:SS AM/PM] Name: message`. Other export styles are not supported yet." |
| Dates invalid | "Most dates could not be read. The app expects month/day/year." |
| Parse warnings | "N lines could not be interpreted and were skipped." (count only) |
| No text messages | "No text messages were found (only media, system or deleted rows). The overview is available; text analysis needs at least one text message." |
| Too little text | "Very few text messages: results below are illustrative." |
| Analysis failure | "The analysis stopped unexpectedly. Your file was not stored. (Reference code.)" Details go to a local log without chat content. |
| Privacy check failure | "Outputs were withheld because a privacy check failed." (Nothing displayed.) |
| Reconciliation check failed | "An internal consistency check failed for this file; results are shown as unverified." (or withheld, open decision) |
| Upload too large | "The file exceeds the size limit." |

## 13. Visual Design

Modern, restrained, suitable for a demonstration. Not a copy of any existing dashboard.

| Decision | Choice | Reason |
|---|---|---|
| Theme | **Light, soft** analytics theme (final redesign) with an optional theme image that restyles accents and surfaces; the interface always stays light and readable | Readable cards and charts; see `dashboard_implementation.md` (final redesign) |
| Colour | One accent colour plus a fixed, colour-blind-safe categorical palette for row kinds (text / media / deleted / system), reused on every chart | Consistent meaning across pages |
| Typography | Platform default sans-serif, clear hierarchy (page title, section heading, caption) | Legible, no font dependency |
| Cards | Metric cards in a single row for the Overview; each shows count and denominator | Fast orientation |
| Spacing | Generous whitespace, one primary visual per section | Reduces clutter |
| Sidebar | Upload, current-run summary and navigation | Persistent context |
| Charts | Interactive, declarative charts with tooltips, direct labels and readable axes; no 3D, no decorative effects | Explainable |
| Tables | Compact, sortable only where a ranking is meaningful (not for participants) | Avoid implying rankings |
| Badges | Small labels: script (Latin / Devanagari), variant (primary / sensitivity), data-sufficiency | Convey status at a glance |
| Empty states | Before upload: what the app does, the expected format with fake data, privacy summary | Guides first use |
| Loading | A single progress panel listing stages (validate, parse, preprocess, n-gram, TF-IDF, analytics) with step status | Honest progress without invented timings |
| Motion | None beyond the progress panel | Professional, low-distraction |

**Charting library (open decision):** the installed environment has matplotlib and seaborn, but not
Streamlit or an interactive charting library. An interactive declarative library that installs with
Streamlit would suit tooltips and direct labelling; static matplotlib figures would work without extra
installs but look less modern. Installing packages needs your approval.

## 14. Approved Visualizations

| Visual | Page | Prominence | Why |
|---|---|---|---|
| Row composition stacked bar | Conversation (and headline metrics on Overview) | **Prominent** | Frames everything |
| Daily activity timeline | Conversation | **Prominent** | Answers "when", shows empty dates and bursts |
| Repetition summary (unique vs repeated + repeated templates) | Patterns | **Prominent** | The project's distinguishing analysis |
| N-gram bars (unigram / bigram / trigram) with all-vs-unique | NLP Insights | **Prominent** | Core lexical view |
| TF-IDF bars with variant toggle | NLP Insights | **Prominent** | Distinctiveness view |
| Metadata summary table | Conversation | Secondary | Exact context |
| Participant counts table | Conversation | Secondary (with caution) | Descriptive only |
| Script diagnostics | NLP Insights | Secondary | Shows the mixed-language limitation |
| Repetition-effect table (all vs unique counts, TF-IDF rank change) | Patterns | Secondary | Links repetition to interpretation |
| Hour histogram, weekday table, text-length summary | Conversation (collapsed) | Appendix-level | Burst-driven or tiny counts |

## 15. Explainability

Each section carries a collapsed "What am I looking at?" panel with the four elements below, so the
dashboard helps in a viva as well as looking good.

| Section | What is measured | How it is calculated | Why shown | Limitation communicated |
|---|---|---|---|---|
| Headline metrics | Row counts by type | Parse then classify each row once; counts must reconcile (parsed rows = header + system + user) | Anchor for everything | Counts of this export only |
| Row composition | Text / media / deleted / system shares of rows | Counts with denominators | Shows how little is text | Media and deleted content unobservable |
| Daily activity | Rows per calendar date | Zero-filled calendar from first to last timestamp | When and how bursty | Time zone unverified; no trend claims |
| Metadata summary | Forwarded, deleted, URL, media types, system categories | Counts from existing flags | Context | Pattern-based detection; English markers only |
| Participants | User rows per pseudonym | Count of rows per `Participant_N` | Context | Not engagement; no comparison |
| Unigram / bigram / trigram | Term and phrase counts | Per-message n-grams (never across messages); `count_all` vs `count_unique` | Vocabulary and phrasing | Small samples; repetition inflates counts |
| TF-IDF | Distinctiveness within the chat | `tf * idf`, smoothed IDF, L2-normalised per document; N = number of documents including empty ones | Which terms distinguish messages | Not importance; unstable at small N |
| Repetition | Exact and masked-template repeats | Identical raw text vs identical text after URL/phone masking | Explains NLP prominence | Exact/masked only; no fuzzy similarity |
| Script note | Effect of English stopwords by script | Token counts before and after removal | Shows the mixed-language limitation | No Marathi/Hindi stopword handling |

## 16. Performance

No performance figures are claimed; none have been measured for uploads.

Design expectations, with code-level observations:
- **Determinism:** the modules are deterministic (verified by tests), so results can be cached by content hash.
- **Caching:** session-scoped, keyed by the content hash; widgets (top-k, toggles, tabs) only filter the loaded tables and never re-run the pipeline.
- **Cost drivers seen in the code:** TF-IDF builds a dense documents-by-vocabulary matrix, and the leave-one-out stability diagnostic recomputes TF-IDF once per document, so its cost grows roughly with the square of the number of messages. For large chats this diagnostic (and possibly the dense matrix) will need a cap or a skipped/"not computed" state. Thresholds must be set after measuring on synthetic larger chats, not assumed.
- **Progress:** stage-by-stage progress panel; the UI stays responsive by never rendering before the run completes.
- **Size limits:** an upload cap and a message-count guard chosen after measurement, with a clear message when exceeded.
- **Rendering:** cap table rows shown, and paginate rather than render large tables.

## 17. Current Dataset vs New Dataset

- The current project chat is the **validation/demo dataset**. Its verified outputs (58 tests, 28
  reconciliation checks) are the reference for checking that the dashboard's pipeline reproduces the
  validated numbers.
- The final dashboard runs the **same validated pipeline on a newly uploaded compatible export**. It has no
  built-in knowledge of the current chat. If a demo mode is offered, it is just another upload
  (a local file when available; open decision on a synthetic sample for public demos).
- **Compatible** means the export format in section 3. Chats from other apps or export styles are
  unsupported, and English-only patterns (system messages, media placeholders, "deleted" and "Forwarded"
  markers) are only confirmed for the current export; other locales are unverified.

**Minimum data and limited insights** (thresholds are proposals for review):

| Analysis | Minimum for any output | Limited insight when |
|---|---|---|
| Overview / composition | At least one timestamped row | Very few rows |
| Daily timeline | At least one timestamped row with a valid date | A single date or all dates invalid |
| Conversation Analytics module | At least one text message and one valid timestamp (it fails otherwise; guard or fix) | Few text messages |
| N-grams | Any text message | Few or short messages: bigrams/trigrams are mostly single occurrences |
| TF-IDF | At least two documents so IDF can vary | Very few documents: almost all IDF values are equal; the stability diagnostic is not meaningful for tiny N |
| Repetition | At least two text messages | No repeats, or all messages identical |
| Participants | At least one user row | One participant: table is a single row |

## 18. Future Extensibility

- Each analysis is a self-contained module with a common contract: input = parsed dataset; output = named,
  anonymised tables plus run metadata with reconciliation checks. The application layer treats modules as
  entries in a list (name, run function, page/tab, privacy class), so adding one adds a tab or section
  without redesigning the app.
- A new module must first pass the same gate as existing ones: written design, tests including privacy
  leak tests, reconciliation checks, and approval.
- Candidate future modules (none proposed for now): multilingual (Marathi-aware) preprocessing once
  justified, in which case the stopword treatment and script note would update; near-duplicate similarity
  if implemented and validated; wider export-format support once real samples exist.
- Sentiment is **not** added: it is excluded for the current dataset by the accepted decision, and would
  only be reconsidered under the conditions in the sentiment design note.

## 19. Dashboard-to-Rubric Mapping

| Rubric component (marks) | How the dashboard contributes |
|---|---|
| Methodology & Implementation (15) | A reusable pipeline application built on validated modules, upload validation, privacy-by-design, deterministic runtime, tests including runtime leak tests, and justified design choices (page structure, session model, adapter options) |
| Analysis, Results & Interpretation (10) | Clear visuals with interpretation panels, limitations shown next to every result, repetition-aware reading of n-grams and TF-IDF, and explicit non-claims |
| Report (10) | Screenshots and the explainability table give ready material for the Implementation and Results sections, and the design decisions are documented |
| Presentation (5) | A live demonstration: upload, run, walk through four pages, and answer viva questions from the "What am I looking at?" panels |

## 20. Final Dashboard Design Decision

**Final page structure:** A. Overview, B. Conversation, C. NLP Insights (Unigrams / Bigrams / Trigrams /
TF-IDF tabs), D. Patterns. Persistent sidebar with upload and current-run summary. No fifth page; no sentiment.

**Runtime flow:** upload → validate → parse and quality checks → preprocessing → n-gram → TF-IDF →
Conversation Analytics (this order keeps both cross-checks active) → anonymised in-memory result set →
render. The pipeline runs unchanged modules against a per-run temporary directory (adapter A), and
the directory is deleted after the outputs are loaded, including on failure.

**Privacy approach:** raw uploads not retained; only pseudonymised, aggregate tables held in session
memory; `Participant_N` per run with no mapping kept; masked URLs and phone numbers; no raw text, names,
sender identifiers, links, `analysis_corpus.csv` or message-level TF-IDF displayed or downloadable;
runtime leak tests required; residual risks stated in the app.

**Visualization list:** row composition; daily activity timeline; repetition summary (with repeated templates);
n-gram bars with all-vs-unique; TF-IDF bars with variant toggle (prominent); metadata summary table,
participant counts table, script note, repetition-effect table (secondary); hour histogram, weekday table,
text-length summary (appendix, collapsed).

**Major design decisions:**
1. Four pages, tabs inside NLP Insights.
2. Current run only, in session memory, with user-initiated anonymised download.
3. Existing validated modules reused unchanged behind an adapter; development results used only as a test oracle.
4. Application-layer validation because the parser never fails on non-chat text and the analytics module fails on zero text messages or invalid dates.
5. Descriptive participant information only, in a secondary table with a caution.
6. Light, soft theme (final redesign), restrained palette, no animation.
7. Explainability panels on every section.

**Open decisions requiring approval:**
1. **Install Streamlit** (and any chart library). It is not installed, and there is no requirements file, so dependency pinning is needed.
2. **Adapter A (temporary directory, unchanged modules) or B (refactor to in-memory `compute_*`)**. Recommendation: A first.
3. **Zero-text handling:** guard in the application layer only, or harden `run_analytics` (a code change to a validated module, with new tests).
4. **Deployment target:** local demonstration (recommended; strongest privacy) or hosted (uploads go to a server).
5. **Term-display privacy filter:** hide terms/phrases occurring in only one message by default; exclude message-level TF-IDF from the UI.
6. **Demo mode:** none, a local-file demo, or a synthetic sample chat for public demonstrations (the real chat must not be published).
7. **Download bundle contents** (anonymised analytics tables and aggregate NLP tables after filtering).
8. **Upload size cap and large-chat handling** (values to be set after measurement, including whether to skip the leave-one-out diagnostic above a size).
9. **Minimum-data thresholds** and badge wording (section 17 values are proposals).
10. **Unrecognised media placeholders and non-English system text:** caveat only, or evidence-based parser extension later.
11. **Date-order handling:** confirmation banner only (recommended), or an explicit month/day vs day/month choice.
12. **Failed second upload behaviour:** keep the previous run visible with an error, or clear it.
13. **Whether to display the uploaded file name** or only a hash prefix.
14. **Charting library choice** (interactive library that installs with Streamlit, versus static matplotlib figures already installed).

**DASHBOARD DESIGN STATUS: APPROVED and IMPLEMENTED** (with the decisions recorded in `docs/project_plan.md`
and `docs/dashboard_implementation.md`).

When this note was written no dashboard code had been created; the implementation followed the approval.
