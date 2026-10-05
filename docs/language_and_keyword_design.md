# Language / Code-Switching and Keyword / Entity Insights: Design & Feasibility (Milestone 5A)

> **Status note (2026-10-05).** This note was written during development about the private development chat (`data/chat.txt`, not in the repository) and describes the validated results at that time. The current behaviour of the pipeline is described in `supported_formats.md`, `final_audit_fixes.md` and `final_verification.md`; where they differ, those pages win.

> **Current status (final audit 2026-10-01):** the LIMITED decisions below were implemented afterwards as
> **Script Mix** (`src/script_mix_analysis.py`, script composition, **not** language identification) and **Key Terms**
> (`src/key_terms.py`), with tests and result files. Language identification and NER were **not** implemented.
> Dashboard integration of Script Mix / Key Terms was completed in the final dashboard polish.
>
> Original status when written: **design / feasibility only.** Nothing was implemented; no source, dashboard, result, test or plan
> file was changed; no packages were installed and nothing was downloaded.
>
> Counts below are **verified** by read-only inspection of the existing outputs
> (`analysis_corpus.csv`, `ngram_unigrams.csv`, `ngram_script_diagnostics.csv`, `tfidf_top_terms.csv`,
> `processed_chat.csv`). No message text and no terms from the chat are reproduced in this document.
> External tools, models and datasets are named only as **candidates that require verification**
> (existence, licence, language coverage, size, behaviour on short code-mixed text) before any use. No
> accuracy or speed figure is claimed for any of them.

## 0. What exists and what the data looks like

**Already implemented and validated:** token-level script classification
(`ngram_analysis.token_script`: latin / devanagari / placeholder / other), the script diagnostics table
(`ngram_script_diagnostics.csv`), a `script` column in the TF-IDF tables, and a script note in the
dashboard's NLP Insights page.

**Shape of the private development chat (exact counts omitted; the chat is not published):**

* a small corpus of text messages, fewer unique texts after masking;
* most messages Latin-script only, a minority mixing Latin and Devanagari in one message, no Devanagari-only messages and one link-only message;
* a larger share of Latin than Devanagari tokens before stopword removal, plus placeholders and a few digit/emoji/symbol tokens;
* in mixed messages, a wide spread of Devanagari share and several script alternations, with a few long messages holding a large share of all tokens;
* some very short messages; no Devanagari digits, danda punctuation or zero-width joiners were found in the development chat;
* one dominant sender;
* several mixed-script messages that were near-identical variants of one announcement template. The exact and masked
  repetition measures count such variants as unique because they are not identical, and that similarity was
  **not measured** by any implemented method.

The fictional chats in `tests/fixtures/` (for example `parser_unicode.txt` and `group_12.txt`) reproduce these situations with invented text.

## A2. Is the corpus sufficient for language identification?

**No.** Reasons: only a small number of text messages with few mixed-script messages, several of which are similar
to one another; no language labels and no way to obtain them without a reader fluent in both languages;
many messages have 8 tokens or fewer; a few long messages dominate the tokens; romanised text cannot be
seen; and a Hindi-versus-Marathi decision inside Devanagari needs validation that does not exist. Any
language-ID result would be an unvalidated label. Descriptive counts of script are supportable; statistics
or inference are not.

## A3. Approaches

| | A. Script-based analysis | B. Lightweight language identification | C. Multilingual language-ID model/library |
|---|---|---|---|
| Methodology | Classify each alphabetic token by Unicode script; summarise per message | Statistical model (for example character n-gram profiles) over longer text, small footprint | Larger pretrained identifier (for example a fastText-style or transformer-based model) |
| Strengths | Deterministic, explainable in one sentence, no training data, works for any script | Labels languages, not scripts; small and fast | Broader language coverage; can separate closely related languages better than B on long text |
| Weaknesses | Cannot name a language; cannot separate Marathi/Hindi or English/romanised text | Designed for paragraphs, not 5-token chat lines; weak on code-mixed text; some implementations are non-deterministic unless seeded; Hindi/Marathi confusion | Model download; heavier; still trained mostly on monolingual text; code-mixed and romanised chat is out of its design domain; confidence scores are not calibrated probabilities |
| Dependencies | Standard library (`unicodedata`, regex), already present in `token_script` | A package and its language profiles (**none installed**; availability and Marathi coverage require verification) | A package plus a downloaded model file (**none installed**; `torch` is present but no language-ID or transformers library is); size, licence, coverage require verification |
| Language coverage | Any language, by script only | Marathi/Hindi/English support varies by tool; requires verification | Usually includes Marathi/Hindi/English; requires verification per model |
| Performance | Linear in tokens; negligible | Fast (not measured here) | Heavier start-up and memory (not measured here) |
| Privacy | Local; no text leaves the machine; outputs can be pure counts | Local if run locally; must not use any remote/API service | Local inference is fine; a remote service is not acceptable |
| Suitable here? | **Yes, descriptively** | No: no validation data, short code-mixed text | No: same, plus download and size |

Conclusion: only approach A is defensible for this dataset, presented as **script mix**, not language.

## A4. Decision (Language / Code-Switching)

**LIMITED / DESCRIPTIVE ONLY:** a message-level **script composition and script mixing summary**
(approach A), presented as counts with their denominators. **EXCLUDE** language identification
(approaches B and C) for this dataset, because it could not be validated.

## A5. Design of the limited implementation (not built)

**Definitions (proposed, deterministic, standard library only)**
- An *alphabetic token* contains at least one letter (by Unicode name) of a Latin or Devanagari letter;
  placeholders, digits, emoji and punctuation are excluded. Devanagari is detected by Unicode letter names
  (so Devanagari digits and the danda are not mistaken for letters). The existing `token_script` function
  is unchanged; the stricter definition is for the new module only. The current data contains no
  Devanagari digits, danda or joiners, so both definitions are expected to agree on it, which must be
  re-verified.
- *Message class:* `latin_only`, `devanagari_only`, `mixed_script` (both scripts among alphabetic
  tokens), or `no_alphabetic`.
- *Devanagari share:* Devanagari alphabetic tokens divided by alphabetic tokens, per message.
- *Script alternation count:* adjacent alphabetic tokens of different script in a message. This is an
  observed alternation, not a count of code-switch points.
- *Short message:* 3 alphabetic tokens or fewer, reported separately because a class for a very short
  message says little.
- Computed for **all messages (primary)** and **unique texts (sensitivity)**, like the TF-IDF design, so
  repetition does not silently inflate classes.

**Output fields** (aggregate only; no per-message rows, no text)
- `script_mix_summary.csv`: `variant`, `message_class`, `messages`, `denominator`, `short_messages`.
- `script_mixing_stats.csv`: `variant`, `metric`, `value`, `denominator` with: mixed messages; mixed messages
  with at least one alternation; total alternations; median and maximum alternations among mixed
  messages; counts of mixed messages per Devanagari-share band (for example up to 0.25, 0.25 to 0.5, 0.5 to
  0.75, above 0.75); messages with no alphabetic token.
- Token totals by script already exist (`ngram_script_diagnostics.csv`) and would be reused.

**Metrics and reconciliation checks:** class counts sum to the number of text messages (and the unique-text count for the second variant); unique plus repeat messages reconcile with the repetition summary; token totals by script
equal the existing script diagnostics (Latin, Devanagari, placeholder and other tokens before stopword
removal); alternations are zero for every non-mixed message.

**Validation method and tests (to write before implementing)**
- Known examples: pure English line, pure Devanagari line, mixed line with a known alternation count,
  emoji-only, link-only (`<URL>` only), digits-only, Devanagari digits only, a danda alone, zero-width
  joiner inside a Devanagari word, a token that is glued across scripts, an empty message.
- Short-message behaviour: one- and two-token messages are classed and flagged short, never dropped.
- Determinism (byte-identical reruns), all-versus-unique consistency, and agreement with the existing
  script diagnostics.
- A regression test that the existing tokenisation, n-gram, TF-IDF and analytics outputs stay
  byte-identical.
- Privacy: outputs contain only counts; none of the values from the privacy fixtures used by the existing
  leak tests appears (phone numbers, names, URLs, text).

**Privacy:** counts only; no terms and no text; nothing needs the term filter. Tiny counts may still be
identifying in a very small group, so the usual "descriptive, small sample" caption applies.

**Dashboard:** a compact panel with horizontal bars of message classes (all versus unique) and a small
table of the mixing statistics, with a plain note that script is not language. Fixed colours for the two
scripts reuse the existing script colours.

**Limitations to display:** script is not language; Devanagari may be Marathi, Hindi or other; Latin may be
English or romanised text; Latin words in a Devanagari sentence may be names or loanwords; very short
messages say little; no inferential statistics at this sample size; the five near-template mixed messages
weigh heavily in the mixed count.

---

# PART B: Keyword / Entity Insights

## B1. Keyword insights versus Named Entity Recognition

| | Keyword insights | Named Entity Recognition (NER) |
|---|---|---|
| Question | Which terms characterise the text? | Which spans are names of people, organisations, places, dates, events? |
| Method | Counting and ranking (statistics) | Sequence labelling (usually a trained model) |
| Needs a model/labels | No | Yes (model, and labels to evaluate it) |
| Output | Words/phrases with scores | Spans with entity types |
| Privacy | Terms can contain names, but no type information | By design surfaces exactly the names and places the project hides |

They are different capabilities and are decided separately.

## B2. Is a new keyword algorithm necessary?

**No.** The existing outputs already contain the ingredients:
- frequency with and without repeated messages (`count_all`, `count_unique`, `msgs_all` in the n-gram tables);
- distinctiveness within the chat (TF-IDF totals, means and ranks for the primary and sensitivity variants);
- repetition effects (Patterns page: occurrences and TF-IDF ranks all versus unique);
- stopword handling (English only, with Devanagari terms left in, plus the script column);
- phrases (bigrams and trigrams).

Established keyword-extraction algorithms (graph-based or statistical keyphrase extractors, for example
RAKE, YAKE or TextRank) rely on stopword lists and on enough running text; with 24 short, template-heavy
messages they would add complexity and instability without evidence of benefit. Their Marathi support is
unverified.

What is genuinely missing is a **repetition-aware ranking that answers "which terms appear across many
different messages?"** The n-gram tables rank by total occurrences (inflated by repeats) and TF-IDF ranks by
distinctiveness (which rewards rarity). A ranking by **spread across unique texts** sits between them and is
a view, not an algorithm.

## B3. Evaluate NER

**Categories considered:** PERSON, ORGANIZATION, LOCATION, DATE, EVENT, OTHER. None would be enabled by
default; each would need separate validation.

| Consideration | Assessment for this project |
|---|---|
| Multilingual NER availability | English pipelines exist (for example spaCy English models). Marathi/Indic NER exists in research tooling (for example IndicNER-style models, multilingual transformer NER models, Hindi models in Stanza); coverage for **Marathi** and for chat text **requires verification** per tool. None is installed. `torch` is present but no NER or transformers library is. |
| English + Marathi/Devanagari suitability | Models are typically trained per language on clean text (news, Wikipedia, machine-translated data). Transfer to informal, bilingual chat is unverified. |
| Short WhatsApp messages | Little context for disambiguation. Some of the messages are mostly capital letters, which defeats capitalisation cues that many models and all heuristic approaches rely on. |
| Code-switching | Models trained on monolingual text often fail on Latin names inside Devanagari sentences (seen here: Latin words are the main content words in mixed messages). |
| Proper-name detection | Names, team names and places in announcements are frequent. Distinguishing a person from a team or organisation from a place needs context that short lines lack; a roster-style message (a list of capitalised names with no sentence) is one of the current messages. |
| False positives | High risk: capitalised words in announcements, acronyms, emoji-adjacent text, hashtags. |
| Privacy risk | **High:** NER would extract exactly the names and places that the display layer hides. Showing entities contradicts the privacy design; showing only per-type counts is safer but unvalidated. |
| Model size / dependencies | Transformer models are large downloads and need a new library; spaCy/Stanza models are smaller but language-limited. Sizes and licences require verification. |
| Evaluation with a few dozen messages | **Impossible.** No labels, too few entities per type, and any labelling would be by the same person who designs the system. |

## B4. Comparison of approaches

| | A. Keyword insights only | B. Multilingual NER | C. Keyword + NER | D. Exclude NER, keep existing NLP features |
|---|---|---|---|---|
| Value | Moderate: a repetition-aware key-term ranking | Possible in principle (entities by type) | Highest in principle | Existing n-gram, TF-IDF, patterns already answer the core questions |
| Complexity | Low (a display-layer join of existing tables) | High (model, dependency, download) | High | None |
| Reliability | High: exact counts, deterministic | Unknown for Marathi/mixed short text | Unknown | High |
| Evaluation difficulty | Low (reproducibility and consistency checks) | Very high (labelled multilingual data needed) | Very high | None |
| Privacy risk | Low to moderate (terms only, existing filter) | High | High | Lowest |
| Viva explainability | High | Low to moderate ("black box", unvalidated) | Low to moderate | High |

## B5. Decision (Keyword / Entity)

- **Keyword Insights: LIMITED / DESCRIPTIVE ONLY.** A small derived "key terms" view over existing outputs.
  No new algorithm, no new analysis module required.
- **Named Entity Recognition: EXCLUDE** for the current dataset (approach D for NER). It cannot be
  evaluated, carries high privacy risk and adds an opaque dependency; capitalisation cues fail on
  announcement-style text. Not forced because it sounds advanced.

## B6. Keyword insights: definition (if approved)

- **Source data:** tables already loaded by the dashboard: `ngram_unigrams` (occurrences and messages
  containing the term, with and without repeats) and `tfidf_top_terms` (document frequency and TF-IDF per
  variant). No new result files; it can be computed in the display layer by a small, tested function.
- **Eligible terms:** unigrams with English stopwords removed; placeholders excluded; must pass the existing
  display filter (terms in at least two messages by default).
- **Metric ("spread"):** the number of **unique texts** that contain the term (document frequency in the
  sensitivity variant). Reported next to occurrences across all messages, occurrences across unique texts,
  the repetition ratio, and the term's total TF-IDF.
- **Ranking:** spread descending; ties by total TF-IDF (sensitivity variant) descending; then alphabetical
  (deterministic).
- **Duplicate / repetition handling:** repeated messages are never removed; the table shows both views so a
  term that is frequent only because one message was repeated is visible (high occurrences, low spread).
- **Output schema (display):** `term`, `script`, `unique_texts_containing`, `messages_containing`,
  `occurrences_all`, `occurrences_unique`, `repetition_ratio`, `tfidf_total_unique`.
- **Visualisation:** a compact table with an optional bar of spread (top terms), consistent with the
  existing bar style; script colour as in the TF-IDF tab.
- **Interpretation wording:** "appears in many different messages", never "topic", "importance" or
  "what people care about".
- **Limits:** small N, English-only stopwords (Devanagari function words can rank), template messages;
  overlap with the Patterns page's comparison table is acknowledged (this view is a different ranking of
  the same evidence, not new evidence).

## B7. NER: strict validation protocol (required before any implementation)

NER would be reconsidered only if **all** of the following hold:
1. A **labelled evaluation set** exists that is independent of any tuning, covers English, Devanagari and
   mixed text in the WhatsApp-message domain, and contains enough entities of each type to report
   intervals (a 24-message chat cannot).
2. Written **annotation guidelines**, at least two annotators, and reported inter-annotator agreement.
3. **Acceptance criteria fixed before running the model:** per-type entity-level strict-match precision,
   recall and F1 (micro and macro), reported separately for English, Devanagari and mixed messages, with
   confidence intervals; a minimum threshold per type below which that type is not offered.
4. **Error analysis:** false positives on capitalised announcements, roster lists, acronyms and emoji;
   false negatives on Latin names inside Devanagari sentences; per-message-length results.
5. A **privacy design**: entity strings are internal only; any display is limited to aggregate type counts,
   and only for types that pass (3); tested with leak tests. NER is never used to certify that text is free of
   personal data.
6. A verified, documented model (licence, size, languages, version pinned) and a reproducible offline run.

---

# PART C: Privacy

## C1. Risks

| Item | Risk in this project |
|---|---|
| Personal names | In sender fields, system messages (handled: never shown) and in message text; in NLP terms they appear if they occur in two or more messages |
| Phone numbers | Masked in analysis text; absent from displayed tables (tested) |
| URLs | Masked as a placeholder; invite links are access tokens and are never shown |
| Locations | Not detected by any method here; place names can appear as ordinary terms |
| Organisation and team names | Not detected; as announcement text repeats them, they pass the two-message filter. Among the 45 unigram terms currently displayable (two or more messages) at least four are place or team/organisation names by manual inspection (not listed here), so the filter plainly does not remove such terms |
| Rare terms | Hidden by default only if they occur in one message |
| Single-message terms | Hidden by default; a user toggle reveals them with a warning |
| Combinations | Bigrams/trigrams can reveal more than single words (for example a name next to a role) |

**The display filter is a precaution, not PII detection.** A name used in two or more messages is shown,
and a name can be absent from the tables yet present in the file.

## C2. What may be shown, hidden, or kept internal

| Category | Policy |
|---|---|
| **Can be shown** | Counts, dates, `Participant_N` pseudonyms, generic system-message categories, anonymous template ids, script-mix counts, aggregate term tables that pass the display filter (two or more messages) with the existing caption |
| **Hidden by default, revealable by an explicit user choice** | Terms occurring in only one message (existing behaviour) |
| **Never shown or downloadable** | Phone numbers, sender identifiers, names from system messages, raw URLs, raw message text, link/number-like terms (existing defensive pattern filter) |
| **Internal only** | `processed_chat.csv`, `analysis_corpus.csv`, message-level TF-IDF, any per-message script table, any entity strings if NER were ever used |

**Possible future strengthening (not proposed now):** a configurable higher minimum-message threshold; a
user-supplied list of terms to hide; showing entity-type counts only. None would make the filter complete
PII detection, and the wording must say so.

---

# PART D: Dashboard integration

The suggested layout (inside NLP Insights: Unigrams, Bigrams, Trigrams, TF-IDF, Language / Code-Switching,
Keyword / Entity Insights) is **appropriate in structure** (one page, extra tabs, no new page), with
adjustments:

- **Rename** the language tab **"Script mix"** (not "Language" or "Code-Switching") so the interface does
  not claim language identification; the explanation panel says why.
- **Rename** the last tab **"Key terms"**; "Entity" is dropped because NER is excluded.
- Seven-tab width is acceptable but no further tab should be added. An alternative that keeps the page
  smaller is to fold "Key terms" into the TF-IDF tab as a third view and keep only "Script mix" as a new
  tab. This is left for approval.
- No new page is justified. Both additions are descriptive, reuse the display filter, carry the standing
  "descriptive, this chat only" caption and a "What am I looking at?" panel (what is measured, how, why,
  limitation), and must handle chats with no text messages by showing an empty state.

**Status: PENDING.**

---

# PART E: Evaluation

**Script mix (deterministic, no accuracy claim):** known-example tests (listed in A5), mixed-script and
short-message cases, determinism, reconciliation with existing script diagnostics, all-versus-unique
consistency, zero-text and no-alphabetic inputs, regression that existing outputs are byte-identical,
privacy leak tests with counts-only outputs. No accuracy is claimed because nothing is being predicted.

**Key terms (reproducibility and consistency):** identical output on reruns; ranking determinism (ties
broken alphabetically); agreement of every column with the source tables; overlap and rank agreement with
TF-IDF and with raw frequency reported descriptively; sensitivity to repetition (all versus unique);
stability under leaving one message out (as already done for TF-IDF); the display filter applied before
display and download; leak tests with the existing privacy fixtures (names, phone numbers, URLs, a
single-use rare term must not appear with the filter on).

**NER (only if ever reconsidered):** the protocol in B7: labelled data, precision/recall/F1 per type and per
language condition, agreement with human labels, multilingual validation, error analysis, and acceptance
thresholds fixed in advance. **No accuracy is claimed without evaluation data.**

---

# PART F: Current dataset decision

For this project and this dataset:

- **Script mix (limited):** defensible, explainable in one sentence, deterministic, privacy-safe (counts only)
  and relevant: a share of the text messages mix scripts. It extends an existing, validated script
  note. It must be named script mix and never claimed as language identification.
- **Key terms (limited):** useful only as a repetition-aware view; needs no new algorithm; implemented as a
  thin, tested join of existing tables. Its marginal value over the existing TF-IDF and Patterns views is
  modest, which is why it stays limited and optional.
- **Language identification: excluded,** because it cannot be validated on 24 short, code-mixed messages.
- **NER: excluded:** not evaluable, high privacy risk, poor fit to short all-capital announcement text.

---

# PART G: Future work

| Capability | Would be revisited with |
|---|---|
| Language identification (Latin: English versus romanised; Devanagari: Marathi versus Hindi) | A much larger, varied set of conversations; language labels produced by fluent readers; a verified, local, licence-compatible tool whose behaviour on short code-mixed text has been measured; code-mixing-aware metrics |
| Code-switching analysis proper | Word-level language labels on a labelled sample and a defined switching measure; until then only script alternation is reported |
| NER | The B7 protocol: labelled English/Marathi/mixed chat data, verified multilingual models, fixed acceptance thresholds, and a privacy design with entity strings kept internal; potentially also as an **internal privacy scanner** (flagging terms for hiding), which would itself require its own validation because false negatives cannot be tolerated |
| Stronger keyword extraction | Longer conversations and validated Marathi stopword/lemmatisation resources, so that a keyphrase method can be justified over the existing rankings |
| Stronger privacy controls | Configurable thresholds, user-defined hide-lists, and a documented review step before any public sharing |

---

## Viva explanation

> "I checked whether I could add language identification and named-entity recognition. With 24 short
> messages, some of them mixing Devanagari and Latin script and no labelled data, I could not validate either,
> and a label I cannot validate is not a result. Script, however, is a deterministic property, so I planned a
> small, privacy-safe script-mix summary and named it script mix rather than language. For keywords I found
> that my existing frequency, TF-IDF and repetition views already cover the ground, so I only planned a
> repetition-aware ranking by how many different messages contain a term. I excluded NER because it would
> extract exactly the names I am trying to protect, cannot be evaluated on this data, and suits neither
> all-caps announcements nor code-mixed text. I documented what would be needed to revisit each one."

## FINAL DECISION

Language / Code-Switching:
LIMITED

Keyword Insights:
LIMITED

Named Entity Recognition:
EXCLUDE

Dashboard Integration:
PENDING


## Update from the final audit (2026-10-05)

* A "mixed-script" message contains characters from more than one detected writing system (Latin and Devanagari, but also any other script).
  The dashboard says exactly that and never "mixed Hindi-English". Script Mix remains script composition, not language identification.
* Scripts other than Latin and Devanagari (for example Gujarati, Tamil, Arabic) are counted as "other script".
* Tokens now lose edge punctuation of any Unicode category (including the Devanagari danda), which affects Key Terms through the shared vocabulary.
