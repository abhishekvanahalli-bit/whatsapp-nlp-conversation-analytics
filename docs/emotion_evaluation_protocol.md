# Emotion & Sentiment Evaluation Protocol: Labelled Evaluation Dataset and Annotation Protocol (Phase 2)

> **Status note (2026-10-05).** This is a research/feasibility note for a feature that is **intentionally not implemented** (sentiment, emotion). Nothing from it is in the pipeline, the dashboard, the results or the requirements.

> **Phase 2: protocol design only.** No labelled dataset was created, no model was run, no package was installed,
> no model was downloaded, and no project file other than this document was created or changed.
> The real WhatsApp chat is **not** used as evaluation data. No model prediction is used to create human labels.
>
> This protocol is meant to be **approved before any item is authored or labelled** (a pre-registration of the
> evaluation plan). Numbers such as dataset sizes, workload hours and acceptance thresholds are **planning
> proposals with stated reasons**, not measurements, and are flagged for supervisor review.
>
> Inputs: `docs/sentiment_design.md` (why sentiment was excluded for the current chat), `docs/emotion_sentiment_design.md`
> (Phase 1: candidates, licences, qualitative test), `docs/language_and_keyword_design.md` and the Script Mix module
> (deterministic script classes), `docs/project_plan.md`, and the test and requirements files (155 tests; no
> modelling dependency in the project). Dataset and licence facts in section 6 were read from the dataset cards on
> 2026-10-01.

**What Phase 1 established that shapes this protocol**
- The current chat has 24 text messages and cannot be a validated dataset on its own.
- Roman-script Hindi and Marathi emotion is UNVERIFIED for every candidate model.
- Candidate models disagreed on the same sentences and several gave 0.99 to 1.0 probabilities on outputs that did not
  match the sentence's evident meaning. **A probability is not treated as a reliability measure anywhere in this protocol.**
- The emotion models use incompatible label sets (11, 10 and 7 labels).
- No production pipeline exists.

## 1. Evaluation objective

> **How reliably can the shortlisted sentiment and emotion approaches classify short conversational messages across
> the language and code-mixing conditions relevant to WhatsApp chats, and in which conditions should they abstain?**

Sub-questions:
1. For each language/script/code-mix stratum and each model: how well does **sentiment** (positive, negative, neutral)
   agree with human labels?
2. The same for **emotion**, evaluated on its own terms and **never combined with sentiment into one metric**.
3. Is the failure concentrated in particular strata (Roman script, code-mixing, emoji, negation, sarcasm)?
4. Is the model's score informative about its own correctness after calibration, and what abstention behaviour results?
5. How much of the ground truth is itself contested (human disagreement and ambiguity)?

Out of scope: training or fine-tuning, LLM-based labelling, and any statement about the real chat's sentiment.

## 2. Sentiment label definitions

**Gold set:** `Positive`, `Negative`, `Neutral`. Sentiment is the **polarity of the evaluation or attitude the writer
expresses or intends** toward the topic, situation or interlocutor. It is a different construct from emotion.

| Class | Operational definition |
|---|---|
| **Positive** | Explicit favourable evaluation, pleasure, approval, praise, gratitude, congratulations, or encouragement |
| **Negative** | Explicit unfavourable evaluation, displeasure, complaint, criticism, disappointment, blame, rejection, distress |
| **Neutral** | No expressed evaluation: factual or informational content, scheduling, logistics, neutral acknowledgements, greetings without evaluative content |

**Rules for specific situations**

| Situation | Rule |
|---|---|
| Explicit positive / negative statements | Label the polarity expressed ("this was wonderful", "I hate waiting"). Intensity is not recorded |
| Informational / factual messages | `Neutral`, even if the fact is good or bad news for someone, unless the writer also evaluates it |
| Questions | `Neutral` unless the question carries an evaluation ("why is this so slow?" is `Negative`; "is the match at 5?" is `Neutral`) |
| Requests and commands | `Neutral` unless evaluative or emotive ("please send the file" `Neutral`; "stop wasting my time" `Negative`) |
| Agreement / acknowledgement ("okay", "fine by me") | `Neutral` unless an evaluation is expressed |
| Gratitude and praise | `Positive` |
| Disagreement / refusal | `Negative` only if it expresses displeasure or criticism; a polite factual "I can't come" is `Neutral` |
| Mixed positive and negative content | If neither clearly dominates, flag `MIXED` (do not force a class). If one clearly dominates the writer's overall stance, label that class |
| Negation | Judge the meaning **after** negation ("not bad" positive-leaning, "not happy" `Negative`); where the scope is unclear, flag `AMBIGUOUS` |
| Sarcasm and irony | Label the **intended** polarity when the cue is clear in the text or emoji (for example an obviously exaggerated praise of a clear failure is `Negative`) and add the `SARCASM` tag; if the intent cannot be established from the message, flag `UNCERTAIN`. Never label the literal surface polarity by default |
| Uncertainty, hedging ("maybe it will be fine") | Label by the evaluative content present; hedging alone is not a polarity |
| Emoji | Emoji are evidence of polarity like words. Polar emoji (for example clearly happy, angry, sad faces, hearts, thumbs) support that polarity; ambiguous or decorative emoji (for example a sports ball) add no polarity. **Conflict between text and emoji** is labelled by the overall intent and tagged `EMOJI_CONFLICT`; if intent is unclear, `AMBIGUOUS`. Emoji-only messages are labelled by their conventional polarity, else `Neutral` |
| Humour | Label the polarity of the attitude (teasing praise is `Positive`); tag `HUMOUR` |
| Culturally specific expressions | Judge using the project glossary (section 8L); if the annotator lacks the competence, `NEEDS_EXPERT` |

**Annotation states (never silently forced into a class).** Each item receives a sentiment label **and** at most one flag:
- `MIXED`: both polarities present and neither dominates;
- `AMBIGUOUS`: two or more reasonable readings (record the alternatives in the note);
- `UNCERTAIN`: the annotator cannot decide (insufficient context, unknown expression);
- `NEEDS_EXPERT`: requires a fluent reader of that language or expression.
Items that remain `MIXED`, `AMBIGUOUS` or `UNCERTAIN` after adjudication are **excluded from the primary scoring set** and reported
as a separate **contested subset** (with counts and with descriptive model behaviour, where abstaining is the expected ideal outcome).

## 3. Emotion label strategy

**No universal emotion taxonomy is invented.** The strategy is: annotate a **small core label set** for which at least
three of the candidate label spaces have a counterpart, record everything else as **tags**, and **evaluate every model only
on the labels it can actually produce**.

### 3.1 Native labels of the shortlisted models (from Phase 1)

| Model | Native labels | Output |
|---|---|---|
| A. tabularisai/multilingual-emotion-classification | anger, contempt, disgust, fear, frustration, gratitude, joy, love, neutral, sadness, surprise (11) | Multi-label (independent sigmoids, threshold 0.5) |
| B. MahaEmotions-BERT (Marathi) | Anger/disgust (merged), Excitement, Fear, Happiness, Neutral, Pride, Respect, Sadness, Sarcasm, Surprise (10) | Single label (softmax) |
| Hindi emotion model (vashuag/HindiEmotion) | anger, disgust, fear, joy, neutral, sadness, surprise (7) | Single label (softmax) |

### 3.2 Which labels map cleanly and which do not

| Gold core label | A | B | Hindi model | Mapping status |
|---|---|---|---|---|
| fear | fear | Fear | fear | **Clean** (same concept and name in all three) |
| sadness | sadness | Sadness | sadness | **Clean** |
| surprise | surprise | Surprise | surprise | **Clean** (valence not specified by any model) |
| neutral | neutral | Neutral | neutral | **Clean by name, definitions differ** (A falls back to neutral when nothing exceeds the threshold) |
| joy | joy | Happiness | joy | **Clean for A and Hindi; approximate for B.** B also has a separate *Excitement*. The main analysis treats Happiness as B's counterpart of joy, and a **sensitivity analysis** (Excitement treated as joy-related) is reported **separately**; the two are never silently merged |
| anger | anger | Anger/disgust | anger | **Clean for A and Hindi; partial for B** (B's class also contains disgust) |
| disgust | disgust | Anger/disgust | disgust | **Clean for A and Hindi; partial for B** |
| other_emotion (see tags) | gratitude, love, frustration, contempt | Excitement, Pride, Respect, Sarcasm | none | **No cross-model counterpart.** Kept separate |

- **B evaluation coarsening:** for B only, gold `anger` and gold `disgust` items are scored under one grouped label
  `anger_or_disgust`. This is a documented coarsening of the *gold* for that model, applied only in B's table, so that B
  is not penalised for a merge it makes by design. B is excluded from per-class anger-versus-disgust comparisons.
- **Labels excluded from cross-model comparison:** every extension label (gratitude, love, frustration, contempt,
  excitement, pride, respect, sarcasm) and any label a model cannot produce.
- **Cross-model comparable core:** `fear`, `sadness`, `surprise`, `neutral` (clean for all three); `joy`, `anger`, `disgust`
  are comparable for the subset of models named in the table. Comparisons state which labels they use.

### 3.3 Proposed evaluation label set

- **Primary emotion (one per message):** `joy`, `anger`, `sadness`, `fear`, `surprise`, `disgust`, `neutral`, `other_emotion`.
  `neutral` means no discernible emotional expression. `other_emotion` is used when the dominant emotion is better described
  by something outside the core set, and then **requires a secondary tag**.
- **Secondary tags (optional unless `other_emotion`):** `gratitude`, `love`, `frustration`, `contempt`, `excitement`, `pride`,
  `respect`, `sarcasm`, plus `disappointment`, `anxiety`, `amusement` (recorded for description; not matched to any model label).
  A message may carry more than one tag. Tags that correspond to a model's native labels allow a **native-label analysis** for that
  model (for example an item tagged `gratitude` is scorable against model A's *gratitude*), reported descriptively where counts are small.
- **Why a single primary emotion plus tags, not multi-label gold:**
  1. two of the three candidate models (and most published emotion models) output a single label;
  2. short messages usually have one dominant emotion, and forcing annotators to list every nuance raises disagreement;
  3. the multi-label model can still be scored: its **top-scoring label** is compared with the primary gold, and a second metric
     (gold primary **contained in** the model's above-threshold set) is reported; nothing is scored on labels the gold does not carry;
  4. tags preserve mixed affect descriptively without making it a scoring target.
  Messages in which two emotions are equally strong are flagged `MIXED_EMOTION` and, like ambiguous items, leave the primary scoring set.
- **No label merging for convenience.** The set above is *not* a claim that these labels are equivalent across models.

## 4. Language and code-mix categories

Latin script does **not** imply English, and script is not language. Each item carries two independent properties:
- **Declared language form** (assigned by the author and confirmed by a fluent reviewer): English, Hindi, Marathi, Hindi-English mixed,
  Marathi-English mixed.
- **Script class** (computed deterministically by the Script Mix definitions, not by a language identifier): `latin_only`,
  `devanagari_only`, `mixed_script`, `no_alphabetic`.

Language-identification models are **not** used to assign strata (circular, and unvalidated).

**Eight disjoint primary strata** (each item belongs to exactly one):

| # | Stratum | Declared form | Script class required |
|---|---|---|---|
| S1 | English | English | latin_only |
| S2 | Hindi, Devanagari | Hindi | devanagari_only |
| S3 | Hindi, Roman | Hindi written in Latin script | latin_only |
| S4 | Marathi, Devanagari | Marathi | devanagari_only |
| S5 | Marathi, Roman | Marathi written in Latin script | latin_only |
| S6 | Hindi-English code-mixed (Roman) | Hindi-English | latin_only |
| S7 | Marathi-English code-mixed (Roman) | Marathi-English | latin_only |
| S8 | Mixed-script (Devanagari and Latin in one message) | Hindi-based or Marathi-based, language recorded per item | mixed_script |

**Cross-cutting tags** (reported as additional breakdowns, not strata): `neutral_informational` (the "neutral/informational chat language"
category), `emoji` (contains emoji; `emoji_only_or_heavy` for emoji-only or emoji-dominant), `negation`, `question`, `request_command`,
`sarcasm`, `humour`, `short` (three or fewer alphabetic tokens), `slang`, `loanwords_in_devanagari` (English words written in Devanagari
stay in S2 or S4).

**Rules**
- An item is placed in S3/S5/S6/S7 only if the author can justify the language from a full sentence; isolated words shared by Hindi and
  Marathi are not used as stand-alone items (`lang_ambiguous` items are dropped or rewritten).
- The script class is verified automatically; a mismatch moves or corrects the item before labelling.
- Romanised spelling is left natural and variable (for example "nahi/nahin", "khup/khoop"): normalising it would hide the problem being tested.

## 5. Message-type coverage

Coverage is achieved by **scenario design**, not by asking authors to write "an angry sentence". Naturalness has priority over
balance; a cell that cannot be filled naturally in a stratum is left sparse and reported as such (for example disgust in some strata).

Target minimum shares of the test set (items may carry several types; minima apply to the whole set and are aimed at every stratum
where natural):

| Coverage item | Target minimum (of test items) | Notes |
|---|---|---|
| Positive, negative, neutral statements | about 35% / 35% / 30% (sentiment, before exclusions) | Ranges of about 10 points are acceptable |
| Questions | 10% | Neutral and evaluative questions both |
| Requests | 10% | |
| Commands / imperatives | 6% | |
| Agreement and acknowledgement | 6% | |
| Disagreement and refusal | 6% | Polite neutral and displeased versions |
| Praise | 8% | |
| Complaints | 8% | |
| Excitement | 6% | Tag |
| Sadness, anger, fear/anxiety, surprise | see emotion distribution, section 7 | Primary emotion |
| Disgust | where naturally expressible (about 4%) | Sparse by design |
| Gratitude | 6% | Tag |
| Disappointment | 5% | Tag |
| Humour | 4% where natural | Tag |
| Sarcasm | 3% where natural (and at least 2 per stratum in Option A) | Tag; hardest case, reported separately |
| Negation | 10% | Both polarity-flipping and non-flipping |
| Emoji-containing | 15% (of which about one fifth emoji-only or emoji-heavy) | Per stratum at least 15% |
| Short messages (3 tokens or fewer) | 10% | |
| Conversational slang | 15% | |
| Code-mixed informal messages | covered by S6, S7, S8 | |
| Neutral / informational chat language | at least 25% per stratum | |

## 6. Dataset source strategy

**Do not use the real WhatsApp chat.** Sources, in order of importance:

**6.1 Manually authored synthetic conversational items (primary; all strata).**
- Authored by fluent writers of the relevant language form, in short WhatsApp-style messages, from a **scenario bank** (for example
  team practice logistics, college group chat, family plans, exam stress, a delayed bus, a match, food, weather, festivals, small disputes,
  thanks and congratulations) using invented people and no real names, numbers or links.
- Authors **do not see any model output** and do not copy from: the real chat, the Phase 1 feasibility sentences (these 23 are
  excluded from dev and test because they were seen in Phase 1), model-card examples, or public datasets.
- **No LLM-generated evaluation text.** One candidate model was trained on LLM-generated text, so LLM-written items could favour it;
  LLM text is also stylised for Roman and code-mixed Indic language.
- Authoring and labelling are **separated**: the author writes from scenarios with a coverage checklist, not from label targets, and does
  not label the same items in the same session (section 8). If one person must do both, the separation is in time (labelling after a delay,
  in shuffled order) and the limitation is stated.
- **Families:** about half of the items are written in **families** (one situation expressed in several strata or variants: Devanagari and Roman
  forms, code-mixed form, with/without emoji, negated form). Families enable invariance checks and are kept together in one split (section 11).
  The other half are independent items, to avoid an artificially parallel dataset.

**6.2 Publicly available labelled datasets (optional external anchors; never mixed into the authored test set).** They give an
independent check in conditions close to published benchmarks and allow comparison with model cards. Text is **not copied into project
files** unless the licence permits and attribution is recorded; the preferred form is a reference (dataset name, version and item ids).

| Dataset | Source | Language | Task / labels | Size | Licence (from its card) | Code-mixing | Resembles WhatsApp chat? | Limitations |
|---|---|---|---|---|---|---|---|---|
| GoEmotions (google-research-datasets/go_emotions) | Hugging Face | English | Emotion: 27 emotions plus neutral, multi-label | 10K to 100K rows (size class from the card metadata) | Apache-2.0 | No | Partly (short Reddit comments) | English only; Reddit domain; different label set from all three candidates |
| emotion (dair-ai/emotion) | Hugging Face | English | Emotion: 6 classes | 10K to 100K rows | `other` on the card: **UNVERIFIED** for our use | No | Partly (tweets) | Licence unclear; English; label noise known |
| MahaEmotions (l3cube-pune/MahaEmotions) | Hugging Face | Marathi (Devanagari) | Emotion: 11 labels (12,000 train synthetic labels; 1,500 validation and 1,500 test manually labelled) | 15,000 | CC-BY-4.0 (dataset card); source tweets from MahaSent, **terms UNVERIFIED** | No | Partly (tweets) | Model B was trained on its train split: its test split is **in-distribution for B**, so B results there are not an independent generalisation check |
| IndicSentiment (ai4bharat/IndicSentiment) | Hugging Face | Hindi, Marathi and eight other Indic languages (Devanagari and other scripts) | Sentiment: positive, negative, neutral | size not stated on the card | **UNVERIFIED** (none on the card) | No | No (product reviews translated into Indic languages) | Translated reviews; not conversational; Devanagari only |
| tweet_sentiment_multilingual (cardiffnlp) | Hugging Face | English, Arabic, French, German, Hindi, Italian, Portuguese, Spanish | Sentiment: 3 classes | 10K to 100K rows | **UNVERIFIED** (none on the card) | No | Partly (tweets) | No Marathi; Hindi in Devanagari; overlaps the XLM-T model's own data |
| Code-mixed sentiment (md-nishat-008/Code-Mixed-Sentiment-Analysis-Dataset) | Hugging Face | Code-mixed (language pairs not verified in this phase) | Sentiment from product-review ratings | 100,000 base instances | CC-BY-NC-ND-4.0 (no derivatives: not suitable for modification or redistribution) | Yes | No (Amazon review-based) | Review domain; licence restricts use |
| Hindi-English tweets sentiment (Abhishek4896/...) | Hugging Face | Hindi, English | Sentiment | under 1,000 | MIT | Yes | Partly | Tiny; minimal documentation |
| L3Cube-MeSent / MeLID / MahaSent-MD / HingLID | GitHub (`l3cube-pune`) | Marathi-English, Marathi, Hindi-English | Sentiment / language ID | about 12,000 tweets (MeSent, per paper); about 60,000 (MahaSent-MD) | **UNVERIFIED** (repositories declare no licence) | Yes (MeSent, MeLID, HingLID) | Partly (tweets) | Licence unclear; models named in Phase 1 were trained on these, so they are in-distribution for those models |
| SemEval-2018 Task 1, SemEval-2020 Task 9 (Hinglish sentiment) | Shared-task pages | English, Arabic, Spanish (Task 1); Hinglish (Task 9) | Emotion / sentiment | not checked in this phase | **UNVERIFIED** | Task 9 yes | Partly | Availability and licence must be checked |

Policy: an external item is used only if its licence permits; if a licence is unclear it is **UNVERIFIED** and not used. External
results are reported **separately** as "benchmark anchors", labelled with whether the set is in-distribution for the model.
No external dataset contains Roman Hindi or Roman Marathi emotion in the WhatsApp register; none was found in Phase 1 or this phase, which is a
reason the authored set is required.

**6.3 The real chat:** excluded from evaluation. Only an in-memory, salted-hash overlap check (section 12) touches it, and a later,
clearly labelled exploratory application (section 16).

## 7. Dataset size options

Unit: one message (an "item"). Test and dev/calibration sets are separate (section 11). About 10% of items are expected to end in the
contested subset (ambiguous, mixed, uncertain) and leave primary scoring. Approximate precision uses a binomial 95% (Wilson)
interval for an accuracy near 0.7 to 0.8 and treats items as independent (family clustering, handled by family bootstrap, widens it).

| | **Option A: minimum feasible MSc set** | **Option B: stronger set** |
|---|---|---|
| Test items | **400** (8 strata x 50) | **960** (8 strata x 120) |
| Dev/calibration items | 120 (8 x 15) | 240 (8 x 30) |
| Guideline pilot (not evaluated) | about 30 | about 50 |
| **Total authored** | about 550 | about 1,250 |
| Test items per stratum, after about 10% exclusions | about 45 | about 108 |
| Approx. 95% interval half-width for a per-stratum accuracy of 0.7 to 0.8 (50 items / 120 items) | about 0.11 to 0.12 | about 0.07 to 0.08 |
| Approx. half-width for the pooled set (400 / 960) | about 0.04 | about 0.03 |
| Double-annotated share of test | 25% (100 items, stratified, about 12 per stratum) | 100% |

**Approximate sentiment distribution (test, before exclusions).** Positive about 35%, negative about 35%, neutral about 30%
(A: about 140 / 140 / 120; B: about 336 / 336 / 288). Acceptable range: plus or minus 10 points per class; naturalness has priority.

**Approximate emotion distribution (primary emotion, test).** neutral 30%, joy 16%, anger 11%, sadness 11%, surprise 8%, fear 6%,
disgust 4%, other_emotion 14%:

| | neutral | joy | anger | sadness | surprise | fear | disgust | other_emotion | total |
|---|---|---|---|---|---|---|---|---|---|
| Option A (400) | 120 | 64 | 44 | 44 | 32 | 24 | 16 | 56 | 400 |
| Option B (960) | 288 | 154 | 106 | 106 | 77 | 58 | 38 | 133 | 960 |

These are **targets, not quotas**. Per-class F1 is reported only for classes with at least 20 gold items in the pooled set (rule stated
in advance); in Option A disgust (about 16) falls below it and fear (about 24) is borderline, which is one reason Option B is stronger.
Per-stratum emotion macro-F1 is reported with its interval and a low-support note. **No claim of statistical representativeness of real
WhatsApp traffic is made**: the set is a designed stress test of conditions, not a sample of chats.

**Annotation workload (planning estimates, not measurements; assumed about 120 items/hour for sentiment and 80 items/hour for emotion, authoring about 25 to 30 items/hour).**

| Task | Option A | Option B |
|---|---|---|
| Scenario bank, guidelines, glossary, pilot | about 6 h | about 10 h |
| Authoring | about 20 h | about 45 h |
| Dedup and review | about 2 h | about 5 h |
| Annotator 1 (sentiment and emotion) | about 11 h (550 items) | about 25 h (1,200 items) |
| Annotator 2 | about 3 h (about 130 items) | about 25 h (1,200 items) |
| Adjudication | about 1.5 h | about 6 h |
| **Total person-hours** | **about 45 h** | **about 115 h** |

Recommendation: **Option A as the commitment, with Option B as the extension if a second annotator is available for the full test set.**

## 8. Annotation protocol

**A. Who labels.** The researcher (Annotator 1) and, if feasible, one additional annotator (Annotator 2) who reads English, Hindi and
Marathi in both scripts; a third person adjudicates if available, otherwise the procedure in section 9 applies. Annotators are identified
by pseudonymous ids. Annotators are the people who assess **human-perceived** sentiment and emotion; authors' intended labels are not
used as gold.

**B. What annotators see.** The message text, its stratum / declared language form (needed for competence), and the two task definitions.
Family ids and the authors' scenario notes are hidden. Variants of one family are never shown in the same session or adjacent in order.

**C. What annotators do not see.** Any model prediction, probability, confidence or model name; other annotators' labels (until adjudication);
the target distributions; the contents of the real chat.

**D. Labelling order.** **Two independent passes**, in different random orders and on different days where possible: pass 1 is **sentiment**
only; pass 2 is **emotion** only (primary emotion, tags, flags). The separation prevents the sentiment decision from mechanically
determining the emotion decision. After both passes an automatic **consistency check** lists conflicts (for example primary emotion `joy`
with sentiment `Negative`) for **review**, never for automatic change.

**E. Ambiguity.** Flags as in section 2 (`MIXED`, `AMBIGUOUS`, `UNCERTAIN`, `NEEDS_EXPERT`) for sentiment, and `MIXED_EMOTION`, `UNCERTAIN`,
`NEEDS_EXPERT` for emotion. A flag is preferred over a guess. Annotators record the alternative readings in a short note.

**F. Multi-emotion messages.** One primary emotion plus optional tags (section 3.3). If two emotions are equally dominant, `MIXED_EMOTION`.

**G. Sarcasm.** Sentiment: intended polarity with the `SARCASM` tag, or `UNCERTAIN` if intent is not recoverable. Emotion: the underlying emotion
conveyed (often anger, contempt or disgust), tag `sarcasm`; model B's *Sarcasm* class is scored through the tag (native-label analysis), not as a
gold primary label.

**H. Emoji.** Treated as evidence as described in section 2; emoji are kept in the text shown. Emoji-only items are allowed.

**I. Negation.** Judge the meaning after negation; unclear scope is `AMBIGUOUS`. Items testing negation appear in both polarity-flipping and
non-flipping forms.

**J. Code-mixing.** The whole message is judged, not the dominant language; a message is not reduced to its English part.

**K. Romanised language.** Roman Hindi and Roman Marathi are read as those languages. Variable spelling is expected. If a line cannot be read confidently
as a specific language, `NEEDS_EXPERT` (and the item is removed if no expert can resolve it).

**L. Culturally specific expressions.** A written **glossary** (prepared before labelling and versioned) records slang, discourse markers and
idioms with their intended polarity/emotion and the regional note; examples of the kind of entry are acknowledgement words, praise slang, and
expressions whose tone depends on intonation. Expressions not in the glossary and not understood are flagged `NEEDS_EXPERT`; new entries are added
through the adjudication log, never by looking at model output.

**Annotation sheet schema (for the later build phase; not created now).** `item_id`, `family_id`, `split`, `text`, `declared_language`, `stratum`,
`script_class`, `sentiment`, `sentiment_flag`, `emotion_primary`, `emotion_tags`, `emotion_flag`, `annotator_id`, `note`, `timestamp`;
adjudication columns `final_sentiment`, `final_emotion`, `final_flag`, `adjudicator_id`, `rule_cited`. Model outputs are stored in a **separate**
file keyed only by `item_id`; they are never written into the annotation sheet.

## 9. Ambiguity and adjudication protocol

1. After independent annotation, items where the two annotators' labels or flags differ enter **adjudication**.
2. The adjudicator sees the text, the stratum and **both annotators' labels and notes** (not any model output) and either assigns a final label,
   or marks the item `CONTESTED` when a defensible single label does not exist.
3. Every decision cites a guideline rule; new rules or glossary entries are logged with the date, and earlier items affected are re-checked.
4. `CONTESTED`, `MIXED`, `AMBIGUOUS`, `UNCERTAIN` and `MIXED_EMOTION` items leave the primary scoring set and are kept in a **contested subset** with
   their counts reported per stratum.
5. If no third person is available, the two annotators discuss disagreements once, record the reason and apply the rule; this weakens independence and
   is stated as a limitation. If only one annotator exists, see section 10.
6. **Review trigger (not an acceptance threshold):** if more than about one in six items in a stratum are contested, the guidelines for that stratum are
   revisited before any model is run.
7. Gold labels are **frozen and hashed** before any model output is computed.

## 10. Inter-annotator agreement plan

**Is a second annotator realistic?** For an MSc project, yes for a subset, if one fluent English/Hindi/Marathi reader can give about 3 h (Option A);
full double annotation (Option B) needs about 25 h. **A second annotator is recommended.**

**Design (Option A):** Annotator 2 independently labels a **stratified 25% of the test items (about 12 per stratum) and the same proportion of dev**,
both tasks, without seeing Annotator 1's labels.

**Statistics (chosen to fit the design):**
- **Cohen's kappa (unweighted)** between the two annotators for sentiment (3 classes) and for primary emotion (8 labels), because there are two fixed
  annotators and nominal labels. Raw percentage agreement is reported beside it because kappa can be misleading with skewed classes.
- **Per-class agreement** (annotator 2 scored against annotator 1 as reference, noting the asymmetry) to show which classes are contested.
- **Bootstrap 95% intervals.** With about 100 double-annotated items the kappa interval is about plus or minus 0.10, which is reported rather than hidden.
- **Per-stratum kappa only in Option B** (about 120 double-annotated items per stratum); in Option A, stratum-level agreement is descriptive (about 12 items).
- Krippendorff's alpha is **not** planned, because the design has two annotators with no missing data; it would be added only if a third annotator labels overlapping items.
- Agreement is also computed **including** flagged items (flags as a category) to show how often humans disagree that an item is labellable.

**Human ceiling.** The human-human macro-F1 agreement on the double-annotated subset is reported and is used in the acceptance criteria as a realistic upper
bound for model performance.

**If only one annotator is feasible (limitation):** report that there is no inter-annotator agreement; estimate **intra-annotator consistency** by re-labelling
20% of the items after at least one week (kappa between the two passes); have a reviewer check all flagged, conflicting and randomly chosen items; and treat
results as **exploratory**: the acceptance criteria below cannot be met without a second annotator on at least the subset.

## 11. Data split

| Set | Purpose | Use rules |
|---|---|---|
| **Test (evaluation)** | Final performance estimates | Frozen and hashed before any model runs; **never used for tuning, thresholding, calibration, mapping choices or model selection**; each model/configuration run on it once for the final report |
| **Dev / calibration** | Calibration, abstention threshold, multi-label decision rule, sensitivity choices | Separate from test at **family level**; used for fitting only; never reported as final performance |
| Guideline pilot | Train annotators and refine guidelines | Excluded from dev and test |
| External anchors (optional) | Independent benchmark checks | Kept apart; reported separately |

- Split by **family**, not by item: every variant of one family (Devanagari/Roman forms, code-mixed form, emoji or negated variants, near-paraphrases)
  sits in the same split; otherwise a transliteration pair across dev and test would leak.
- Stratified assignment so every stratum appears in both dev and test.
- If calibration needs more data than the dev set offers, a **cross-validation within dev** is used; the test set is still untouched.
- Any fix after seeing test results (for example a bug) requires a documented re-run and is reported as such; the set is not edited to help a model.

## 12. Duplicate and leakage handling

1. **Exact duplicates:** after Unicode NFKC normalisation, case-folding, whitespace collapse and emoji-preserving punctuation trimming, identical items are merged
   (kept once; repeated short acknowledgements in different contexts are also kept once).
2. **Near-duplicates:** normalised character 3-gram Jaccard similarity of at least 0.8 within a script (threshold declared in advance) is flagged and
   manually reviewed; retained pairs share a `family_id` and therefore a split.
3. **Cross-script pairs and variants:** share a `family_id`.
4. **Source contamination:** items are compared with the model cards' example sentences, the Phase 1 feasibility sentences, and any external anchor set; matches
   are removed. Because authored text is new, contamination of a model's pretraining data cannot be fully excluded and is stated as a limitation.
5. **Real-chat overlap (privacy-preserving):** salted hashes of normalised real-chat messages are computed **in memory** and compared with hashes of evaluation
   items; any match removes the item; no real text is written anywhere.
6. **Labels versus models:** no model output is ever consulted to write, select, relabel or drop an item.
7. **Bootstrap and intervals** resample **families**, not items, so dependence is respected.
8. **In-distribution warning:** external test splits from the training family of a model (for example MahaEmotions test for model B) are labelled as in-distribution
   for that model and not used as evidence of generalisation.

## 13. Metrics

Sentiment and emotion are evaluated **separately**, per model, never pooled into one figure.

**Sentiment (3 classes), on the primary scoring set:** accuracy; macro precision, macro recall and **macro-F1**; per-class precision/recall/F1;
confusion matrix; **polarity-flip rate** (gold positive predicted negative or the reverse, as a share of polar items), because a flip is worse than a neutral confusion.

**Emotion (core labels the model can produce), on the primary scoring set:** accuracy; **macro-F1**; per-class F1 (when at least 20 gold items);
confusion matrix; **neutral-collapse rate** (gold non-neutral predicted neutral, the silent failure seen in Phase 1); for the multi-label model both *top-label* and
*gold-in-predicted-set* variants; native-label analysis through tags (descriptive).

**Why macro-F1 is essential:** classes are imbalanced by design and in nature (neutral is large; disgust and fear are small). Accuracy rewards predicting the large
class; macro-F1 averages per-class F1 with equal weight, so a model that never predicts a small class pays for it. Micro or weighted averages are not primary. Classes with zero gold
support are excluded from a macro average and named.

**Breakdowns required (never only an overall figure):**
- per **stratum** (S1 to S8) and per **script class**;
- **Roman text** (S3, S5, S6, S7) versus Devanagari (S2, S4) versus mixed-script (S8);
- **code-mixed** (S6, S7, S8) versus monolingual;
- by **cross-cutting tag**: emoji, negation, question/request, sarcasm, short, neutral/informational;
- **language/category coverage**: how many items per stratum survive exclusion and how many were answered, unsupported, low-confidence;
- **abstention rate** per stratum when the model or the pipeline abstains;
- **cross-script consistency** on paired family variants (same sentence in Devanagari and Roman): rate of identical predictions (a diagnostic, not accuracy);
- contested subset: counts and descriptive model behaviour.

**Uncertainty:** 95% **family-level bootstrap** intervals for macro-F1 and accuracy; paired bootstrap for differences between models and from baselines.
**Baselines** reported with every table: majority-class and "always neutral".

## 14. Confidence, calibration and abstention

The Phase 1 test showed models returning 0.99 to 1.0 on wrong outputs and another giving low scores on uncertain text. This protocol therefore never
treats a raw probability as reliability.

**Quantities.** `p_raw` (softmax maximum for single-label models; for the multi-label model, the top sigmoid and the set above 0.5), `p_cal` (calibrated), and
the outcome status.

**Procedure (all fitted on the dev set only):**
1. **Raw analysis on dev:** reliability diagram, expected calibration error (adaptive bins, because of small n) and Brier score per model.
2. **Informativeness check:** the area under the ROC curve of the score for predicting correctness. If its lower 95% bound is not above 0.5 (chance), the score is declared
   **uninformative** for that model/stratum, and the model cannot use score-based abstention there.
3. **Calibration:** temperature scaling (one parameter, suitable for a few hundred items), per model, and per script group only if the dev data allows; otherwise pooled.
   Saturated models that calibration cannot separate are documented, not hidden.
4. **Abstention threshold `tau`:** chosen on dev by a rule stated **in advance**: the smallest `tau` that cuts the error rate among answered items by at least one third relative
   to no abstention while keeping coverage of at least 50% of in-scope items. Reason: it forces abstention to buy a real gain without discarding most of the data, which suits an exploratory
   MSc evaluation; both numbers are conventions to be confirmed by the supervisor.
5. **Optional agreement signal:** where two models overlap in scope, disagreement is evaluated on dev as an additional low-reliability flag.
6. **One-time application on test:** the frozen `p_cal`, `tau` and rules are applied to the test set; nothing is refitted.

**Output statuses** (per message, per task):

| Status | Meaning |
|---|---|
| `supported` | In scope of the support matrix, model ran, calibrated score at or above `tau`; the label is returned |
| `low_confidence` | In scope, model ran, calibrated score below `tau` (or disagreement flag); **no label is returned** |
| `unsupported` | No candidate claims support for the task and language form, so no model is run |
| `unverified` | A candidate exists but has not met the acceptance criteria for this stratum, or the language cannot be established (for example Latin-script text of unknown language); **no label is returned** |

Unsupported and unverified inputs are **never forced into an emotion label** and are never counted as `neutral`. Reports give the four outcomes as counts with denominators, and
compute accuracy only over `supported` items, alongside coverage.

## 15. Language coverage matrix

Status today is **before** any evaluation. Definitions: **SUPPORTED** = evaluated against this protocol and the acceptance criteria met for the stratum; **LIMITED** = evaluated,
partly met, usable only with prominent caveats; **UNVERIFIED** = a candidate exists but no adequate evidence for our use (a multilingual model alone is not evidence);
**UNSUPPORTED** = no candidate claims support.

| Language / form | Sentiment: candidates and evidence | Emotion: candidates and evidence | Status today (sentiment / emotion) | Decision after evaluation |
|---|---|---|---|---|
| English | Several models; published evidence in other domains; plausible on invented examples (not validation) | tabularisai (paper: zero-shot human-annotated English data) | UNVERIFIED / UNVERIFIED | Per S1 criteria |
| Hindi, Devanagari | XLM-T (Hindi among fine-tuning languages; licence UNVERIFIED) | tabularisai (Hindi listed; no human-labelled Hindi validation); small Hindi ALBERT model | UNVERIFIED / UNVERIFIED | Per S2 criteria |
| Hindi, Roman | Hinglish-twitter (states Roman Hindi; emoji-driven; evaluation only with emoji) | none documents it; tabularisai inconsistent in Phase 1 | UNVERIFIED / UNVERIFIED | Per S3; expected weakest |
| Marathi, Devanagari | MahaSent-MD (manually labelled benchmark; licence of data UNVERIFIED) | MahaEmotions-BERT (manual test labels, synthetic train labels; tabularisai lists no Marathi) | UNVERIFIED / UNVERIFIED | Per S4 criteria |
| Marathi, Roman | MeSent-RoBERTa family (code-mixed Marathi-English; Roman not shown for pure Marathi) | none | UNVERIFIED / **UNSUPPORTED** | Per S5; emotion stays UNSUPPORTED unless a candidate appears |
| Hindi-English | Hinglish-twitter; XLM-T (unverified) | none documented | UNVERIFIED / **UNSUPPORTED** | Per S6 (sentiment only) |
| Marathi-English | MeSent-RoBERTa (about 12,000 manually annotated code-mixed tweets, per paper) | none found | UNVERIFIED / **UNSUPPORTED** | Per S7 (sentiment only) |
| Mixed-script (Devanagari + Latin) | MeSent (Roman + Devanagari family), XLM-T | none | UNVERIFIED / UNSUPPORTED | Per S8 |

Emotion for Hindi-English and Marathi-English is **UNSUPPORTED today** not because the models are multilingual or not, but because **no candidate with a documented task,
licence and evaluation was found**. If a candidate appears, the same protocol applies.

## 16. Real-chat application protocol

The 24-message chat is treated separately and **only after** the evaluation and acceptance decisions are made.

1. It is never part of dev or test data.
2. The chosen approach (only for strata that met the criteria) may be applied to the chat **in memory**; no message-level output is written.
3. Outcomes are reported as **counts with denominators** by status (`supported`, `low_confidence`, `unsupported`, `unverified`) and, for `supported` items only, label counts.
   Both the 24 messages and the 18 unique texts are shown; forwarded messages are reported separately (consistent with earlier decisions).
4. Because Script Mix cannot establish language for Latin-script text, **most of the 16 Latin-only messages are expected to be `unverified`**; Devanagari-containing messages are
   scored only if the matching stratum was accepted.
5. Every result carries the banner **EXPLORATORY APPLICATION** and, beside it, the **evaluated performance and interval of the relevant stratum**, so a reader can see how
   much the number can be trusted.
6. The difference is stated explicitly: **evaluated model performance** (measured on the authored test set against human labels) versus **exploratory application**
   (model outputs on 24 unlabelled messages). No statement such as "40% of the chat is happy" is made: counts only, small numbers, no validated ground truth for the chat, one dominant sender,
   announcement-heavy text.
7. The earlier decision that sentiment is excluded for the current chat stands unless the project owner approves reversing it after the acceptance review.

## 17. Privacy

- The evaluation dataset is **synthetic or appropriately licensed public data**: no real sender names, phone numbers, invitation links, private messages or identifying information.
  Invented names are generic and are not taken from the real chat; links use reserved example domains; numbers are not used.
- No raw private chat text in any evaluation file; the real chat is only compared through **in-memory salted hashes** (section 12).
- External datasets: licence recorded; text not copied into the repository unless the licence permits and attribution is recorded; **UNVERIFIED** licences are not used.
- Annotators see only synthetic (or licensed) text and are referred to by pseudonymous ids; annotator labels are stored separately from any personal information.
- Model predictions are stored separately from gold labels, keyed by `item_id`, and are never shown to annotators.
- All inference is **local and offline**; no text is sent to a hosted service; model files and caches stay outside the repository.
- Authored items may later be added to the repository under a stated licence chosen by the author, after a review that they contain nothing identifying.

## 18. Limitations

- **Synthetic, authored text** is not real WhatsApp text: it may be cleaner, more stereotyped, and shaped by the authors' style. Results are a designed stress test and **do not represent real chat traffic**.
- **Small sample:** per-stratum intervals are wide in Option A (about plus or minus 0.11 to 0.12 for accuracy); per-class emotion results are sparse (disgust, fear).
- **Annotator subjectivity and fluency:** emotion is culturally situated and labels are contested; one or two annotators from one region cannot cover dialects and registers. Agreement is measured on a subset only in Option A.
- **Label-set choices:** a coarse 3-class sentiment and an 8-label emotion core exclude distinctions the models make (and models' own label semantics differ). Mapping caveats (joy/Happiness, anger/disgust) remain.
- **Model-side contamination** of pretraining data cannot be excluded; in-distribution benchmark splits are flagged.
- **Romanised spelling variation** makes some items inherently ambiguous.
- **Calibration data is small** (120 or 240 items); thresholds are noisy and are reported with that caveat.
- **Dependencies, licences and hardware** (non-commercial licence of one model, unverified licences of others, local CPU only) constrain what can be shipped.
- The protocol tests **approaches**; it does not validate any individual future chat.

## 19. Acceptance criteria for production implementation

Emotion and sentiment may enter the production dashboard **only for strata and tasks that individually meet the criteria below**, and only with the stated caveats. There is **no single overall
pass**: a good overall score cannot hide a failing stratum. Numbers are **conventions for an exploratory MSc project**, justified below and open to supervisor adjustment; they are not universal
standards and were fixed before any label or model output exists.

**Gate 1: ground truth is trustworthy enough.**
- Protocol approved and pre-registered; labels frozen and hashed before model outputs.
- **Inter-annotator agreement** on the double-annotated subset: sentiment Cohen's kappa of at least **0.60**, emotion (core labels) at least **0.50**. Reason: 0.61 to 0.80 is the conventional
  "substantial agreement" band for kappa and 0.41 to 0.60 "moderate"; emotion is inherently harder to agree on, so the bar is one band lower. Below these, the labels are too noisy to certify
  a model and the guidelines are revised first.
- Contested items reported per stratum; a stratum in which more than **20%** of items are contested cannot be SUPPORTED (Reason: a fifth or more of the data having no defensible label makes
  the remaining score unrepresentative).
- At least **40 primary-scoring items** in every stratum for which support is claimed (Reason: below about 40 items the 95% interval on accuracy is wider than about plus or minus 0.14).

**Gate 2: per-stratum model performance (family-bootstrap 95% intervals).**

| Level | Sentiment (macro-F1) | Emotion (macro-F1 over the model's evaluable core labels) |
|---|---|---|
| **SUPPORTED** | point estimate at least **0.70**, lower bound at least **0.60**, and point estimate at least **0.8 x the human-human macro-F1 agreement** | point at least **0.55**, lower bound at least **0.45**, and at least **0.8 x human-human agreement** |
| **LIMITED** | point at least 0.50 and lower bound above both baselines | point at least 0.40 and lower bound above both baselines |
| **UNVERIFIED / UNSUPPORTED** | anything below LIMITED, or insufficient data | same |

Reasons: sentiment has three classes (chance macro-F1 about 0.33), and a strong multilingual model is reported at about 0.69 on its own multilingual tweet test set (the XLM-T family card), so 0.70 on
a controlled synthetic conversational set is a moderate bar; emotion has about eight classes (chance about 0.13), so 0.55 is roughly four times chance, a moderate bar that is a convention here and not a literature-derived figure; the **relative** condition (0.8 of the human ceiling) stops the bar from exceeding what humans themselves achieve; the **lower-bound** conditions stop a lucky point estimate
from passing. Additionally, every level requires that the model **beats both trivial baselines** (majority class and always-neutral) with a paired bootstrap interval that excludes zero.

**Gate 3: no hidden failure mode.**
- **Polarity-flip rate** (sentiment) at most **10%** of polar items in the stratum, and **neutral-collapse rate** (emotion) at most **25%** of non-neutral items (Reason: with at most one in ten
  polar messages reversed, direction-of-tone counts stay directionally informative; a model that calls more than a quarter of emotive messages neutral systematically hides affect, the failure seen in
  Phase 1).
- **Roman-script strata** (S3, S5, S6, S7) are decided **separately**; a Devanagari or English pass does not transfer. Documented Roman limitations are displayed.
- Sarcasm, negation and emoji breakdowns are reported; failures there are displayed as limitations.

**Gate 4: abstention behaviour.**
- The score is **informative** (AUROC for correctness with lower bound above 0.5), or the model does not use score-based abstention.
- On `supported` answers the stratum still meets Gate 2 (selective performance), and **coverage is at least 50%** of in-scope items for SUPPORTED (otherwise LIMITED).
- `unsupported` and `unverified` inputs are never forced to a label; their share is shown.

**Gate 5: reproducibility.** Evaluation data frozen with SHA-256 hashes; dependency and model versions pinned and recorded; deterministic CPU inference (two full runs give identical
metrics); the evaluation script and protocol version are stored; results regenerate from a clean environment.

**Gate 6: privacy and licences.** Dataset privacy rules of section 17 met and tested; **licence permissions confirmed in writing** for every model and dataset used (including the non-commercial
licence of one candidate and every UNVERIFIED item); attribution recorded; no text leaves the machine at run time.

**Gate 7: engineering.** Dependencies approved by the project owner (none installed in the project so far), locally runnable offline on the target machine, resource use measured, tests and
leak tests written; dashboard integration designed and approved separately.

**Gate 8: honest presentation.** The interface labels validated strata, their evaluated performance, and "EXPLORATORY APPLICATION" for the project chat; no validated-sounding percentages; unsupported and
low-confidence shown as outcomes.

**If the criteria are not met:** the capability stays exploratory or excluded, which is itself a documented, defensible result for the project.

## Decisions for the project owner (before the build phase)

1. Option A (recommended commitment) or Option B.
2. Who is Annotator 2 (and any adjudicator), and who reads both Hindi and Marathi in Devanagari and Roman script.
3. Whether the author and Annotator 1 are the same person (if so, the time separation in section 6.1 applies and is reported).
4. Which external anchors (if any) to use, after licence confirmation (several are UNVERIFIED).
5. Confirmation of the conventions in section 14 (abstention rule) and section 19 (thresholds).
6. Contact or confirmation about the non-commercial model licence and the unverified licences.
7. `docs/project_plan.md` does not yet record the Phase 1 and Phase 2 documents; it was not edited in this phase.
