# Final verification record

Everything here was run on **2026-10-05 and 2026-10-06** (the light dashboard redesign of 2026-10-06 is covered in sections 1, 2 and 6) on the development machine (Windows 11, Python 3.12) with **fictional data only**, except the two
clearly marked private-data checks (counts only; nothing private is stored or printed). "NOT VERIFIED" marks what could not be checked.

## 1. Summary

| Check | Result |
|---|---|
| Full test suite (development environment, `requirements-dev.txt`, fresh-clone file set) | **304 tests, 304 passed, 0 failed, 0 skipped** |
| Copy of only the Git-tracked files in a clean virtual environment (runtime requirements + pytest, no scikit-learn) | 304 tests: 302 passed, 0 failed, 2 skipped (the two scikit-learn cross-checks, skipped by design when scikit-learn is absent) |
| Same suite plus the local-only private regression test | 308 tests, all passed |
| Generalisation: 10 fictional fixtures through the full pipeline | 10 / 10 OK (section 3) |
| Reproducible run: pipeline twice on the fictional sample | byte-identical, and identical to the committed `results/sample` (section 8) |
| Browser review (Microsoft Edge via Playwright, fictional chats, 1440 px and 1366 px) | 52 screenshots captured; the ones listed in section 6 were viewed |
| Privacy: rendered text of every page and NLP tab for the private chat (re-run after the redesign) | 0 phone numbers, sender names, system-row names, links or message texts (counts only) |
| Privacy: files Git would commit (`scripts/check_repo_privacy.py`) | 0 findings |
| Clean install from `requirements.txt` | OK (streamlit 1.65, pandas 3.0.6, numpy 2.5.3, plotly 7.1.0, pillow 12.3.0) |

## 2. Test suite

| File | Tests | Covers |
|---|---|---|
| `test_parser_and_tokenizer.py` | 63 | sender-less system rows, invisible marks, multi-line, placeholders, tokenizer, typed CSV, date order |
| `test_generalization_fixtures.py` | 35 | every fixture through the whole pipeline, participant counts, privacy, TF-IDF stability |
| `test_dashboard_core.py` | 39 | validation, temporary-run adapter, run manager, display filter, bundle |
| `test_dashboard_app.py` | 31 | Streamlit pages (headless), every kind of chat on every page, error states |
| `test_dashboard_theme.py` | 32 | theme image palette, readability, reset, invalid images, download isolation |
| `test_tfidf_analysis.py` | 22 | formula, sklearn cross-check, variants, determinism |
| `test_key_terms.py` | 22 | coverage definition, independent recomputation, privacy |
| `test_script_mix_analysis.py` | 24 | script classes, alternations, reconciliation |
| `test_conversation_analytics.py` | 19 | composition, activity, repetition, 28 reconciliation checks, privacy |
| `test_ngram_analysis.py` | 17 | n-gram generation, counts, masking |
| `test_private_sample_regression.py` | 4 | local-only, git-ignored; aggregate expectations for the private chat (skipped without `data/chat.txt`) |

Sample-data tests use the committed fictional chats (`tests/helpers.py` builds the pipeline output once per session). Only the local-only
file depends on private data. Every bug of `final_audit_fixes.md` has a named regression test.

## 3. Generalisation matrix (fictional fixtures)

| Fixture | Kind | Rows | Text msgs | Participants | Warnings |
|---|---|---|---|---|---|
| `one_to_one.txt` | one-to-one chat | 71 | 66 | 2 | 0 |
| `group_12.txt` | group with 12 participants, system events, marks before the bracket | 168 | 143 | 12 | 0 |
| `group_30.txt` | group with 30 senders (one phone-number sender) | 138 | 122 | 30 | 0 |
| `single_sender.txt` | one participant only | 33 | 30 | 1 | 2 (small chat, date order) |
| `zero_text.txt` | media, deleted and system rows only | 5 | 0 | 2 | 3 |
| `parser_system_events.txt` | all sender-less system line shapes | 12 | 2 | 2 | 2 |
| `parser_unicode.txt` | invisible marks, Devanagari, curly quotes, emoji, year rollover | 13 | 11 | 3 | 1 |
| `media_deleted.txt` | Android and iOS placeholders, deleted wording, edited marker | 23 | 5 | 2 | 2 |
| `numeric_terms.txt` | `007`, `12345`, `2026`, `123ABC`, `ABC123`, `none/null/nan/na` | 11 | 10 | 2 | 2 |
| `privacy_cases.txt` | all phone formats, invite links, e-mail, web addresses, repeated names | 19 | 18 | 2 | 2 |

Also tested inline: 1, 2 and 5 text messages; all-identical, stopword-only and emoji-only chats; an all-numeric vocabulary; Day/Month dates;
Android-style and invalid files; CRLF line endings; 420 text messages (sampled stability diagnostic).
The dashboard pipeline, the anonymised download (22 files each) and all four dashboard pages work for every fixture
(`tests/test_dashboard_app.py::test_all_pages_render_for_every_kind_of_chat_without_names_or_links`).
**NOT VERIFIED:** real group or iOS exports, and chats above 3,000 text messages.

## 4. Analytical validity

| Analysis | Input | Transformation | Output | Interpretation | Limitation | Checked by |
|---|---|---|---|---|---|---|
| N-grams | Text messages (user rows that are not media/deleted) | masked, lower-cased, punctuation-stripped tokens; n-grams per message only | counts over all messages and over unique texts, document frequency, repetition ratio | how often a word/phrase occurs; the ratio shows repetition inflation | English-only stopwords; whitespace tokens | hand-computed unit tests, `count_all >= count_unique`, no cross-message n-grams |
| TF-IDF | one document = one message | `tf * (ln((1+N)/(1+df)) + 1)`, L2 per message; primary and unique variants | per-term total, mean, top-3 count | distinctive **within this chat** | unstable for small N; many equal IDFs; descriptive only | max abs difference to scikit-learn below 1e-12, L2 norms = 1, hand-computed cases, determinism |
| Stability diagnostic | the same documents | leave-one-out top-10 overlap (all documents up to 200, else 60 evenly spaced) | mean / minimum overlap, mode | how much the ranking depends on single messages | sampled above 200 documents | mode and determinism tests; scores unchanged by the mode |
| Script Mix | tokens of text messages | Unicode letter names → Latin / Devanagari / other; message class and alternations | counts per class, alternation statistics | writing systems used; **not language** | other Indian scripts fall into "other" | unit tests, agreement with the n-gram script diagnostics |
| Key Terms | the TF-IDF vocabulary | distinct messages containing each term | coverage, total occurrences, ratio | spread across messages vs raw frequency | English-only stopwords; internal table is display-filtered | independent recomputation inside the module and in tests |
| Conversation analytics | all parsed rows | counts with explicit denominators; zero-filled calendar | composition, daily activity, hour/weekday tables, length summary, repetition | descriptive structure of one chat | timestamps as recorded; no per-participant comparison | 28 reconciliation checks that must pass before anything is written |
| Repetition | masked text of text messages | identical-text groups (exact and masked-template) | unique texts, repeats, `Template Tn` groups | how much of the text is repeated | no fuzzy similarity | reconciliation: unique + repeats = text messages; group sizes reproduce the repeat count |
| Media / deleted / system | placeholder patterns and system lines | whole-message or bracketed placeholder rules; four generic system categories | counts | what is not text | placeholders in other languages count as text | `test_parser_and_tokenizer.py` |

All of these are **descriptive**. Nothing predictive is computed.

## 5. Privacy validation

* **Tokenisation-level masking** (`ngram_analysis`): international and local phone formats, WhatsApp invite links with or without `https://`, e-mail and web addresses;
  dates, prices and ordinary numbers are not masked (`test_privacy_cases_are_masked_at_tokenisation_not_only_hidden_at_display`,
  `test_dates_prices_and_ordinary_numbers_are_not_masked_as_phones`).
* **Display and download filter** (`display_privacy`): single-message terms hidden by default; terms that look like links, addresses, WhatsApp domains or contain 7+ digits dropped even when
  "show single-message terms" is on. The anonymised zip contains no sender name, phone number, link or message text for any fixture
  (`test_privacy_cases_do_not_reach_the_download_or_display_tables`, `test_bundle_contains_no_sender_names_in_any_fixture`).
* **Documented limitation:** a name used in several messages is still shown (`test_names_in_several_messages_are_not_hidden_documented_limitation`).
  Privacy filtering is a precautionary display/download layer and is not a complete PII detector.
* **Private-chat check (counts only):** the private development chat was uploaded through the browser UI and the rendered text of all four pages and all six NLP tabs was scanned for its
  phone numbers, number groups, sender names, system-row names, links and message texts: **0 matches** in every view.
* **Repository check:** `scripts/check_repo_privacy.py` scanned the files Git would commit (derived from `.gitignore`): **0 findings**.

## 6. Dashboard and theme validation (light design, Edge)

`scripts/browser_smoke_test.py` drives the app with fictional chats at a chosen width and saves 26 screenshots per run; it waits until charts have finished loading and checks that no fictional name, number or
link appears in the rendered text (the one-line example in the empty state uses the fictional names on purpose). It ran at **1440 px and 1366 px**; both runs passed the text check.

Screenshots **viewed** (not just captured):
* **1440 px:** empty state; one-to-one Overview, Conversation, Patterns, and the Unigrams, **Bigrams** and TF-IDF tabs; the 30-participant Overview with the green and the **dark-image** themes.
* **1366 px:** group-12 Overview; one-to-one Patterns, Unigrams and Key Terms tabs; the **empty-file error**; the failed second upload (which also shows the invalid-theme-image message); the 30-participant Overview with the **grey-image** theme; the zero-text Overview.

Not individually viewed: the Trigrams and Script Mix tabs and the blue, purple and light-image theme screenshots of the light design (they use the same components; the contrast of every theme is also tested numerically),
the invalid-file error screenshot, and the single-sender and group-30 Conversation pages.

Specific items checked: no clipped chart labels or titles; no horizontal overflow at 1366 px; navigation icons are CSS-drawn line icons (four different icons, no emoji or font glyphs); badge dots and ticks render correctly;
the Patterns chart shows at most the 10 most repeated templates with a note; the dark, grey and light images all fall back to the default palette with a pale header strip and readable text; toggles, radio buttons and sliders are visible
against the light page. Earlier findings that were fixed and re-checked: clipped axis labels (`automargin`), garbled badge symbols, theme variables not applying (selector strength), the Apply/Reset click race (callbacks).
Contrast is tested numerically (`tests/test_dashboard_theme.py`, ten colours including very dark, very light and grey): accents at least 4.5:1 on the cards and on the page, primary text above 12:1, muted text at least 4.5:1,
white text on the primary button at least 4.5:1, and a header strip that is always pale (mean brightness of at least 0.85).

## 7. TF-IDF scale (synthetic chats, 3,000-word random vocabulary, nine senders)

| Text messages | Before the fix | After the fix |
|---|---|---|
| 500 | 40.5 s total (TF-IDF 38.9 s) | 11.1 s (TF-IDF 9.7 s) |
| 1,000 | did not finish within 6 minutes (stopped) | 19.0 s (TF-IDF 15.9 s) |
| 2,000 | not measured | 36.8 s (TF-IDF 31.9 s) |

Real chats have smaller vocabularies and are faster; other machines were not measured. The configurable default limit stays at 1,000 text messages.

## 8. Reproducible clean run (fictional `data/sample_chat.txt`)

| Step | Seconds |
|---|---|
| parse and preprocess | 0.24 |
| n-grams | 0.09 |
| TF-IDF | 2.77 |
| Script Mix | 0.07 |
| Key Terms | 0.10 |
| conversation analytics | 0.56 |

26 output files, 0 parsing failures, 3.8 s in total. Two independent runs in fresh temporary folders are **byte-identical** and identical to the committed `results/sample`.
Failure behaviour (`RunManager`): an invalid file, an empty file, an Android-style file and a Day/Month file are each rejected with their own error code and leave no run;
after a valid upload, a failed second upload keeps the previous run, and a second valid upload replaces it.

## 9. Not verified

Real iOS exports; real Android exports (unsupported by design); chats above 3,000 text messages; browsers other than Edge; screen sizes other than 1440 px for the screenshots
(the layout uses Streamlit columns that collapse on narrower screens, which was not inspected); the optional `playwright` script on other machines.
