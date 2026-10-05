# Multilingual and Code-Mixed Emotion & Sentiment: Research, Feasibility and Design (Phase 1)

> **Status note (2026-10-05).** This is a research/feasibility note for a feature that is **intentionally not implemented** (sentiment, emotion). Nothing from it is in the pipeline, the dashboard, the results or the requirements.

> **Phase 1 only.** Research, resource verification, a controlled qualitative feasibility test, and design.
> **Nothing was implemented in the project.** No existing source, test, dashboard, requirements, result,
> data or other document was modified; this is the only project file created. The feasibility test ran in a
> scratch area outside the project (models, libraries and outputs there are not part of the repository).
>
> Verification date: 2026-10-01. Model, dataset and licence facts below were read from the actual model/dataset
> cards (README and configuration files) and repository metadata, not from search-result snippets.
>
> **The feasibility results are a qualitative test on 23 invented sentences. They are NOT model validation and
> NOT accuracy measurements.** No accuracy is claimed for any model on any WhatsApp data. No real-chat text
> was sent to any model in this phase.

## 1. Problem definition

Design a **general** capability, not a Marathi-only feature and not a model fitted to the current chat, that can
attach **sentiment** and **emotion** information to WhatsApp messages written in English, Hindi, Marathi and other
Indian languages, in Devanagari or Latin script (romanised), code-mixed (for example Hindi-English or
Marathi-English), with emoji, short lines and slang, and that can say **"unsupported / low confidence /
unverified"** instead of forcing a prediction when language or model coverage is inadequate.

Existing context that constrains the design:
- The current chat has 24 real text messages (18 unique), 16 Latin-only and 7 mixed English/Devanagari, announcement-style,
  one dominant sender, no labels. Sentiment was excluded for this dataset in `docs/sentiment_design.md` for
  exactly these reasons; Phase 1 does not reverse that decision for the current chat.
- The Script Mix feature (implemented) gives a deterministic script class and alternation count per message,
  and explicitly does not identify language.
- Privacy rules: no raw text, names, numbers or links in outputs; local processing only; display-layer filter.
- Baseline: 155 tests passing before this phase (unchanged after it).

## 2. Sentiment and emotion are separate tasks

| | Sentiment | Emotion |
|---|---|---|
| Question | Is the evaluation positive, negative or neutral? | Which affective state is expressed (anger, joy, fear, ...)? |
| Label set | 3 classes (positive, negative, neutral) | Model-specific, 7 to 11 classes here, **different per model** |
| Structure | Single label | Single label (most models) or multi-label (one model) |
| Relationship | "Frustration" and "sadness" are both negative; "surprise" can be either | Emotion is finer and culturally situated |

They are kept separate in the design. **No universal emotion taxonomy is invented.** Each model's native labels
are preserved and reported with the model's name. A normalisation layer is considered only if a mapping is
semantically defensible (see section 11); it is not defensible between the models found.

## 3. Language and code-mix requirements (evidence-gated, not "every language")

Status vocabulary: **SUPPORTED-CLAIMED** (a model card states support; not validated on our data),
**PLAUSIBLE-OBSERVED** (behaved plausibly on our invented examples; no evidence beyond that), **UNVERIFIED**
(no evidence either way; includes anything inferred only from a model being "multilingual").

### SUPPORTED_LANGUAGES (target list, with evidence status per task)

| Language / script | Sentiment | Emotion |
|---|---|---|
| English (Latin) | SUPPORTED-CLAIMED (several models) | SUPPORTED-CLAIMED (tabularisai, per its paper: zero-shot checks on human-annotated English data) |
| Hindi, Devanagari | SUPPORTED-CLAIMED (XLM-T lists Hindi among its 8 fine-tuning languages; licence UNVERIFIED) | SUPPORTED-CLAIMED by model card (tabularisai lists Hindi; its paper reports no human-labelled Hindi validation; a small Hindi-only ALBERT model has a tiny test set) |
| Marathi, Devanagari | SUPPORTED-CLAIMED (MahaSent-MD, manual labels) | SUPPORTED-CLAIMED (MahaEmotions-BERT; training labels synthetic, test labels manual); **not** among tabularisai's listed languages |
| Bengali, Tamil, Urdu, Punjabi | UNVERIFIED | Listed by tabularisai; UNVERIFIED for our use |
| Gujarati, Telugu, Kannada, Malayalam, Odia, Assamese and others | UNVERIFIED (not investigated) | UNVERIFIED |

### SUPPORTED_CODE_MIX_TYPES

| Code-mix type | Sentiment | Emotion |
|---|---|---|
| Marathi-English (Roman and Devanagari) | SUPPORTED-CLAIMED by one model (MeSent-RoBERTa, trained on about 12,000 manually annotated code-mixed tweets per the paper) | **None found** |
| Hindi-English (Hinglish, Roman) | Community models only, weak documentation (for example one with an emoji-dominated behaviour noted in its own card) | **None with a documented task, licence and evaluation** |
| Hindi-English in mixed scripts | UNVERIFIED | UNVERIFIED |

### UNSUPPORTED / UNVERIFIED_CASES

- **Romanised Hindi and romanised Marathi** for emotion: UNVERIFIED for every model examined. No model card provides
  evidence. Observed behaviour on invented examples was inconsistent (section 7).
- **Romanised text in general** for any model other than MeSent (whose card covers code-mixed Marathi-English) is UNVERIFIED.
- Hindi versus Marathi distinction inside Devanagari and inside Latin script: no validated identifier (section 9).
- Marathi emotion via tabularisai: Marathi is not among its listed languages.
- Any language not listed above, transliterated Indic languages, slang and abbreviations: UNVERIFIED.
- Sarcasm and negation handling: only a Marathi emotion model has a "Sarcasm" class; negation errors were observed (section 7).

The design therefore **must return "unsupported", "low confidence" or "unverified"** for these cases.

## 4. Candidate model comparison

All sizes are parameter counts from the model metadata; download sizes were measured. All inference was on CPU
(4 threads). "Tested" means loaded and run on the 23 invented sentences.

| Model | Task | Languages | Roman support | Code-mix | Native labels | Licence (from card) | Size | Evidence | Major limitations | Tested |
|---|---|---|---|---|---|---|---|---|---|---|
| **A. tabularisai/multilingual-emotion-classification** | Emotion, **multi-label** (sigmoid, threshold 0.5) | 23 listed, incl. Hindi, Bengali, Tamil, Urdu, Punjabi; **not Marathi** | **UNVERIFIED** | **UNVERIFIED** | anger, contempt, disgust, fear, frustration, gratitude, joy, love, neutral, sadness, surprise (11) | **CC-BY-NC-4.0** (non-commercial) | 278 M params; 1.13 GB | Card: F1-micro 0.840, F1-macro 0.839 on an 11,500-row held-out test set; paper: test set appears synthetic; zero-shot on human-annotated GoEmotions (English) and SemEval-2018 (English, Arabic, Spanish) only | Training data synthetic (LLM-generated); no human-labelled Hindi or Marathi validation; no statement on romanised or code-mixed text; card says real-world validation is strongly advised | Yes |
| **B. l3cube-pune/marathi-emotion-detect** (MahaEmotions-BERT) | Emotion, single-label | Marathi (Devanagari) | **UNVERIFIED** | **UNVERIFIED** | Anger/disgust, Excitement, Fear, Happiness, Neutral, Pride, Respect, Sadness, Sarcasm, Surprise (**10 in the model config**) | CC-BY-4.0 | 237 M params; 0.96 GB | Card points to paper only (no numbers on the card). Paper abstract: training labels from GPT-4; validation/test manually labelled; BERT models trained on synthetic labels did not surpass GPT-4 | The dataset card lists 11 labels (anger and disgust separate); the model config has 10 (merged): an inconsistency to note. Built on MahaSent (Twitter). Domain is tweets | Yes |
| **C. l3cube-pune/me-bert-mixed** | **Masked language model (fill-mask). NOT a classifier** | Marathi-English | Card: trained on Roman + Devanagari text | Yes (pretraining) | None (no classification head) | CC-BY-4.0 | about 178 M params (mBERT-based); 0.72 GB | Paper: MeCorpus of 10 M code-mixed sentences; downstream benchmarks (sentiment, hate, language ID) are separate models | Cannot output sentiment or emotion by itself; useful only as an encoder to fine-tune (needs labelled data) | Yes (fill-mask only) |
| D1. l3cube-pune/me-sent-roberta | Sentiment | Marathi-English code-mixed | Card for family: Roman + Devanagari | Yes | Neutral, Positive, Negative | CC-BY-4.0 | 278 M; 1.14 GB | Paper: MeSent about 12,000 manually annotated code-mixed tweets; no numbers on the card | Dataset licence UNVERIFIED (repository has none); Twitter domain | Yes |
| D2. cardiffnlp/twitter-xlm-roberta-base-sentiment (XLM-T) | Sentiment | Fine-tuned on 8 languages (Ar, En, Fr, De, Hi, It, Es, Pt); "can be used for more" | **UNVERIFIED** | **UNVERIFIED** | negative, neutral, positive | **UNVERIFIED** (none on the card or HF metadata; the code repository is Apache-2.0, which is not the weights' licence) | 278 M; 1.12 GB | Card does not give numbers; sibling multilingual model card reports F1 about 0.69 on its tweet test set | Licence unclear; tweets | Yes |
| D3. l3cube-pune/marathi-sentiment-md (MahaSent-MD) | Sentiment | Marathi (Devanagari) | **UNVERIFIED** | **UNVERIFIED** | Negative, Neutral, Positive | CC-BY-4.0 | 237 M; 0.96 GB | Paper: about 60,000 manually tagged samples, four domains; best accuracy reported for the MahaBERT model (numbers not on the card) | Dataset licence UNVERIFIED (repository has none) | Yes |
| D4. pascalrai/hinglish-twitter-roberta-base-sentiment | Sentiment | Hinglish (Roman Hindi-English) with emoji | Yes (stated target) | Yes (stated target) | negative, neutral, positive | MIT | 124 M; 0.50 GB | Card: f1 0.74 on unseen data from its own dataset (converted to Hinglish; method not stated); "no evaluation done for text without emojis"; emoji dominate its decisions | Trained on a dataset converted to Hinglish; emoji-driven | Yes |
| D5. vashuag/HindiEmotion | Emotion | Hindi (Devanagari) | No | No | anger, disgust, fear, joy, neutral, sadness, surprise | MIT | 33 M; 0.16 GB | Card: accuracy 0.81 on a test set with only 1 to 26 examples per class | Tiny evaluation; Hindi Devanagari only | Yes |
| D6. l3cube-pune/me-lid-roberta | **Token-level language ID** | Marathi / English / Other | Yes (code-mixed) | Yes | Marathi, English, Other | CC-BY-4.0 | 124 M; 0.50 GB | Family paper; no numbers on the card | **No Hindi class** (Hindi is forced into other classes); dataset licence UNVERIFIED | Yes |
| D7. l3cube-pune/hing-bert-lid | Token-level language ID | English / Hindi only | Yes | Yes | EN, HI | CC-BY-4.0 | 108 M; 0.44 GB | Family paper; no numbers on the card | Binary; no Marathi or Other class; dataset licence UNVERIFIED | Yes |
| D8. Gek524/hinglish-emotion-xlmr (and similar community models) | Emotion (4 labels: anger, joy, sadness, trust) | Hinglish (claimed by name) | not documented | not documented | as listed | **UNVERIFIED** (auto-generated empty card) | 278 M | **None** | No documentation, licence or evaluation | **No** (not suitable to test) |

**Search findings.** Searching for current Hinglish and Hindi-English emotion models found only community uploads with
empty or auto-generated cards, no licence and no evaluation. For Marathi-English emotion, **no** emotion model or
dataset was found; MeSent is sentiment only. Multilingual emotion models exist (tabularisai; several GoEmotions
re-implementations) but none documents Roman-script Indic text. Sentiment and emotion were never assumed to be interchangeable:
MeBERT-Mixed is not a classifier, and a sentiment model was not treated as an emotion model.

## 5. Candidate dataset comparison (for future evaluation and training)

| Dataset | Content | Labels | Licence (from its card/repository) | Use here |
|---|---|---|---|---|
| L3Cube-MahaEmotions | 15,000 Marathi sentences; 12,000 train (GPT-4 annotated), 1,500 validation and 1,500 test (manual) | 11 emotions (Happiness, Sadness, Respect, Anger, Fear, Surprise, Disgust, Excitement, Pride, Sarcasm, Neutral) | CC-BY-4.0 (dataset card); built on MahaSent (Twitter), whose terms are UNVERIFIED | Possible **external test** for Marathi Devanagari emotion; not WhatsApp |
| L3Cube-MahaSent-MD | About 60,000 manually tagged Marathi sentences, 4 domains | Positive, negative, neutral | UNVERIFIED (GitHub repository declares no licence) | External test for Marathi sentiment |
| L3Cube-MeSent / MeLID / MeHate | About 12,000 manually annotated Marathi-English code-mixed tweets each | Sentiment / language ID / hate | UNVERIFIED (repository declares no licence) | External test for code-mixed Marathi-English sentiment and language ID |
| GoEmotions and SemEval-2018 (English and others) | Human-annotated English (and Arabic, Spanish) | Multi-label emotions | Not checked in this phase | English emotion checks |
| Hindi GoEmotions translation (HF community) | Translated (method not stated) | Emotions | `unknown` | Not suitable as validation (translated; not Roman; licence `unknown`) |
| Hinglish sentiment datasets (several on the Hub) | Tweets/reviews | Sentiment | Mixed (for example CC-BY-4.0, MIT, CC-BY-NC-ND-4.0) | Candidates for Hinglish sentiment checks; each licence must be read |
| **WhatsApp-style in-domain set** | Does not exist | Needs annotation | n/a | **Required** (section 15) |

## 6. Licence verification

Recorded from the actual cards and repositories. Where a licence is not stated on the card, it is marked UNVERIFIED and
no use is assumed to be permitted. Model and dataset licences are kept separate.

| Item | Licence on the card / repository | Notes |
|---|---|---|
| tabularisai model | **CC-BY-NC-4.0** | Non-commercial only. Base model XLM-R is MIT. Training data synthetic (LLM-generated); the dataset is not published on the card. An academic, non-commercial MSc project may be compatible, but **this must be confirmed**, and a public or commercial deployment is excluded |
| MahaEmotions-BERT | CC-BY-4.0 | Attribution required. Base MahaBERT (marathi-bert-v2) CC-BY-4.0 |
| MahaEmotions dataset | CC-BY-4.0 (dataset card) | Source sentences come from MahaSent (Twitter); platform terms UNVERIFIED. Training labels were produced by GPT-4: provider terms on model-generated labels UNVERIFIED |
| MeBERT-Mixed, MeSent-RoBERTa, MeLID-RoBERTa, HingBERT-LID, MahaSent-MD (models) | CC-BY-4.0 | Attribution required |
| MeCorpus, MeSent, MeLID, MeHate, HingLID, MahaSent-MD (datasets) | **UNVERIFIED** | Hosted in GitHub repositories (`l3cube-pune/MarathiNLP`, `l3cube-pune/code-mixed-nlp`) that declare no licence; the paper says "publicly released", which is not a licence |
| XLM-T sentiment model (cardiffnlp/twitter-xlm-roberta-base-sentiment) | **UNVERIFIED** | No licence in the HF metadata or card. The code repository (xlm-t) is Apache-2.0 and the tweetnlp library is MIT, but neither is stated to cover the weights. Base XLM-R is MIT. Training data licence UNVERIFIED |
| Hinglish-twitter sentiment model | MIT (card) | Dataset was converted to Hinglish from a Hub dataset (method not stated); its licence UNVERIFIED |
| HindiEmotion | MIT (card) | Dataset not stated |
| Community Hinglish emotion models (for example Gek524) | **UNVERIFIED** | Empty card |

## 7. Qualitative feasibility findings (not validation)

**Method.** 23 invented sentences (English 3, Hindi Devanagari 3, Roman Hindi 3, Marathi Devanagari 3, Roman Marathi 3,
Hindi-English 2, Marathi-English 2, emoji 2, neutral 2). Each locally runnable model was loaded and run on the same
sentences in the same way. Nothing was corrected, filtered or re-run to improve results; the one loading adjustment
per model is listed in the appendix. "As intended" means only that the output matches what the sentence
was written to express in the author's reading; it is not an accuracy figure and the sample cannot support one.

**Top label (probability) per example:**

| # | Category | Example | A tabularisai (emotion) | B MahaEmotions (emotion) | HindiEmotion (emotion) | XLM-T (sent.) | MahaSent-MD (sent.) | MeSent (sent.) | Hinglish-tw (sent.) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | english | I am really happy today | joy 0.972 | Happiness 0.749 | neutral 0.811 | positive 0.909 | Positive 0.997 | Positive 1.0 | positive 0.975 |
| 2 | english | This is so frustrating | frustration 0.958 | Sadness 0.641 | neutral 0.984 | negative 0.941 | Negative 0.994 | Negative 1.0 | negative 0.98 |
| 3 | english | Okay, I understand | neutral 0.957 | Neutral 0.91 | neutral 0.88 | neutral 0.541 | Neutral 0.936 | Neutral 1.0 | neutral 0.567 |
| 4 | hindi_devanagari | आज बहुत अच्छा लग रहा है | joy 0.934 | Happiness 0.717 | joy 0.691 | positive 0.852 | Positive 0.997 | Positive 1.0 | neutral 0.908 |
| 5 | hindi_devanagari | मुझे बहुत गुस्सा आ रहा है | anger 0.954 | Sadness 0.82 | anger 0.888 | negative 0.905 | Negative 0.992 | Negative 0.997 | neutral 0.943 |
| 6 | hindi_devanagari | ठीक है, समझ गया | neutral 0.987 | Neutral 0.91 | neutral 0.96 | positive 0.48 | Neutral 0.857 | Neutral 1.0 | neutral 0.912 |
| 7 | roman_hindi | Aaj bahut accha lag raha hai | neutral 0.639 | Surprise 0.588 | anger 0.762 | negative 0.556 | Neutral 0.993 | Positive 1.0 | negative 0.711 |
| 8 | roman_hindi | Mujhe bahut gussa aa raha hai | anger 0.953 | Fear 0.844 | anger 0.729 | positive 0.468 | Negative 0.551 | Negative 1.0 | negative 0.986 |
| 9 | roman_hindi | Theek hai samajh gaya | neutral 0.945 | Neutral 0.866 | anger 0.897 | positive 0.413 | Neutral 0.989 | Positive 1.0 | neutral 0.702 |
| 10 | marathi_devanagari | आज खूप छान वाटत आहे | joy 0.977 | Happiness 0.759 | neutral 0.868 | positive 0.854 | Positive 0.997 | Neutral 1.0 | neutral 0.916 |
| 11 | marathi_devanagari | मला खूप राग येतोय | fear 0.975 | Sadness 0.82 | neutral 0.986 | negative 0.768 | Negative 0.994 | Neutral 1.0 | neutral 0.909 |
| 12 | marathi_devanagari | ठीक आहे समजलं | neutral 0.979 | Neutral 0.913 | neutral 0.984 | neutral 0.396 | Positive 0.819 | Neutral 1.0 | neutral 0.906 |
| 13 | roman_marathi | Aaj khup chan vatat aahe | neutral 0.634 | Neutral 0.914 | neutral 0.928 | positive 0.35 | Positive 0.996 | Positive 1.0 | neutral 0.439 |
| 14 | roman_marathi | Mala khup rag yetoy | neutral 0.511 | Neutral 0.911 | neutral 0.883 | negative 0.341 | Neutral 0.996 | Neutral 0.951 | neutral 0.756 |
| 15 | roman_marathi | Thik aahe samajla | neutral 0.762 | Neutral 0.832 | neutral 0.928 | positive 0.403 | Neutral 0.994 | Neutral 1.0 | neutral 0.884 |
| 16 | hindi_english | Aaj ka match was really amazing | neutral 0.888 | Excitement 0.926 | neutral 0.971 | positive 0.863 | Positive 0.997 | Positive 1.0 | positive 0.967 |
| 17 | hindi_english | Mujhe ye bilkul pasand nahi bro | none at 0.5 (top anger 0.221) | Neutral 0.621 | neutral 0.807 | negative 0.536 | Negative 0.994 | Negative 1.0 | positive 0.657 |
| 18 | marathi_english | Aaj match khup mast hota bro | neutral 0.875 | Surprise 0.762 | neutral 0.993 | positive 0.457 | Positive 0.995 | Positive 1.0 | neutral 0.624 |
| 19 | marathi_english | Mala this bilkul avadla nahi | none at 0.5 (top frustration 0.439) | Neutral 0.893 | neutral 0.976 | negative 0.468 | Negative 0.983 | Negative 1.0 | neutral 0.542 |
| 20 | emoji | Great job bro 🔥❤️ | love 0.916 | Happiness 0.385 | neutral 0.973 | positive 0.907 | Positive 0.997 | Positive 1.0 | positive 0.982 |
| 21 | emoji | Yaar this is so sad 😢 | sadness 0.998 | Sadness 0.827 | neutral 0.668 | negative 0.939 | Negative 0.994 | Negative 1.0 | negative 0.958 |
| 22 | neutral | Meeting is at 5 pm | neutral 0.996 | Neutral 0.912 | neutral 0.983 | neutral 0.822 | Neutral 0.995 | Neutral 1.0 | neutral 0.965 |
| 23 | neutral | Please send the link | neutral 0.99 | Neutral 0.9 | neutral 0.97 | neutral 0.692 | Neutral 0.993 | Neutral 1.0 | neutral 0.926 |

(The multi-label model A reports every label at or above 0.5; "none at 0.5" means it abstained. Other models return one label from a softmax.)

**Observations (descriptive; qualitative only)**

*tabularisai (emotion, multi-label):*
- English and Hindi-Devanagari examples came out as intended, with high scores.
- Marathi-Devanagari "I am very angry" was labelled **fear at 0.975**, a high-scoring unexpected label (Marathi is not a listed language).
- Roman and code-mixed examples frequently came out **neutral** (for example the positive Roman Hindi line at 0.64 and the
  positive code-mixed match lines at 0.89 and 0.88): a silent failure mode, because "neutral" looks like a valid answer.
- Two code-mixed negative lines produced **no label at or above 0.5**: the multi-label threshold gives natural abstention.
- Emoji lines (love, sadness) came out as intended.

*MahaEmotions-BERT (Marathi emotion, single-label):*
- Positive Devanagari lines came out as intended; the Marathi "I am very angry" line was labelled **Sadness at 0.82**,
  even though Marathi is the model's own language and Anger/disgust is one of its classes; the Hindi angry line
  was also labelled Sadness.
- Roman Marathi lines were all Neutral (0.83 to 0.91). Roman Hindi gave Surprise and Fear for positive and angry lines.
- A single softmax cannot abstain except through a low top probability.

*HindiEmotion (Hindi Devanagari only):*
- The three Hindi-Devanagari lines came out as intended, but English "happy" and "frustrating", Marathi, Roman and code-mixed
  lines were mostly neutral, and **all three Roman Hindi lines were labelled anger** (including "I am feeling very good"
  at 0.76). Confident and wrong outside its language.

*Sentiment models:*
- **XLM-T** (licence unverified): English, Hindi-Devanagari, Marathi-Devanagari and emoji lines mostly as intended; Roman lines were low
  scoring and mixed (top probability between 0.34 and 0.56), and two Roman Hindi lines had the opposite polarity to
  the intent. Its low top probabilities on uncertain text are a usable abstention signal.
- **MahaSent-MD** (Marathi): surprisingly consistent on English, Hindi-Devanagari, Marathi-Devanagari and code-mixed lines, but it
  returned Neutral at 0.99+ for the positive Roman Hindi line and for "I am very angry" in Roman Marathi, with scores of 0.99 or more.
- **MeSent** (Marathi-English code-mixed): matched the intended polarity on all four code-mixed lines and most Roman lines, but
  gave **Neutral at 1.0** for two Marathi-Devanagari lines (positive and angry) and Positive for a neutral Roman Hindi line.
  Its probabilities were about 1.0 almost everywhere, so **the score carries no information about correctness**.
- **Hinglish-tw**: good on English and emoji; returned neutral for the Hindi and Marathi Devanagari lines (0.9+), negative for the positive
  Roman Hindi line, and **positive for "Mujhe ye bilkul pasand nahi bro" ("I do not like this at all")**, a negation failure; consistent
  with its card ("emoji take more attention than the Hinglish words").

*Language identification and encoder models:*
- **MeLID-RoBERTa** (Marathi/English/Other): English words were tagged English and Roman Marathi words mostly Marathi, but Roman **Hindi**
  was tagged Marathi (there is no Hindi class) and a few Marathi function words were tagged English; emoji got "Other".
- **HingBERT-LID** (English/Hindi only): every word is forced into EN or HI, so Marathi became HI, emoji became HI, and several Devanagari
  function words were tagged EN. It cannot express "other".
- **MeBERT-Mixed** (masked language model): confirmed to be a fill-mask model with no classification head. For the masked sentence
  "Aaj match khup [MASK] hota bro" its top prediction was a plausible Roman Marathi word; it is not an emotion or sentiment classifier.

**Cross-cutting findings**
1. **No model handled all conditions.** Every model failed on at least one category, and the failures were often confident.
2. **Probability is not confidence.** Three models (MeSent, MahaSent-MD, HindiEmotion on foreign input) gave 0.99 to 1.0 on outputs that
   did not match the intent; the multilingual XLM-T was the opposite, with low scores on uncertain text. Using a raw top probability as
   "confidence" would be misleading.
3. **Roman-script Hindi and Marathi are the weakest area for emotion** and are UNVERIFIED everywhere; the silent "neutral" outcome is the main risk.
4. **Negation and sarcasm** (for example "pasand nahi") failed in one model; emotion models disagree heavily on the same angry line
   (anger, fear, sadness, neutral were all returned).
5. **Labels are incompatible across emotion models** (11 labels including frustration, contempt, gratitude, love versus 10 including
   Pride, Respect, Sarcasm, Excitement versus 7 basic emotions).
6. **Emoji behaviour differs** by model (decisive in one, ignored in another).
7. **Practicality on CPU (this machine, 4 threads, measured with single-sentence calls):** loading took 1.3 to 26 s (the first
   load reads the file), 23 sentences took about 2 to 3 s for a model (roughly 0.1 s per sentence including Python overhead), and each
   model needs about 0.15 to 1.1 GB of disk. Memory was not measured. A pipeline with several models would need about 4 to 5 GB
   of weights. No performance guarantee is implied.

## 8. Proposed architecture (not locked)

The research supports a **coverage-gated, abstaining** design, not an "all languages" one:

```
Message (local, in memory)
   -> Preprocessing (existing masking; keep emoji and original characters)
   -> Script / code-mix assessment (existing Script Mix: script class, alternations)
   -> Coverage check against a declared support table (language/script/code-mix x task x model)
        unsupported or unverified ............. -> return "unsupported" / "unverified" (no model run)
        supported-claimed ..................... -> run the declared model(s) for the task
   -> Sentiment classifier  (3 labels)    +    Emotion classifier (native labels of the routed model)
   -> Reliability check (calibrated score, abstention threshold, model agreement where two models overlap)
        low reliability ....................... -> return "low confidence"
   -> Aggregate analysis (counts with denominators, per model and label set; never pooled across label sets)
   -> Privacy filter (aggregate only)
   -> Dashboard (later, and only after approval)
```

Why it is not locked: the router depends on a language/script assessment that cannot be validated for romanised text (section 9), the
reliability layer depends on labelled calibration data that does not exist, and two of the three routes need licence confirmation. These are
prerequisites (section 17), not details.

## 9. Language and code-mix routing strategy

- **Script Mix is the only validated routing input.** Devanagari-only, Latin-only, mixed-script, and no-alphabetic messages are known
  deterministically; script is not language.
- **Latin-script messages cannot be routed by language today.** Latin may be English, romanised Hindi, romanised Marathi or code-mixed.
  The two token-level identifiers examined are not adequate: MeLID covers only Marathi/English/Other (Hindi is mislabelled Marathi) and
  HingBERT-LID covers only English/Hindi (Marathi mislabelled Hindi, emoji labelled Hindi). Neither has published validation we could
  check, and neither separates Hindi from Marathi.
- **Devanagari messages cannot be split into Hindi and Marathi** without a validated identifier; Devanagari alone does not
  select a single-language model safely.
- **Design consequence.** The route is chosen by **declared support** per task, and anything whose language cannot be established
  is returned as `unverified_language`. A router would send a message to a model only when the support table says the model covers its
  script/code-mix class *and* a validated language assessment (future work) agrees. Until then the usable routes are limited: English
  (once English can be established), and explicitly exploratory runs flagged as such.
- A word-level language identifier is **EXCLUDED** for now (section 18), pending validation.

## 10. Sentiment label strategy

- Labels: positive, negative, neutral, plus the system states `unsupported`, `unverified_language`, `low_confidence`.
- Each result records the model name, version/hash and the script/code-mix class; aggregates are per model.
- Models disagree on the same lines (section 7), so outputs from different models are **not merged** into one column without evidence
  that the merge is valid. Where two supported models overlap, disagreement is a reliability signal, not something to average away.
- No class is silently collapsed (for example "neutral" from a model that returns it for unsupported text must be distinguishable from
  a genuine neutral: the coverage check comes first).

## 11. Emotion label strategy

- **Native labels only.** Each result carries the model's own label set (A: 11 labels, multi-label; B: 10 labels; others as above).
- **No universal taxonomy, no label merging.** Any mapping (for example "frustration" or "anger/disgust" to a shared "anger" class,
  or "respect" and "pride" to a positive group) would be a semantic decision that changes meaning; a mapping is considered only
  after the native labels have been evaluated and with written justification per label. Labels with no counterpart remain unmapped.
- Multi-label output (model A) and single-label output (the others) are **not comparable**; aggregates never mix them.
- Because Roman/code-mixed emotion is UNVERIFIED everywhere, the default for those messages is `unverified_language`, not a label.

## 12. Confidence handling

- A raw model probability is reported as **"model score"**, never "confidence", unless it has been calibrated on labelled data.
- Observed: some models are saturated (about 1.0 on wrong answers), some are low on uncertain input. Without calibration, no single
  threshold is defensible; thresholds cannot be set from 23 invented sentences.
- Required before any thresholding: a labelled validation set, calibration (for example temperature scaling per model), a reliability
  diagram and expected calibration error per stratum (script, code-mix type), and a coverage-versus-error curve to choose an abstention
  threshold.
- Multi-label models can abstain naturally (no label above threshold); single-label models need an explicit rule. Disagreement between two
  overlapping models can serve as an additional low-reliability flag.

## 13. Unsupported and low-confidence handling

The system must be able to return, and the dashboard must display as such, at least:
- `unsupported`: the support table says no model covers the script/language/code-mix class for the task;
- `unverified_language`: language cannot be established for this message (for example Latin-script text);
- `low_confidence`: a supported model ran but its reliability check failed;
- `not_applicable`: no alphabetic text (links, digits, emoji only) per Script Mix.

These are counted and shown like any other outcome (with denominators); they are never replaced by a forced prediction and never
counted as "neutral".

## 14. Privacy design

- **Local, offline inference only.** No message text is sent to a hosted service or API. Models are obtained once as files and loaded
  from disk; no telemetry; inference does not need the network. (In this environment, Python's HTTP client could not verify the
  Hugging Face certificate; files were therefore downloaded with another client and loaded offline, which suits the privacy goal. A future
  setup must not depend on the network at run time.)
- **Model files and caches stay outside the repository**; model licences and attribution (CC-BY) are recorded with them.
- **No message-level outputs for real chats.** Outputs are aggregate counts (per model, per label, with denominators and the unsupported /
  low-confidence categories), using the existing display-layer privacy approach. Any per-message table is internal only and never written
  to shared results or shown.
- No sender names, numbers, URLs or raw text appear in outputs; emoji may be passed to a model but not displayed as text.
- Model predictions are **probabilistic signals, not facts about a person**; wording in the interface must say so (the tabularisai card
  itself makes this point).
- Additional risk: heavy models and downloads complicate hosted deployment; the local-only approach favours local use.

## 15. Evaluation strategy

Three separate things must never be conflated:

**A. Published benchmark performance (external, reported by model authors).** Their numbers describe their test sets, not WhatsApp:
tabularisai F1-micro 0.840 on its own synthetic-distribution test set (and zero-shot checks on English/Arabic/Spanish human data only),
MahaEmotions and MahaSent-MD and MeSent on Marathi and code-mixed tweets, Hinglish-tw f1 0.74 on its converted dataset, XLM-T about 0.69 on
its multilingual tweet set. They are quoted as such and never as our accuracy.

**B. Our qualitative feasibility test (this phase).** 23 invented sentences, no labels, no statistics.

**C. Future evaluation requirement (needed before any accuracy statement):**
1. An **in-domain, labelled WhatsApp-style evaluation set** (public, synthetic with documented method, or consented data) stratified by
   English, Hindi and Marathi in Devanagari and Roman script, Hindi-English and Marathi-English code-mixing, emoji, short messages,
   negation, all-capitals, and announcement text; separate **sentiment** and **emotion** labels with written guidelines.
2. **At least two fluent annotators**, inter-annotator agreement (Cohen's kappa or equivalent), adjudication, and a held-out test
   split never used for threshold or model selection.
3. **Metrics** reported per stratum and per model: accuracy, per-class precision, recall and F1, macro-F1, confusion matrix, expected
   calibration error, and abstention coverage versus error; bootstrap confidence intervals. No pooled figure across strata that hides
   failures.
4. **External benchmark checks** on MahaEmotions (test, manual), MahaSent-MD, MeSent and English benchmarks where licences allow.
5. **Invariance tests**: the same sentence in Devanagari and in Roman script, with and without emoji, and negated variants; report
   cross-script consistency.
6. Acceptance criteria written **before** running (per stratum, per model); a stratum that does not meet them is marked unsupported.
7. Error analysis by stratum (silent "neutral", negation, sarcasm, cross-language confusion).

## 16. Current-chat limitations

- Only 24 text messages (18 unique): 16 Latin-only (language unverified; appear English on manual reading), 7 mixed English/Devanagari,
  announcement-heavy, 23 of 24 from one sender, 3 forwarded, many repeats. Nothing here can validate or calibrate a model.
- Announcement and instruction text is mostly neutral, so any distribution of labels would mostly describe the genre.
- No labelled data; no defensible evaluation protocol exists for the chat itself.
- Therefore predictions on the current chat, if ever run, are **exploratory** and must be presented as coverage and model-behaviour
  counts (how many messages were supported, unsupported, low-confidence), not as findings about the group. The earlier exclusion
  (`docs/sentiment_design.md`) stands for the current chat. Real-chat text was **not** used in this phase.

## 17. Implementation prerequisites (all must hold before any production code)

1. **Licences confirmed** in writing for every model to be used: tabularisai (non-commercial), XLM-T (UNVERIFIED), and dataset licences
   where datasets are used (the GitHub-hosted datasets are UNVERIFIED); confirm that the intended project use (MSc, non-commercial,
   local) is covered and record attribution.
2. **Labelled evaluation data and the protocol in section 15** agreed and built; acceptance criteria fixed first.
3. **A support table** (language/script/code-mix x task x model) with each cell's evidence; every UNVERIFIED cell defaults to "unsupported".
4. **A validated way to establish language for Latin-script and Devanagari messages**, or explicit acceptance that such messages stay
   `unverified_language`.
5. **Calibration and abstention thresholds** derived from labelled data.
6. **Dependency decision** (approval required, not installed in the project): `transformers` with a compatible `huggingface_hub`
   (in this trial the 4.57 line worked with `huggingface_hub` below 1.0; the 5.x line required an extra HTTP package that was
   not available), `tokenizers`, `safetensors`, `regex`, `sentencepiece` for one model, and the existing `torch` (CPU build present).
   Models must be loadable offline.
7. **Resource budget**: disk (about 0.15 to 1.1 GB per model), load time, and memory measured on the target machine.
8. **Privacy design of section 14** implemented with leak tests, extending the existing ones.
9. **Dashboard integration** designed and approved separately (not part of Phase 1).

## 18. Decisions

| Component | Decision | Reason |
|---|---|---|
| Script / code-mix assessment as the routing input (existing Script Mix) | **IMPLEMENT** (already implemented) | Deterministic, validated, privacy-safe; explicitly not language identification |
| Support table and "unsupported / unverified / low-confidence" outcomes | **IMPLEMENT** (as part of any future work) | Required so that no prediction is forced; needs no model |
| Word-level language identification (MeLID, HingBERT-LID or others) | **EXCLUDE** | Two-language coverage only; Hindi mislabelled as Marathi and the reverse; Devanagari and emoji misfires; no validation available |
| Roman-script Hindi/Marathi handling for emotion | **EXCLUDE** (report `unverified_language`) | No model documents support; behaviour observed was inconsistent and often a silent "neutral" |
| Sentiment classifier, coverage-gated | **LIMITED**: candidates XLM-T (licence UNVERIFIED), MahaSent-MD (Marathi Devanagari), MeSent (Marathi-English code-mixed), English models; exploratory until validated | Best-documented area, but no model covers every condition; needs licence confirmation, labelled evaluation and calibration |
| Emotion classifier, coverage-gated | **LIMITED** (exploratory, opt-in): tabularisai for English and Hindi Devanagari (non-commercial licence), MahaEmotions-BERT for Marathi Devanagari | Labels incompatible across models; confident errors observed (Marathi anger labelled fear or sadness); no code-mixed or Roman evidence; nothing for Hindi-English or Marathi-English emotion |
| Universal emotion taxonomy / label normalisation | **EXCLUDE** | No semantically defensible mapping between the native label sets |
| Custom fine-tuning (for example on MeBERT-Mixed) | **EXCLUDE** | No labelled data; would need its own protocol |
| Confidence calibration and abstention layer | **IMPLEMENT** (prerequisite of any classifier) | Raw probabilities were saturated or uninformative; thresholds must come from labelled data |
| Aggregate-only outputs and privacy filter | **IMPLEMENT** (part of any future work) | Matches existing privacy rules; no per-message real-chat output |
| Application to the current 24-message chat | **LIMITED** (coverage counts only, exploratory) | Too small, unlabeled, announcement-heavy; earlier exclusion stands |
| Dashboard integration | **PENDING** | Not designed in this phase |

**Overall recommendation.** **Do not proceed to a production emotion/sentiment pipeline yet.** Proceed only to Phase 2 preparation:
(1) confirm licences, (2) design and build the labelled evaluation set and protocol, (3) decide the dependency approach,
then re-test the candidate models under that protocol. Until then, the capability stays exploratory and coverage-gated, and any
claim of "supports every language" is explicitly not made.

## Appendix: method and environment notes (scratch area, outside the project)

- Models were downloaded to a scratch directory with a standard HTTP client and loaded **offline** by path; transformers 4.57.6,
  `huggingface_hub` 0.36.2, tokenizers 0.22.2, safetensors 0.8.0, regex and sentencepiece 0.2.2 were installed to a scratch library folder
  (not the project or the main Python environment), with the existing CPU `torch` 2.13. The 5.x line of `transformers` failed to import
  because its `huggingface_hub` dependency needed a package not available here.
- Loading adjustments that were part of the test setup, not of prediction: a slow (sentencepiece) tokenizer for XLM-T because the fast
  conversion failed, and `add_prefix_space=True` for the RoBERTa token classifier (required by its tokenizer for pre-split words).
- Models not tested: community Hinglish emotion models with empty cards and no licence (for example Gek524), additional Hinglish sentiment
  uploads with minimal cards, and other multilingual GoEmotions re-implementations (not documented for Indic text).
- Inputs were 23 invented sentences held in memory and in scratch files only. No real chat text was used. No file in the project
  (source, tests, dashboard, requirements, results, data, other documents) was changed.
