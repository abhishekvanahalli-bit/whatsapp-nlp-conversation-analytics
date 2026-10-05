# Final audit: what was found and fixed

A master audit of the project (October 2026) checked whether the pipeline generalises beyond the single development chat. It ran
synthetic one-to-one chats, groups of 12 and 30 participants, a single sender, 0-120 text messages, parser variants and privacy probes.
This page records every verified problem, the fix, and the regression test that now guards it. "Backend change" says whether a
fix can alter calculated results.

## 1. Bugs found and fixed

| # | Problem (verified) | Fix | Regression test | Backend change? |
|---|---|---|---|---|
| 1 | A timestamped line **without a sender** (iOS encryption notice, "X added Y", "X left", "You were added", group-name change) became an `unparsed` row. The analytics reconciliation check `header+system+user == parsed rows` then failed and the **whole analysis stopped**. | `parse_chat` treats a sender-less timestamped line as a **system** row (`preprocessor.py`). A `Name: text` shape whose "name" reads like a system sentence is also a system row. Generic categories are kept (`conversation_analytics.system_category`). | `test_parser_and_tokenizer.py`: system-event tests; fixture `parser_system_events.txt` | Only for input that used to fail |
| 2 | An invisible mark (U+200E ...) before `[` made the row look like a **continuation line**: two messages were silently merged, with no warning. | Leading invisible marks are ignored when detecting a new row. | `test_invisible_marks_before_the_bracket_start_a_new_row`, fixture `parser_unicode.txt` | Only for input that was mis-parsed |
| 3 | iOS-style placeholders (`image omitted`, `sticker omitted`, `<attached: ...>`, `Missed voice call`, `You deleted this message`) were counted as **text** and polluted the vocabulary. | `BRACKETED_PATTERNS` (contained anywhere) and `BARE_PATTERNS` (whole message), plus new deleted wording and removal of the `<This message was edited>` marker. Text that merely mentions a placeholder stays text. | `test_known_media_placeholders_are_classified`, `test_ordinary_text_is_never_media`, `test_deleted_placeholders`, fixture `media_deleted.txt` | Only for the new placeholder wording |
| 4 | **Numeric terms**: `pd.read_csv` turned `007` into `7`, treated `none`/`null`/`nan` as missing values, and made TF-IDF crash (`merge on str and int64`) when every term was numeric. A chat with only numeric messages also crashed n-gram analysis. | New `src/csv_io.py` (`read_csv_typed`): text and term columns are read as strings and only an empty field is missing. Used by every module that reads a CSV and by the dashboard loader. | `test_numeric_terms_survive_the_whole_pipeline_as_strings`, `test_all_numeric_vocabulary_does_not_crash`, `test_words_that_pandas_treats_as_missing_stay_words`, fixture `numeric_terms.txt` | No calculation changes |
| 5 | **Tokenizer**: only ASCII punctuation was stripped. `don’t` (curly apostrophe) was not an English stopword; `"now"` and `now` were different terms; and the Devanagari danda made `रहा।` a different term from `रहा`. | Curly quotes are normalised; punctuation of **any Unicode punctuation category** is stripped at token edges (letters, digits, emoji and inner punctuation such as `don't` are kept). | `test_tokenizer_normalises_unicode_punctuation`, `test_curly_apostrophe_stopwords_...`, `test_danda_and_plain_word_are_the_same_term_...` | **Yes**, see section 2 |
| 6 | **Privacy**: only `+`-prefixed phone numbers and `http(s)://`/`www.` links were masked. Local numbers (`9876543210`, `098765-43210`, `022 2345 6789`), bare invite links (`chat.whatsapp.com/...`), e-mail addresses and bare web addresses stayed in the tokens; the display filter caught only digit runs of 7 or more. | `ngram_analysis.mask_phones` / `mask_urls` extended (documented patterns; dates and prices are left alone); the display filter also drops terms with 7+ digits in total, WhatsApp domains and bare domains. | `test_generalization_fixtures.py`: privacy tests; fixture `privacy_cases.txt` | **Yes**, only for text containing those patterns |
| 7 | **TF-IDF stability diagnostic** (leave-one-out) grows roughly with N squared: 500 synthetic messages took 40 s, 1,000 did not finish within the audit window. | Full leave-one-out up to 200 documents; above that, 60 evenly spaced documents. The mode is recorded in the metadata. The TF-IDF scores are not affected. | `test_stability_*`, `test_larger_chat_completes_in_reasonable_time` | Diagnostic only |
| 8 | Day/Month exports with some days 12 or below were **partly misread** (only a warning). | Day/Month evidence now **rejects** the file (`date_order_unsupported`); an ambiguous order stays a prominent warning. | `test_day_month_dates_are_rejected_instead_of_misread` | Rejects instead of misreading |
| 9 | Smaller issues: the file's final newline was appended to the last message; a failed consistency check showed the generic `analysis_failed`; TF-IDF metadata in the download listed source line numbers; hard-coded "small chat" wording in metadata; the dashboard said "mix Latin and Devanagari" for any mixed-script message and "Template Groups" (ambiguous in a group chat). | Final newline dropped; `consistency_check_failed` error code; `empty_document_line_start` not downloaded; wording made generic; Script Mix says "more than one writing system"; "Repeated Templates". | `test_download_metadata_has_no_source_line_numbers`, dashboard fixture tests | Labels and metadata only |

## 2. Expected differences after the tokenizer and privacy changes

The development chat (private; not in the repository) was re-run with the fixed pipeline and compared with the results produced before
the fixes. Only aggregate counts are reported here.

| Quantity | Before → after | Why |
|---|---|---|
| Parsed / system / user rows; text / media / deleted rows | unchanged | bracketed placeholders with a same-row caption are still media |
| Unique texts, repeats, repeated templates; participant counts; Script Mix class counts; reconciliation checks (28) | unchanged | |
| Unigram / bigram / trigram table rows | a few rows fewer in each table | three unigram forms that ended in a non-ASCII punctuation mark (for example the Devanagari danda or an ellipsis) merged with their plain forms, with the same effect in phrases |
| TF-IDF vocabulary (both variants) | smaller by a couple of terms | same merge |
| TF-IDF top-terms rows / Key Terms rows | a few rows fewer | same merge |
| Script diagnostics: tokens of "other" script | slightly fewer | punctuation-only tokens are no longer counted |

Every difference traces to non-ASCII punctuation at word edges. No message, count or ranking changed for any other reason.
The unchanged-totals assertions were run locally against the private chat (an untracked, local-only test file); they are not part of the public repository.

## 3. Performance after the fix

See `docs/final_verification.md` (section "TF-IDF scale"). The full leave-one-out stays exact for small chats; larger chats use the
documented sample. The configurable limit of 1,000 text messages is unchanged.

## 4. What was deliberately not changed

* No TF-IDF, n-gram, Script Mix, Key Terms or repetition **formula** was modified.
* No sentiment, emotion, entity recognition, language identification or new analysis was added.
* No Marathi/Hindi stopword list was added (English-only stopwords remain a documented limitation).
* Android exports remain unsupported (`docs/supported_formats.md`, section 5).
