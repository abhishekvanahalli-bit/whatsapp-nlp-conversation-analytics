# Project Plan — WhatsApp NLP & Conversation Analytics Dashboard

> **Status note (2026-10-05).** This note was written during development about the private development chat (`data/chat.txt`, not in the repository) and describes the validated results at that time. The current behaviour of the pipeline is described in `supported_formats.md`, `final_audit_fixes.md` and `final_verification.md`; where they differ, those pages win.

> Planning document. **Current status (final audit, 2026-10-01): feature development is frozen for the first
> MSc presentation; see `docs/project_freeze.md` and section 9.** Earlier text in this document records the
> plan and milestone history.
> Nothing here changes source code, `data/chat.txt`, or `results/processed_chat.csv`.
> **Governing structure:** the official university rubric (50 marks) and official report structure,
> both recorded in section 18. Status labels used throughout: **Implemented** (exists and tested),
> **Planned** (intended, not started), **Conditional** (only if a stated feasibility check passes).

---

## 1. Project Title

**WhatsApp NLP & Conversation Analytics Dashboard**
A reproducible, privacy-aware pipeline for analysing mixed-language (English + Marathi) WhatsApp chats.

## 2. Problem Statement

WhatsApp exports are semi-structured text: multi-line messages, system notices, media placeholders,
deletion tombstones, forwarded markers, locale-dependent timestamps, and mixed scripts. Common
tutorial-level analysers apply a single regex, assume clean English text, and report raw counts
(word clouds, top words, message totals) without validating parsing, questioning whether counts
reflect real language use or repetition, or protecting participant identity.

The problem is to turn a raw export into **trustworthy, explainable, privacy-preserving conversation
analytics**, and to be explicit about what a given chat can and cannot support statistically. This
matters most for small, multilingual, announcement-style chats, where naive methods produce
confident-looking but misleading results.

## 3. Project Aim

To design, implement, and critically evaluate an NLP pipeline and dashboard that parses WhatsApp chat
exports, extracts descriptive linguistic and temporal patterns, and reports them together with
explicit validation and limitations — with particular attention to mixed-language text, repetition,
and participant privacy.

## 4. Specific Objectives

1. **Robust ingestion.** Parse raw exports into a structured table, handling multi-line messages,
   system/header lines, media/deleted/forwarded markers, and Unicode, with automated data-quality checks.
2. **Transparent preprocessing.** Build separate, documented preprocessing layers (raw → cleaned →
   analysis view) that preserve the raw data and justify every normalisation, masking, and filtering step.
3. **Descriptive lexical analysis.** Quantify vocabulary and phrase usage (unigram/bigram/trigram now;
   TF-IDF later) while distinguishing genuine lexical popularity from repetition of the same message.
4. **Mixed-language handling.** Measure how English-only preprocessing affects Devanagari text and
   design, justify, and test a multilingual approach (script-aware tokenisation and stopword handling)
   rather than assuming one.
5. **Interpretable message-level analysis.** Apply explainable methods (temporal activity, sender
   contribution, message-type composition, and — only where defensible — topic exploration) with each
   output tied to a stated question. Sentiment/tone is excluded for the current dataset (see
   `docs/sentiment_design.md`).
6. **Communication and reproducibility.** Deliver an interactive dashboard, tests, and a report that
   present results with uncertainty and limitations, using anonymised outputs only.

## 5. Research / Analysis Questions

- RQ1. How much of the chat is conversational text versus system, media, and deleted content?
- RQ2. When do participants communicate (date, weekday, hour), and is activity bursty?
- RQ3. How is contribution distributed across senders, and what does that imply about the chat's nature
  (discussion vs. broadcast)?
- RQ4. Which words and phrases dominate, and how much of that dominance is due to repeated
  messages rather than lexical variety? (Partly answered in Day 2 M1: repeated invite text produces
  the top English bigrams/trigrams, ratio 5.0.)
- RQ5. How does English-only stopword handling affect mixed English/Marathi text? (Baseline measured:
  a share of Latin tokens removed, none of the Devanagari tokens.)
- RQ6. Which messages/terms are distinctive relative to the rest of the chat (TF-IDF, later)?
- RQ7. Can sentiment or tone be characterised for this chat, and is any such measure valid for
  announcement-style, bilingual text? (Addressed by the feasibility assessment in
  `docs/sentiment_design.md`: sentiment/tone is **not implemented** for the current dataset — a
  methodological scope decision, not a claim that sentiment analysis is impossible in general.)

## 6. Scope

- Single-chat, single-export analysis of the supplied WhatsApp file.
- Parsing, cleaning, quality checks, and anonymised analysis outputs.
- Descriptive NLP: tokenisation, n-grams, TF-IDF, keyword/phrase analysis (Key Terms), repetition analysis,
  Script Mix (script composition; not language identification).
- Temporal and sender activity analytics.
- Multilingual (English + Marathi/Devanagari) preprocessing design, with justification.
- Sentiment/tone: feasibility assessment only (`docs/sentiment_design.md`); **not implemented** for the
  current dataset.
- Interactive dashboard over anonymised outputs; automated tests; written report.

## 7. Out of Scope

- Claims that findings generalise to other chats, groups, or populations.
- Supervised sentiment/topic classifiers or accuracy figures without labelled ground truth.
  (Manual labelling of a tiny subset may be used only as a sanity check, not a benchmark.)
- Sentiment/tone analysis of the current chat dataset (excluded by the dataset-suitability decision in
  `docs/sentiment_design.md`; may be revisited as future work — see section 19).
- Large pretrained-model pipelines added only for impressiveness.
- Identifying, profiling, or de-anonymising individuals.
- Real-time WhatsApp integration, multi-user uploads, or cloud deployment.
- Analysis of media content (images/videos are only counted as placeholders).
- Modifying or committing the raw chat.

## 8. Dataset Description

| Item | Value |
|---|---|
| Source | One small private WhatsApp group-chat export used during development (not published; real chats are never committed) |
| Period | A few weeks; a handful of busy dates with several empty calendar dates |
| Parsed rows | Header, system and user rows (counts omitted; the pipeline reports them for any chat) |
| User rows | Mostly media placeholders and deleted tombstones, with a small share of real text messages (a few of them repeated after link masking) |
| Senders | A few distinct senders; one contributed most rows |
| Languages | English and Marathi (Devanagari), often mixed within a message; some romanised mixing |
| Content type | Announcement/invitation-style group messages: invite links, requests and notices |
| Derived files | `results/processed_chat.csv` (Day 1, 22 columns, internal, contains raw text); `results/analysis_corpus.csv` and `results/ngram_*.csv`; `results/tfidf_*`; `results/analytics_*`; `results/script_mix_*` and `results/script_mixing_stats.csv`; `results/key_terms*` (see section 13 for which files are internal only) |

## 9. Current Project Status

**Completed (Day 1 + Day 2 M1):**
- Robust parsing incl. multi-line messages, system messages, header handling
- Media / deleted / forwarded detection; Unicode-aware processing; datetime feature extraction
- Data-quality checks; baseline tokenisation and English stopword handling
- Separate analysis-preprocessing layer (URL → `<URL>`, phone → `<PHONE>`, sender anonymisation)
- Unigram/bigram/trigram analysis with both repetition-inclusive and unique-text counts
- Script diagnostics quantifying the mixed-language effect
- 17 automated tests passing; raw data and `processed_chat.csv` verified unchanged

**Open decisions / known issues:**
- **Forwarded marker (decision made, change Implemented):** `is_forwarded` metadata is preserved; the
  literal `[Forwarded]` marker is removed from the text used for NLP analysis; the original raw
  chat is never modified. The Day 2 M1 outputs (`analysis_corpus.csv`, `ngram_*.csv`) were
  originally generated before this decision and contained the token `forwarded`; they have since been
  regenerated without it. The decision and its rationale (a WhatsApp-generated marker is
  metadata, not authored language) will be documented in the report.
- Marathi tokenisation/stopwords deliberately not handled yet (to be designed and justified).
- Privacy/anonymisation is an ongoing requirement and must be verified before submission (section 13).

**Current status (final audit, 2026-10-01; scope frozen):**
- **IMPLEMENTED:** WhatsApp parsing and preprocessing; n-gram analysis (unigram, bigram, trigram); TF-IDF;
  Conversation Analytics (incl. repetition analysis and descriptive sender/activity analytics); Script Mix
  (script composition, **not** language identification); Key Terms; privacy/anonymisation; Streamlit dashboard
  (Overview, Conversation, NLP Insights, Patterns); automated testing (**304 tests passing**).
- **NOT IMPLEMENTED:** production sentiment analysis; production emotion classification; named-entity
  recognition; language identification.
- **FUTURE WORK (research only):** multilingual / code-mixed sentiment; multilingual / code-mixed emotion; a
  labelled evaluation dataset (`docs/emotion_evaluation_protocol.md`); model calibration; broader language
  coverage; (Script Mix / Key Terms dashboard integration now done).
- **Not yet started:** report and presentation.

## 10. Methodology Roadmap

Guiding rules: raw data is never edited; every technique has a stated purpose, validation, an
explainability note, and a limitation; features are added only if they answer a question in section 5.

| Stage | Description | Status |
|---|---|---|
| A. Ingestion & parsing | Regex parser, multi-line joining, system/header/media/deleted/forwarded flags | Done |
| B. Quality assurance | Row-count reconciliation, null/format checks, unparsed-line checks | Done |
| C. Baseline preprocessing | Clean text, tokenise, English stopwords | Done |
| D. Analysis preprocessing | URL/phone masking, anonymised senders, conversational-row filter | Done |
| E. N-gram analysis | n=1,2,3; all vs unique counts | Done |
| F. Descriptive analytics | Volume by day/hour/weekday, sender share, message-type composition, message-length stats (implemented per the approved scope in `docs/conversation_analytics_design.md`; sender information descriptive only) | Completed |
| G. Multilingual preprocessing | Script detection per token; evidence-based Marathi handling (candidate sources: published resources, corpus-derived frequency evidence — chosen and justified before use); Devanagari-safe tokenisation; compare against baseline | Script diagnostics and Script Mix implemented; Marathi-aware preprocessing not implemented (future work) |
| H. TF-IDF | Document = message (and/or grouped by day); interpret distinctiveness; handle tiny-corpus instability | Completed |
| I. Repetition analysis | Exact and near-duplicate detection; effect of repetition on all statistics | Completed for exact and masked-template repetition (within Conversation Analytics); fuzzy near-duplicate detection not implemented |
| J. Sentiment / tone | Feasibility assessment completed (`docs/sentiment_design.md`); not implemented because the current dataset does not support a defensible result | Not implemented — excluded for current dataset |
| K. Topic/keyword exploration | Key Terms implemented as a limited, descriptive view over existing tables (`docs/language_and_keyword_design.md`); topic modelling not implemented | Key Terms implemented; topic modelling not implemented |
| L. Dashboard | Streamlit + Plotly application that runs the validated pipeline on an uploaded compatible export (`docs/dashboard_design.md`, `docs/dashboard_implementation.md`) | Implemented (four pages); Script Mix and Key Terms are integrated into the NLP Insights page (final dashboard polish complete) |
| M. Evaluation & report | Tests, sanity checks, sensitivity analysis, limitations, viva material | Tests and sanity checks done (304 passing; results regenerate byte-identically); report and viva material planned |
| N. Script Mix | Deterministic script composition of each message (Latin / Devanagari / mixed); not language identification (`src/script_mix_analysis.py`) | Implemented (limited, descriptive) |
| O. Sentiment / emotion research | Model and dataset research, qualitative feasibility test, labelled-evaluation protocol (`docs/emotion_sentiment_design.md`, `docs/emotion_evaluation_protocol.md`) | Research only; **not implemented** (future work) |

## 11. Objective → Method → Expected Result

| # | Objective | Method | Expected result |
|---|---|---|---|
| 1 | Robust ingestion | Regex parser, multi-line joining, flags, reconciliation checks | Structured table; zero unexplained unparsed lines; documented counts (header + system + user = parsed rows) |
| 2 | Transparent preprocessing | Layered files (raw → processed → analysis corpus), masking, tests asserting raw data unchanged | Reproducible pipeline; anonymised outputs; raw data verifiably untouched |
| 3 | Descriptive lexical analysis | N-grams, TF-IDF, all-vs-unique counts | Ranked terms/phrases labelled descriptive; quantified repetition inflation |
| 4 | Mixed-language handling | Script diagnostics, evidence-based Marathi handling, before/after comparison | Measured change in top terms; justified choices; documented residual errors |
| 5 | Interpretable message-level analysis | Time/sender analytics; optional keyword/topic exploration (sentiment excluded for the current dataset, see `docs/sentiment_design.md`) | Charts and tables answering RQ2, RQ3, RQ6, each with a limitation note; RQ7 answered by the documented sentiment feasibility assessment |
| 6 | Communication & reproducibility | Dashboard, tests, report | Working dashboard on anonymised data; passing test suite; rubric-aligned report |

## 12. What Makes This Project Different from the CampusX Baseline

CampusX provides a descriptive WhatsApp chat analytics baseline. This project is independently
engineered and extends that baseline with stronger parsing and validation, multilingual-aware
preprocessing, n-gram analysis, TF-IDF, a documented sentiment feasibility assessment (sentiment not
implemented for the current dataset), evaluation/validation where applicable, temporal and metadata analysis, privacy-aware processing,
and an interactive dashboard.

CampusX is used as reference and inspiration for descriptive analytics only; this project's code is
written independently. The extensions below are labelled by status:

| Extension over the descriptive baseline | Status |
|---|---|
| Parsing with multi-line, system, header, media/deleted/forwarded handling and data-quality checks | Implemented |
| Automated tests (304 passing) including raw/processed-data-unchanged assertions | Implemented |
| Privacy-aware analysis outputs (URL → `<URL>`, phone → `<PHONE>`, anonymised senders) | Implemented (verification ongoing; see section 13) |
| N-gram analysis (n=1–3) with repetition-inclusive and unique-text counts | Implemented |
| Measurement of English-only stopword effect on mixed English/Marathi text | Implemented (baseline only) |
| Removal of `[Forwarded]` marker from NLP text, `is_forwarded` kept | Implemented |
| Temporal and metadata analysis (date/weekday/hour, sender, message type) | Implemented (approved scope; sender information descriptive only) |
| Multilingual-aware preprocessing, justified before use | Script diagnostics and Script Mix implemented; Marathi-aware preprocessing not implemented |
| TF-IDF | Implemented |
| Interactive dashboard | Implemented (Streamlit + Plotly) |
| Sentiment approach, justified for the languages present | Not implemented — excluded for current dataset (feasibility assessment completed; see `docs/sentiment_design.md`) |
| Evaluation/validation | Planned where applicable (sanity checks, sensitivity analysis; see section 15) |
| Key Terms (keyword view over existing tables) | Implemented (limited); topic modelling not implemented |
| Script Mix (script composition) | Implemented (limited; not language identification) |

## 13. Data Privacy Considerations

- **Warning:** raw chat data (`data/chat.txt`) and unmasked processed outputs
  (`results/processed_chat.csv`) contain real phone numbers/names and must NOT be published or
  placed into the final public dashboard, report, or GitHub repository. They stay local and are never
  displayed in the dashboard. Where a public artefact is needed, use only anonymised outputs or a
  synthetic sample.
- **Privacy/anonymization is an ongoing requirement and must be verified before submission.**
  Privacy is not claimed to be fully solved.
- Analysis outputs use `<PHONE>`, `<URL>`, and `Sender_N` pseudonyms; a test asserts these strings do
  not leak into generated CSVs.
- Masking limits: the phone regex only catches `+CC …` formats; personal names inside message text
  (e.g. player or team lists) and shared group-invite links are not fully handled. Additional
  name-masking is a planned check before any output is published.
- Pseudonymised data is still potentially re-identifiable (small group, unique content); the dashboard
  is for local/academic use only.
- Group members did not consent to analysis: use only data you are entitled to use, and consider
  seeking ethics/module-leader confirmation.
- **Internal-only files (contain chat-derived content; never for publication or the public dashboard):**
  `data/chat.txt`, `results/processed_chat.csv` (raw text and numbers), `results/analysis_corpus.csv` (masked
  message text), `results/tfidf_terms_by_message.csv` (per-message terms), `results/key_terms.csv` and
  `results/tfidf_top_terms.csv` (term lists that can include personal names), and the Day 1 notebook
  `notebooks/01_data_parsing_and_preprocessing.ipynb` (its saved outputs show real phone numbers and message
  content). The dashboard display and download paths apply the privacy filter and were verified to contain none
  of these identifiers (final audit).
- Report should describe these safeguards and their limits.

## 14. Known Dataset Limitations

- **Tiny sample:** a small number of text messages (fewer unique texts); most n-gram counts are very small. Rankings are unstable.
- **Single dominant sender** (almost all user rows): no meaningful sender comparison; conversation
  dynamics (replies, turn-taking) essentially absent.
- **Announcement-style, repetitive content:** phrase statistics reflect one organiser's templates.
- **Short period** (about 2.5 weeks), one topic domain: no long-term trends.
- **Mixed language:** English + Marathi (+ occasional Hinglish-style mixing); whitespace tokenisation
  splits Marathi inflections into separate word types.
- **Media not analysable** (placeholder rows) and deleted messages have no text.
- **Locale-specific export format** (two-digit-year `M/D/YY`, 12-hour time): the parser is tied to it.
- **No ground-truth labels** for sentiment, topic, or language.
- Conclusions are descriptive of this chat only and must not be presented as generalisable.

## 15. Planned Evaluation Strategy

No supervised accuracy claims. Evaluation is by verification, sanity checks, and sensitivity analysis.

1. **Parsing correctness:** row-count reconciliation (parsed rows vs. logical lines), spot-check a
   sample against `chat.txt`, unit tests on tricky lines.
2. **Pipeline integrity:** tests that raw and processed files are unchanged; no phone numbers or URLs
   in outputs; count invariants (e.g. `count_all ≥ count_unique`).
3. **Function-level tests:** every module has tests (304 tests in the final suite).
4. **Sensitivity analysis:** re-run results with/without stopwords, with/without deduplication, with
   different masking — report which conclusions change.
5. **Multilingual preprocessing:** evaluate by before/after comparison of top terms and by manual
   inspection of a sample; report residual errors. Not by accuracy.
6. **TF-IDF:** check stability under small perturbations (e.g. drop one message) and interpret cautiously.
7. **Sentiment:** not implemented for the current dataset (see `docs/sentiment_design.md`), so no
   sentiment evaluation is performed. If revisited in future with a larger, labelled,
   language-appropriate dataset and validated resources, no accuracy would be claimed without valid
   labelled ground truth.
8. **Dashboard:** manual checks that figures match the saved CSVs; no raw identifiers shown.
9. **Reproducibility:** one command regenerates all outputs from raw data.

## 16. Planned Results and Visualisations

Each visual is tied to a question and carries a limitation caption.

| Result | Visual | Question |
|---|---|---|
| Composition of rows (user/system/header; text/media/deleted) | Stacked bar / table | RQ1 |
| Messages by date, weekday, hour | Timeline, bar chart, day×hour heatmap | RQ2 |
| Sender contribution (anonymised) | Bar chart with dominance note | RQ3 |
| Top unigrams/bigrams/trigrams, all vs unique | Paired bar charts | RQ4 |
| Effect of English stopwords on Latin vs Devanagari tokens | Before/after bars | RQ5 |
| Distinctive terms per message/day | TF-IDF table / bar chart | RQ6 |
| Message length distribution, repetition ratio | Histogram / table | RQ4 |
| Tone/sentiment | Not produced — excluded for current dataset (`docs/sentiment_design.md`) | RQ7 |
| Data-quality summary | Table | RQ1 |

Avoid word clouds as primary evidence (poor at quantitative comparison); if used, only as a labelled
supplement.

Status note (final audit): the descriptive tables for the row-composition, timing, sender-count and
repetition items above are generated (Conversation Analytics), and the dashboard visualises composition, daily
activity, repetition, n-grams and TF-IDF (`docs/dashboard_implementation.md`). Script Mix / Key Terms dashboard
integration was completed in the final dashboard polish.

## 17. Final Dashboard Plan

Superseded by the approved and implemented design (`docs/dashboard_design.md`, `docs/dashboard_implementation.md`):
- **Tech:** Streamlit + Plotly. The app runs the validated pipeline on an uploaded compatible `.txt` export in a
  per-upload temporary directory (deleted afterwards) and renders anonymised results; it does not read `results/`.
- **Pages:** Overview, Conversation, NLP Insights (unigrams, bigrams, trigrams, TF-IDF), Patterns. Participants are a
  descriptive section of the Conversation page, not a page.
- **Design rules:** descriptive-results captions, limitation text beside each result, no phone numbers, names,
  links or raw message text, single current run kept in session memory, synthetic demo mode.
- **Done:** Script Mix and Key Terms dashboard integration (final dashboard polish). No sentiment or
  emotion page.

## 18. Official Rubric and Report Structure

### 18.1 Official university rubric (50 marks)

| Component | Marks | How this plan addresses it |
|---|---|---|
| Problem Definition & Objectives | 5 | Sections 2–7 |
| Data Collection & Preprocessing | 5 | Sections 8, 10 (stages A–D, G), 13, 14 |
| Methodology & Implementation | 15 | Sections 10–12, 15. Criterion emphasises a clear, innovative, well-implemented methodology with justification of techniques/models, so every technique needs a stated purpose and justification |
| Analysis, Results & Interpretation | 10 | Section 16. Criterion requires clear results, visualizations/metrics, and interpretation |
| Report | 10 | 18.2 below |
| Presentation | 5 | Dashboard (section 17) and viva/presentation material |
| **Total** | **50** | |

### 18.2 Official report structure

1. Cover Page
2. Abstract
3. Introduction
4. Literature Review (if any)
5. Methodology
6. Implementation
7. Results & Analysis
8. Conclusion & Future Work
9. References

### 18.3 Content mapping (planning aid, within the official structure)

| Official section | Planned content |
|---|---|
| Introduction | Problem statement, aim, objectives, research questions, scope (sections 2–7) |
| Literature Review | WhatsApp/chat analytics, n-grams/TF-IDF, code-mixed and low-resource NLP, privacy/ethics |
| Methodology | Dataset, preprocessing layers, technique justification, privacy handling, evaluation strategy (sections 8, 10, 13–15) |
| Implementation | Architecture, modules, tests, dashboard |
| Results & Analysis | Results and visualisations with interpretation and limitations (sections 14, 16) |
| Conclusion & Future Work | Findings (descriptive, sample-specific), limitations, future work |
| References / appendices | References; any appendix material placed under the official headings |

## 19. Milestone Checklist

**Day 1 — Foundation**
- [x] Parser, multi-line, system/header, media/deleted/forwarded flags, datetime, Unicode
- [x] Data-quality checks, tokenisation, basic stopwords, `processed_chat.csv`

**Day 2 — Lexical analysis**
- [x] M1: analysis-preprocessing layer, URL/phone masking, n-grams (n=1–3), all-vs-unique, 17 tests
- [x] Decide handling of `[Forwarded]` marker token (keep `is_forwarded`, remove marker from NLP text; implementation: Implemented)
- [x] This planning document
- [x] Official rubric and report structure recorded (section 18)
- [x] Implement forwarded-marker removal and regenerate Day 2 M1 outputs
  - Completion evidence: 17 tests passing; raw chat (`data/chat.txt`) unchanged; `processed_chat.csv`
    unchanged; `is_forwarded` metadata preserved; affected n-gram outputs regenerated; repeated
    messages preserved.
- [ ] Verify privacy/anonymisation before any submission

**Next (order to be confirmed)**
- [x] Descriptive analytics (time, sender, composition) — Conversation Analytics
  - Completion evidence:
    - Conversation Analytics implemented in `src/conversation_analytics.py`.
    - Approved scope implemented; excluded analyses (period grouping, length over time, per-sender
      comparisons, reply network) not built.
    - 58/58 total tests passing (19 new tests).
    - Privacy leak tests passed (phone numbers, system-message names, invite/access URLs, raw
      sender identifiers, raw message text); `Participant_N` pseudonyms independent of `Sender_N`.
    - 28 reconciliation checks passed.
    - 10 approved analytics result files generated (`analytics_*.csv`, `analytics_run_metadata.json`).
    - Raw data and existing NLP / TF-IDF / n-gram outputs unchanged.
    - Export time zone remains unverified.
    - Dashboard is NOT started yet.
  - Results review — **COMPLETED**, decision: **READY FOR DASHBOARD DESIGN**
    (`conversation_analytics_results_review.md` (kept locally, not in the public repository, because it reports aggregate results of the private chat)):
    - Conversation Analytics implementation completed; results reviewed and interpreted.
    - 58/58 tests passed; 28 reconciliation checks passed; no discrepancies found.
    - Privacy review of all 10 analytics result files found no leaks.
    - Cross-module interpretation against the n-gram and TF-IDF outputs completed.
    - Four dashboard candidate visuals identified (row composition, daily activity timeline,
      repetition summary, metadata summary table).
    - The next milestone is Dashboard Design. This does NOT mean the dashboard has been built:
      the dashboard itself is not yet implemented.
- [ ] Multilingual preprocessing design + justification + before/after — not implemented (future work; script diagnostics and Script Mix exist)
- [x] TF-IDF with stability check
  - Completion evidence:
    - Implemented in `src/tfidf_analysis.py` (numpy/pandas; scikit-learn used only as a reference).
    - Primary corpus: N = all actual text messages; repeated messages preserved.
    - Sensitivity corpus: N = unique texts only.
    - Empty documents retained in N (contribute no TF or DF).
    - `<URL>` / `<PHONE>` excluded from the ranked vocabulary.
    - No Marathi stopword list added.
    - 39 tests passing, 0 failing.
    - scikit-learn cross-check passed, with only floating-point differences (~1e-16).
    - Raw data and existing preprocessing / n-gram results unchanged.
    - Four result files generated: `tfidf_terms_by_message.csv`, `tfidf_top_terms.csv`,
      `tfidf_variant_comparison.csv`, `tfidf_run_metadata.json`.
    - Limitations documented (`docs/tfidf_design.md`).
    - TF-IDF rankings are descriptive for this small corpus and should not be treated as
      generalizable.
- [x] Repetition analysis (exact and masked-template) — Completed within Conversation Analytics;
  fuzzy near-duplicate detection not implemented
- [x] Sentiment feasibility assessment — Completed (`docs/sentiment_design.md`)
- [x] Sentiment implementation — Not implemented / excluded for current dataset
  (not a pending item). Reasons: only a few real text messages; strong sender imbalance (almost all from one
  sender); English and English/Marathi mixed text; no ground-truth sentiment labels; short,
  announcement-heavy messages; forwarded content needs separate treatment; evaluation would not be
  defensible without suitable labelled evaluation data and verified language-appropriate resources.
  This is a methodological scope decision, not a claim that sentiment analysis is impossible in general.
  Future work: sentiment could be revisited if a larger, labelled, language-appropriate dataset and
  validated resources become available.
- [x] Key Terms (keyword view; unique-message coverage) — implemented in `src/key_terms.py` with tests and results; topic modelling not implemented
- [x] Script Mix (script composition; **not** language identification) — implemented in `src/script_mix_analysis.py` with tests and results
- [x] Sentiment / emotion research — Phase 1 feasibility (`docs/emotion_sentiment_design.md`) and Phase 2 evaluation protocol (`docs/emotion_evaluation_protocol.md`) completed as **research only**; nothing implemented
- [x] Dashboard — **implemented** (Streamlit + Plotly; 304 tests pass); Script Mix and Key Terms are integrated into the NLP Insights page (final dashboard polish complete)
  - Approved decisions (`docs/dashboard_design.md`):
    - Technology: Streamlit with Plotly interactive charts, using the existing validated analysis modules
      as the backend (no refactor to in-memory architecture yet).
    - Runtime: upload → validate → per-upload temporary run directory → parse → preprocess → n-grams →
      TF-IDF → conversation analytics → privacy/display filtering → load anonymised results → render →
      delete the temporary directory (on success and on failure).
    - Only the current successful run is retained in session memory; a successful new upload replaces it;
      a failed new upload keeps the previous run visible; no server-side chat history; no process-wide
      result cache; raw uploads not retained; anonymised downloads may be offered.
    - Input: only the validated bracketed WhatsApp `.txt` export format; the app performs its own
      validation; other formats are not claimed as supported.
    - `src/conversation_analytics.py` is hardened so zero-text input returns a graceful limited result.
    - Dates: existing Month/Day/Year interpretation preserved and displayed with the parsed date range;
      timestamps are as recorded in the export and the time zone is unverified.
    - Privacy: no raw phone numbers, sender identifiers, personal names, raw invite/access URLs or
      unnecessary raw text; `Participant_N` generated independently per run with no mapping kept. By
      default terms occurring in only one message are hidden in the display layer only (a precaution
      against exposing low-frequency identifying terms; not complete PII detection).
    - Demo mode uses synthetic data only (never the real project chat).
    - Configurable upload-size and analysis thresholds; small chats show a limited-data warning instead
      of being rejected; thresholds are measured and documented, not guessed.
    - Media placeholders are recognised as listed in `supported_formats.md` (extended in the final audit).
    - Four pages only: Overview, Conversation, NLP Insights, Patterns (participants are not a page).
- [x] Extended tests — 304 tests passing
- [x] Single-command reproducibility script (`scripts/run_full_pipeline.py`, 2026-10-05; the line below is the earlier status) -  (each module has its own `python src/<module>.py`; the final audit verified that all 26 result files regenerate byte-identically from `data/chat.txt`)
- [ ] Report draft, viva notes, final review

## 20. Current Decision Gate

Milestone 2 (TF-IDF) has been completed after the project definition, objectives, scope, CampusX baseline comparison, and rubric mapping were reviewed and accepted.

Milestone 3 (Sentiment/Tone feasibility) has been completed and its decision accepted: sentiment/tone analysis will not be implemented on the current dataset (methodological scope decision; see `docs/sentiment_design.md`).

Milestone 4 (Conversation Analytics) has been completed and its design approved with three required changes (independent `Participant_N` pseudonyms, required privacy leak tests, approved scope kept unchanged): implemented in `src/conversation_analytics.py` (see `docs/conversation_analytics_design.md`). The dashboard has not been started.

Conversation Analytics results review has been completed with the decision READY FOR DASHBOARD DESIGN (see `conversation_analytics_results_review.md` (kept locally, not in the public repository, because it reports aggregate results of the private chat)). The next milestone is Dashboard Design; the dashboard itself has not been built.

Milestone 5 (Dashboard Design) has been reviewed and APPROVED with the decisions recorded in section 19; implementation has started and the dashboard is NOT yet completed.

Milestone 5 (Dashboard) was implemented after the design approval (`docs/dashboard_implementation.md`).

Milestone 5A: Script Mix and Key Terms were implemented as the final two NLP additions (limited, descriptive). Language identification and NER were not implemented.

Sentiment / emotion: Phase 1 (feasibility) and Phase 2 (evaluation protocol) are research documents only; **no sentiment or emotion feature is implemented**. Finding: there is no single verified model in the tested set that reliably covers English + Hindi + Marathi + Roman Hindi/Marathi + code-mixing + emotion. This is future work.

**Project freeze (2026-10-01):** feature development is frozen for the first MSc presentation (`docs/project_freeze.md`). Next: final dashboard design/polish, then report and presentation.
