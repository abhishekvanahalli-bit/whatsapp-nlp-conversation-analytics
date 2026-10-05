# Project freeze: final technical state

**Frozen on 2026-10-05 after the final A-Z audit and completion pass.** Evidence for every statement below is in
[`final_verification.md`](final_verification.md) (tests, generalisation matrix, clean install, reproducible run, browser review) and
[`final_audit_fixes.md`](final_audit_fixes.md) (what was found and fixed). The supported export format is defined in
[`supported_formats.md`](supported_formats.md).

## Scope (frozen)

Implemented: export parsing, preprocessing and data-quality checks; unigrams, bigrams, trigrams; TF-IDF (primary and unique-text
variants, stability diagnostic); conversation analytics (composition, activity, repetition, media/deleted/forwarded/link counts, system categories,
hour/weekday/length tables); Script Mix; Key Terms; privacy filtering and anonymised download; Streamlit dashboard with an optional theme image;
automated tests; a reproducible command-line pipeline; documentation.

**Intentionally not implemented:** sentiment analysis, emotion classification, named-entity recognition, language identification, reply networks,
predictive models. A research note on emotion/sentiment feasibility is kept as future work (`emotion_sentiment_design.md`); nothing from it is in
the code, the dashboard or the requirements.

## Module map

| Area | Where |
|---|---|
| Parsing, placeholders, tokenisation | `src/preprocessor.py` |
| Typed CSV reading (terms stay strings) | `src/csv_io.py` |
| N-grams and masking | `src/ngram_analysis.py` |
| TF-IDF | `src/tfidf_analysis.py` |
| Script Mix, Key Terms | `src/script_mix_analysis.py`, `src/key_terms.py` |
| Conversation analytics | `src/conversation_analytics.py` |
| Run pipeline for the dashboard / command line | `src/run_pipeline.py`, `src/pipeline_steps.py`, `scripts/run_full_pipeline.py` |
| Privacy filter, download | `src/display_privacy.py`, `src/results_bundle.py` |
| Dashboard | `app/` (`streamlit_app.py`, `views.py`, `ui.py`, `charts.py`, `theme.py`) |
| Fictional data | `tests/fixtures/`, `data/sample_chat.txt`, `src/demo_data.py`, `scripts/generate_synthetic_fixtures.py` |

## Test status

Final run (fresh-clone file set, `requirements-dev.txt` installed): **304 tests, 304 passed, 0 failed, 0 skipped**. Without scikit-learn two
cross-check tests are skipped by design (302 passed, 2 skipped). A local-only, git-ignored regression test for the private chat adds 4 passing tests
(`final_verification.md`).

## Known limitations (verified)

* **Format.** Only `[M/D/YY, H:MM:SS AM/PM] ...` exports are read. Android no-bracket, 24-hour, no-seconds, four-digit-year and Day/Month exports are
  not supported. iOS-style conventions were verified on fictional fixtures only; no real iOS export was available.
* **Dates.** When every month/day value is 12 or below, the date order cannot be confirmed (prominent warning). The time zone is unknown.
* **NLP.** English-only stopwords; whitespace tokenisation; Script Mix is script composition, not language identification; TF-IDF and Key Terms are
  unstable for small chats; the TF-IDF stability diagnostic is sampled above 200 documents.
* **Privacy.** Masking and the display filter are pattern based. They are not a complete PII detector; a name used in several messages is still shown.
* **Scale.** Default limit 1,000 text messages (configurable). Measured on the development machine with synthetic text: 500 messages 11 s, 1,000 messages
  19 s, 2,000 messages 37 s. Other machines and real vocabularies were not measured.
* **Dashboard.** Verified in Microsoft Edge (Playwright) and the Streamlit test harness only.

## Repository hygiene

Real chat exports and everything derived from them are excluded by `.gitignore` (`data/*` except the fictional sample, `local_private/`, `results/*`
except `results/sample`). `scripts/check_repo_privacy.py` scans the files Git would commit.

## Next phase

Report and presentation, written from this frozen state.
