# Sentiment / Tone Feasibility and Design Note (Milestone 3, design only)

> **Status note (2026-10-05).** This is a research/feasibility note for a feature that is **intentionally not implemented** (sentiment, emotion). Nothing from it is in the pipeline, the dashboard, the results or the requirements.

> Status: **design / feasibility assessment only. Nothing is implemented, no packages were installed,
> no datasets were downloaded, and no sentiment values exist or are reported here.**
> Decision status: **ACCEPTED by the project owner (Option C): sentiment is NOT implemented.** The text below
> is kept as originally written for the research record (updated status only, final audit 2026-10-01).
>
> Inputs to this assessment: the accepted `docs/project_plan.md`, the analysis corpus produced by the
> tested preprocessing layer, and the constraints below. Existing source, data, results, and tests were
> not modified.
>
> Any external resource named below (lexicons, datasets, models) is named only as a *candidate that
> requires verification* of existence, licence, language coverage and suitability before any use. No
> performance figure for any of them is claimed.

## Actual dataset facts used

| Fact | Value |
|---|---|
| Parsed rows | 93 (72 user, 20 system, 1 header) |
| Real text messages for NLP | **24** (18 unique texts after URL masking; 6 repeats) |
| Script composition of the 24 (read-only count from the analysis corpus) | 17 Latin-only, **7 mixed English + Devanagari**, 0 Devanagari-only |
| Sender distribution of the 24 | 23 from `Sender_1`, 1 from `Sender_2` |
| Message length in tokens | median about 9; two long messages (about 100 and 120 tokens) hold roughly half of all tokens; the rest are short |
| Forwarded (`is_forwarded`) text messages | 3 of 24 |
| Content type | announcement / invitation / request style (join-group links, size and photo requests, camp notices) |
| Sentiment ground truth | none |
| Raw chat | must remain untouched; outputs must stay anonymised |

## 1. Purpose of Sentiment/Tone Analysis

The question sentiment analysis would answer: **"What is the emotional polarity (positive / neutral /
negative) or general tone of the messages, and how does it vary across time or messages?"**

That corresponds to RQ7 in the project plan: *can sentiment or tone be characterised for this chat, and
is any such measure valid for announcement-style, bilingual text?* The plan already allowed the honest
answer to be "not reliably". This document tests that hypothesis against the actual data.

Two distinct constructs must not be conflated:
- **Sentiment** = polarity of expressed feeling (happy/unhappy, approving/disapproving).
- **Tone** = register or communicative function (formal, polite, directive, urgent). "Please share your
  picture" is polite and directive, not positive.

Most of this chat is directive/informational. Directive tone is a different measurement from sentiment
polarity and would need its own justification and validation; it is not proposed here.

## 2. Dataset Suitability

Honest assessment: **the data are not sufficient for meaningful sentiment analysis.**

- **24 messages (18 unique)** is far too small for stable descriptive proportions. One message moves a
  percentage by about 4.2 points (1/24), or 5.6 points across the 18 unique texts.
- **Little evaluative content.** The messages are mostly instructions, links and notices. A keyword
  spot-check for evaluative wording (for example "great", "thank", "inspiration") found it in at most
  one or two of the 24 messages, and one message (the long camp notice) contains most of it. That
  observation is a feasibility signal only, not a sentiment result. Polarity would probably be
  "neutral" or "not applicable" for the great majority, so any output would mostly describe the *genre*
  (announcements), not the *feelings* of the group.
- **One sender** wrote 23 of the 24 messages. Results would describe one organiser's announcements, not
  a group.
- **Repetition.** 6 of 24 messages are repeats, which would double-count identical text.
- **Length imbalance.** Two long messages account for about half of all tokens; token-level methods
  would be dominated by them.
- **No labels,** so nothing can be validated (section 5).

It is *possible* to run a tool over these messages and produce numbers. That is exactly the risk:
numbers would appear without any evidence that they mean anything.

## 3. Language Analysis

- **English (17 messages Latin-only).** Sentiment resources are abundant for English, but they are
  mostly built for reviews, social media or news. Announcement/administrative text is a domain mismatch.
- **Marathi/Devanagari.** 7 of 24 messages contain Devanagari (mixed with English words such as "group",
  "join", "team", "camp", "auction"). Marathi is a lower-resource language for sentiment.
  English-only tools would treat Devanagari tokens as unknown words and silently ignore them, so a
  score would reflect only the English fraction of a mixed message.
- **Mixed-language / code-mixed messages.** All Devanagari-containing messages are code-mixed. Code-mixed
  sentiment is a known hard problem; tools trained on monolingual text may perform worse.
- **Tokenisation/inflection.** Marathi suffixes (for example खेळाडू vs खेळाडूंनी) fragment word forms; the
  project has intentionally not added Marathi stemming or stopwords yet.
- **Existing preprocessing is not sentiment-safe.** The English stopword list currently removes negation
  words (for example "not", "no"), which would invert meaning in lexicon methods. Any sentiment method
  must start from the raw token sequence (`tokens`), not `tokens_no_stopwords`. Emoji (for example 🏐)
  and punctuation carry polarity signals in some tools and would need explicit handling.
- **Is language detection necessary?** For a valid sentiment pipeline: yes, at least a per-message
  script/language flag, so that unsupported or partially supported messages are reported as such rather
  than scored. The existing script detection (`token_script`) is a token-level proxy only; it cannot
  distinguish Marathi from Hindi (both Devanagari) and has not been validated as language detection.

## 4. Candidate Approaches

### A. Lexicon-based sentiment

- **How it works:** each word has a pre-assigned polarity score in a dictionary; a message score is an
  aggregate (sum/mean) with optional rules for negation and intensifiers.
- **Data required:** a polarity lexicon per language. English lexicons exist. A Marathi lexicon (for
  example derived from Marathi WordNet resources) would need to be **verified for existence, licence, size
  and quality** before use; none is assumed available offline. No lexicon exists for code-mixed text.
- **Fit to this dataset:** poor. English lexicon coverage of this vocabulary is likely low
  (organisational words); the Marathi side is unverified; code-mixing breaks word-level lookup.
- **Advantages:** fully transparent; needs no training data; every score traceable to specific words;
  cheap to compute.
- **Limitations:** ignores context, sarcasm and domain (words like "camp" or "selected" carry no polarity
  but "please" may be scored positive by mistake); coverage may be so low most messages score 0.
- **Explainability:** highest of the three.
- **Complexity:** negligible.
- **Evaluation requirements:** still needs labelled data to claim any accuracy, plus a **coverage report**
  (fraction of tokens/messages with at least one lexicon hit).

### B. TF-IDF + supervised classical machine learning

- **How it works:** turn text into TF-IDF features, then train a classifier (for example logistic
  regression or naive Bayes) on labelled examples.
- **Data required:** a **labelled training set** that is large and diverse enough to learn from. The
  project's 24 messages are not, and their existing TF-IDF vectors cannot serve as classifier features:
  they use a vocabulary fitted on this chat only.
- **Fit:** not feasible with the project data. Feasible only by training on an **external** labelled
  corpus, in which case the feature vocabulary comes from that corpus and transfer to WhatsApp
  announcements is a domain shift. A Marathi/mixed-language labelled dataset would have to be found and
  verified.
- **Advantages:** standard, inspectable (feature weights), trains fast, allows proper metrics.
- **Limitations:** bag-of-words loses order and negation; quality depends entirely on training data and
  its language/domain match.
- **Explainability:** good (top weighted features).
- **Complexity:** low.
- **Evaluation requirements:** held-out labelled test data (train/test split or cross-validation),
  class balance analysis, confusion matrix, per-class precision/recall/F1.

### C. Pretrained multilingual transformer/model

- **How it works:** a large language model pretrained on many languages (and possibly fine-tuned for
  sentiment) maps text to a label/score.
- **Data required:** no task-specific training data to run inference, but a **model must be downloaded**
  (not done here). Whether a specific model supports Marathi and code-mixed text for sentiment, and on
  what training domain, **requires verification**. Examples of *candidate categories* (all unverified
  here): multilingual encoder models fine-tuned for sentiment; Marathi-specific models trained on Marathi
  sentiment data.
- **Fit:** plausible in principle for mixed-language input, but the training domain (typically social
  media or reviews) differs from announcements, and Marathi code-mixed performance for any particular
  model is unknown until measured.
- **Advantages:** handles context and multiple languages without a hand-built lexicon.
- **Limitations:** opaque; downloads large model weights; output probabilities are not calibrated
  confidence; may label directive text arbitrarily positive or neutral; results can change with model
  version; adds heavier dependencies and environment risk.
- **Explainability:** low (post-hoc methods only).
- **Complexity:** highest (model size, runtime, reproducibility).
- **Evaluation requirements:** labelled test data in the target languages and domain, with the same
  metrics as B, plus agreement analysis against human annotators.

**Comparative summary**

| | Lexicon | TF-IDF + ML | Pretrained multilingual |
|---|---|---|---|
| Needs labelled data to train | No | Yes (external) | No (to run); yes (to validate) |
| Handles Marathi / code-mixed | Unverified / weak | Depends on external data | Unverified; plausible |
| Explainable | High | Good | Low |
| Effort / risk | Low | Medium | High |
| Valid on this chat without labels | No | No | No |

**No approach is validated by simply running it on these 24 messages.**

## 5. Ground Truth / Labels

**Accuracy cannot be claimed without labelled ground truth** because accuracy, precision, recall and
F1 are defined only as agreement between predictions and trusted reference labels. Without them, a
sentiment score is an unverified output of a tool. Its correctness is unknown, not merely
"approximately right".

Possible label sources:

1. **Manually labelled project messages.** Human annotators (ideally more than one, fluent in English
   and Marathi) label messages. Requirements: a written label scheme, at least two annotators, an
   inter-annotator agreement measure (for example Cohen's kappa), and resolution of disagreements.
   This is the only way to obtain *in-domain* evidence.
2. **External labelled dataset** (for example a Marathi or multilingual sentiment corpus). This can
   train (approach B) or test (any approach) but measures performance on *that* data's domain, not on
   WhatsApp announcements. Existence, licence, size, annotation quality and language match require
   verification. Nothing is downloaded in this milestone.
3. **Existing benchmark dataset.** Same as 2, with the added advantage that results can be compared with
   published work, provided the benchmark's language and domain match.

**Separation of roles:** training/evaluation data must be kept distinct from the actual WhatsApp chat.
The chat is the *application target*. Labels from an external corpus validate the *method*; only
a suitably large in-domain labelled sample validates the method *on this kind of text*.

**Explicitly rejected:** labelling only a handful of the 24 messages and then claiming a reliable model
or accuracy figure. A tiny labelled sample gives unstable metrics with huge uncertainty, most labels
would probably be "neutral", the same messages would be both tuning and test material (leakage), and one
annotator's judgment would be presented as ground truth. Such a result would look rigorous and
not be.

## 6. Language-Specific Feasibility

All statements below are feasibility assessments, not measured results. Nothing was run.

| Question | Assessment |
|---|---|
| Can an English-only lexicon handle the English-only messages (17)? | It can run, but coverage and domain fit are unverified and probably low for announcement text. |
| Can it handle Marathi/Devanagari? | No. Devanagari tokens would be unknown and ignored. |
| Can it handle code-mixed messages (7)? | Only the English fragments would count; the score would silently ignore the Marathi part. |
| Marathi lexicon | Needs verification of availability, licence, coverage. None assumed. |
| Classical ML on external Marathi data | Depends on a labelled Marathi/code-mixed corpus being found and verified. |
| Pretrained multilingual model | Marathi coverage of the pretraining data and of the sentiment fine-tuning has to be verified per model. Quality on code-mixed, announcement-style text is unknown. |
| Hindi vs Marathi | Both Devanagari; the current script check cannot separate them. Language identification would need its own validation. |

Everything under "needs verification" must be checked (existence, licence, language and domain coverage,
reproducibility, privacy of the tool, e.g. no text sent to external services) **before any
implementation**. Chat text must not be sent to third-party online services.

## 7. Forwarded Messages

Three of the 24 messages have `is_forwarded = True`. Forwarded text was not authored by the sender, so
its polarity reflects a third party (for example a forwarded link or a contact's name/school), not the
group's expressed sentiment.

Options: include as normal; exclude; analyse separately.

**Recommendation: exclude forwarded messages from any primary sentiment analysis and, if scored at
all, report them separately.** Justification:
- The research question concerns what participants express; forwarded text does not answer it.
- It is consistent with the existing project treatment (forwarded marker is metadata, `is_forwarded`
  preserved).
- With only 3 forwarded messages, a separate analysis cannot support conclusions, so "separate and
  flagged" is more honest than merging.
- The flag stays in every output so the choice can be audited or reversed.

## 8. Output Design (only if sentiment is later implemented)

Proposed per-message table, for example `results/sentiment_by_message.csv`. **No values exist.**

| Field | Meaning |
|---|---|
| `line_start` | Traceability key to `analysis_corpus.csv` (no raw text or identities) |
| `sender_anon` | `Sender_N` pseudonym |
| `is_forwarded`, `is_repeat` | Metadata carried through |
| `script_class` | latin / mixed / devanagari (validated language flag) |
| `n_tokens` | Message length, for context |
| `method`, `method_version` | Exactly which approach and version produced the value |
| `label` | Positive / neutral / negative **or** `not_scored` |
| `score` | Native numeric output of the method |
| `score_type` | What `score` is (for example lexicon aggregate vs model probability), so it is not misread |
| `confidence` | Only if the method provides a genuine, defensible measure. Otherwise left empty; model probabilities are **not** labelled "confidence" |
| `lexicon_coverage` | (lexicon methods) fraction of tokens found in the lexicon |
| `included_in_primary` / `exclusion_reason` | For example "forwarded", "unsupported language", "no coverage" |

Aggregates would report **counts** with their denominators (for example "x of 21 scored messages"),
never bare percentages, and would carry the standing caption: *descriptive, small-sample,
not generalisable; sentiment not validated unless section 9 is satisfied.*

## 9. Evaluation Plan

Depends on the method chosen; **only metrics that can actually be obtained are permitted.**

| Situation | What can be reported |
|---|---|
| No labels available | Coverage, agreement between methods (if more than one), examples for qualitative inspection. **No accuracy, precision, recall or F1.** |
| External labelled dataset (method validation) | Accuracy, per-class precision/recall/F1, macro-F1, confusion matrix, class distribution, on a proper held-out set, clearly stated as *performance on that dataset*. |
| Adequate in-domain, multi-annotator labels | The same metrics on in-domain data, plus inter-annotator agreement (for example Cohen's kappa) as a ceiling on how much human labels agree. |
| Chat-only tiny labelled set | Not acceptable as evidence of reliability (section 5). At most a labelled, qualitative sanity examination, reported as illustrative. |

Additional checks for any implementation: determinism, no leakage between training and test sets,
behaviour on empty/very short messages, negation handling using raw tokens, privacy leak checks
(same style as existing tests), and a sensitivity check (all 24 vs 18 unique, with vs without
forwarded).

## 10. Risk of Misinterpretation

A statement such as **"The group is 70% positive"** would be misleading because:

- **Tiny sample:** 70% of 24 is roughly 17 messages; changing one message shifts the figure by about 4
  points. There is no meaningful uncertainty interval at this size.
- **Announcement-heavy content:** the messages are mostly instructions. A "positive" label would often
  reflect politeness ("please") or organisational wording, not feelings.
- **Sender imbalance:** 23 of 24 messages come from one sender, so "the group" is not measured; one
  person's writing style is.
- **Multilingual text:** 7 mixed-language messages; a tool may score only the English words, so the
  score describes part of the message.
- **Forwarded content:** third-party text would be attributed to the group unless excluded.
- **Repetition:** repeated announcements would be counted several times.
- **No ground truth:** nobody has verified that "positive" means positive. The label would be an
  unvalidated tool output, and the percentage would inherit that.
- **Length imbalance:** two long messages could dominate token-level scores.

Any report would need to avoid group-level proportions, avoid causal or personality claims, and state
that sentiment is not validated.

## 11. Recommendation

**Recommended outcome: C. Do not implement sentiment analysis on this chat, because the data do not
support a defensible result. Record it as a documented, evidence-based negative finding.**

Evidence from the actual constraints:
1. Only 24 messages (18 unique) with little evaluative language: outputs would describe the announcement
   genre, not sentiment.
2. No labels, so no result could be validated; accuracy claims are impossible.
3. 7 of 24 messages are Marathi/English code-mixed, and no verified Marathi or code-mixed resource is
   available in the project; English-only tools would silently ignore part of the text.
4. 23 of 24 messages from one sender: no group-level interpretation is possible.
5. Approaches B and C require external labelled data or downloaded models that have not been verified
   and would test the method on a different domain from this chat. Approach A gives transparent scores
   but no validity evidence.

Why not B (limited/qualified analysis)? It would produce numbers whose validity cannot be checked, with
mostly "neutral" or "not scored" outputs and heavy caveats. That adds a feature but not evidence. Why
not A? Only if the data supported it.

This decision does not close the topic. It becomes a documented project result: the feasibility
assessment (this document) is itself evidence of methodological judgement. The sentiment stage in the
project plan remains "Conditional" and would be re-opened only if the gate in section 14 is met. The
project plan itself has not been edited by this milestone.

## 12. Viva Explanation

> "I investigated sentiment analysis but decided not to implement it on this chat, and I can justify
> that. There are only 24 real text messages, 23 from one sender, mostly announcements and instructions,
> and about a third mix English with Marathi. I have no labelled data, so I could not measure accuracy.
> English-only sentiment tools would ignore the Marathi text, and I could not verify a Marathi or
> code-mixed resource. Running a tool anyway would give numbers such as '70% positive' that look precise
> but that I could not defend. So I documented the options: lexicon, classical ML and multilingual
> models, what data each needs, and the conditions under which I would implement it: a verified language
> resource, labelled evaluation data, and a large enough in-domain sample. Deciding not to force it
> follows the same principle as the rest of the project: every technique must have a purpose,
> validation and stated limitations."

## 13. Rubric Alignment

- **Methodology & Implementation:** shows a reasoned method-selection process (three candidate
  approaches compared on data requirements, fit, explainability, complexity and evaluation) and rejects
  an unjustified technique. Implementation quality is demonstrated by not adding an unvalidated
  component. The decision is explainable in a viva.
- **Analysis, Results & Interpretation:** provides an evidence-based interpretation of *what the data
  can and cannot support*, and explicitly prevents misleading statements about group sentiment. The
  interpretation uses the actual dataset facts (24 messages, 23 from one sender, 7 code-mixed).
- **Conclusion & Future Work:** gives a concrete, testable future-work path (verified Marathi/code-mixed
  resource, external benchmark validation, larger in-domain labelled sample, forwarded-message
  handling) with explicit conditions, and a limitations statement for the report.

## 14. Implementation Gate

Sentiment implementation **must not begin** until **all** of the following hold:

1. **Decision:** the project owner explicitly approves reversing recommendation C, or approves a specific
   limited option (B) in writing.
2. **Resource verification:** for the chosen method, existence, licence, language coverage
   (English, Marathi, code-mixed) and domain suitability are verified and documented. Nothing is
   assumed from a package name. Models/lexicons/datasets are not downloaded until this step passes and
   approval is given.
3. **Labelled evaluation data:** a labelled dataset exists that (a) covers the languages present, (b) is
   separate from the WhatsApp chat, and (c) is large enough for stable per-class metrics; **or** an
   in-domain sample has been labelled by at least two annotators with reported agreement. Labelling a
   few of the 24 messages does not satisfy this.
4. **Evaluation protocol written first:** metrics, held-out split, no leakage, and what will be reported
   if performance is poor.
5. **Preprocessing safety:** the method uses raw tokens (negation retained), per-message language/script
   handling, and a documented policy for emoji.
6. **Forwarded messages:** excluded from the primary analysis and flagged, as in section 7.
7. **Privacy:** chat text is processed locally only (no external services); outputs contain no raw
   phone numbers, URLs or identities; leak tests extend the existing suite.
8. **Reporting rules agreed:** counts with denominators, mandatory small-sample and
   "not validated" captions, and no group-level percentages.
9. **Tests written before results are regenerated,** and existing raw data and outputs are verified
   unchanged.

---

## Sentiment Implementation Decision

**Recommended (by this design note): Option C, do not implement sentiment analysis on this dataset,
and document the assessment as a justified finding.**

**Status: ACCEPTED (Option C).** Sentiment analysis is **not implemented** in this project version; it is future work
(see `docs/emotion_sentiment_design.md` and `docs/emotion_evaluation_protocol.md` for the later research).

At the time of writing no sentiment analysis had been implemented, no packages installed, no datasets or models
downloaded, and no sentiment results generated; that remains true of the project.
