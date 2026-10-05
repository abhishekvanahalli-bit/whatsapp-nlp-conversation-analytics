# TF-IDF Technical Design Note (Milestone 2, design only)

> **Status note (2026-10-05).** This note was written during development about the private development chat (`data/chat.txt`, not in the repository) and describes the validated results at that time. The current behaviour of the pipeline is described in `supported_formats.md`, `final_audit_fixes.md` and `final_verification.md`; where they differ, those pages win.

> **Current status (final audit 2026-10-01): the approved design was implemented** in `src/tfidf_analysis.py`
> (results in `results/tfidf_*`; tests in `tests/test_tfidf_analysis.py`).
> Original status when written: **design proposal. Nothing is implemented and no TF-IDF results exist yet.**
> Dataset facts used here describe the shape of the private development chat (not published): a small number of
> real text messages used for NLP; fewer unique message texts after URL masking; English + Marathi (Devanagari);
> one sender wrote most messages; repeated announcement/invitation-style messages. Raw chat files and
> `processed_chat.csv` are never modified.
> Any numbers in section 1 are a **toy illustration**, not project results.

---

## 1. What TF-IDF is

**Term Frequency (TF)** asks: *how prominent is this word inside one document?*
**Inverse Document Frequency (IDF)** asks: *how rare is this word across all documents?*
Multiplying them rewards words that are frequent here but rare elsewhere.

**Formulation** (the common smoothed variant, e.g. scikit-learn's default):

- `tf(t, d)` = number of times term *t* occurs in document *d* (raw count)
- `df(t)` = number of documents containing *t*; `N` = number of documents
- `idf(t) = ln((1 + N) / (1 + df(t))) + 1`
- `tfidf(t, d) = tf(t, d) × idf(t)`, then each document vector is L2-normalised:
  `tfidf_norm(t, d) = tfidf(t, d) / sqrt(Σ_t' tfidf(t', d)²)`

Toy illustration (N = 4, not project data): a term in 1 of 4 documents has
`idf = ln(5/2) + 1 ≈ 1.92`; a term in all 4 has `idf = ln(5/5) + 1 = 1.00`. The `+1` and the
smoothing keep ubiquitous words at weight 1 instead of 0 and avoid division by zero.

**What a high TF-IDF score means:** in that document, the term is comparatively frequent *and* it
appears in few other documents of this corpus. It means "distinctive within this collection", not
"important", "positive", or "meaningful" in any wider sense.

## 2. Why TF-IDF is being added

- Raw counts (our n-gram tables) rank words by how often they occur overall. Words common to
  every message therefore dominate, regardless of whether they tell messages apart.
- TF-IDF adds a **per-message distinctiveness** measure: which words characterise a particular
  message relative to the rest of the chat.
- For conversation analysis, this helps to (a) summarise what each message is *about* in a few terms,
  (b) separate template/boilerplate vocabulary from message-specific content, and (c) later provide
  vectors for similarity/near-duplicate checks (roadmap stage I) if justified.

It is added because it answers RQ6 ("which messages/terms are distinctive relative to the rest of the
chat"), not to enlarge the project.

## 3. Difference from the existing n-gram analysis

| | N-gram analysis (implemented) | TF-IDF (proposed) |
|---|---|---|
| Question | What words/phrases occur, and how often (with and without repetition)? | Which terms distinguish one message from the others? |
| Unit of result | Corpus-level counts | Message-level (and aggregated) weights |
| Sensitive to | Volume and repetition | Rarity across documents |
| Word order | Kept (n = 2, 3) | Ignored (bag of words; unigrams first) |

They coexist because they are complementary: n-grams describe the *dominant vocabulary and
templates*, TF-IDF describes *what stands out against that background*. Comparing the two also
exposes repetition effects: a term can be very frequent (n-gram top ranks) yet have a low TF-IDF weight
because it appears in most messages.

## 4. Document definition

| Option | Assessment for this dataset |
|---|---|
| **One message = one document** | Natural unit; one document per text message (or per unique text); keeps `line_start` traceability; matches n-gram design. Small N, but honest. |
| One participant = one document | **Rejected.** One sender wrote nearly all messages, so this yields effectively 1 large document and 2 tiny ones. IDF is meaningless with N = 3. |
| One day/time period = one document | **Rejected as primary.** Only a few dates, one of them holding a large share of the rows, and several days with few or no text messages, so day documents are highly uneven. May be run later purely as an exploratory sensitivity check, clearly labelled. |

**Decision: one message = one document.** Because messages repeat, IDF will be computed in two variants
(no message is deleted from the data; this mirrors the `count_all` / `count_unique` design):

- **Variant A (PRIMARY / HEADLINE): all actual text messages (N = number of text messages).** These messages are the actual
  conversation. Exact duplicates are not silently removed from the primary analysis, so repeated
  boilerplate keeps its real effect (including lowering the IDF of its own words).
- **Variant U (SENSITIVITY / COMPARISON): unique message texts (N = number of unique texts).** Shows how the rankings
  change when repeated templates are collapsed to one copy each.

**Definition of N:** N is the total number of documents in the selected corpus, i.e. N = the number of text
messages for variant A and the number of unique texts for variant U. N is *not* redefined as the number of non-empty documents (see the
empty-document rule in section 6).

Reporting both, side by side, shows whether conclusions depend on the repetition treatment. The unique
set must be defined with the same rule as the existing analysis (`text_masked` equality, after
forwarded-marker removal and URL/phone masking) so the numbers reconcile with `is_repeat`.

## 5. Corpus limitations (explicit)

- **N is tiny.** IDF values are coarse: with N documents, df can only be 1..N, so many terms share
  identical IDF. A term appearing in one message has the maximum IDF by construction, so rare
  words are not "special", just unique to one short message.
- **Short documents.** Many messages have few tokens, so TF is mostly 1 and TF-IDF is dominated by IDF.
- **Sender imbalance.** Almost all documents come from one sender, so "distinctive" means
  "distinct within one organiser's announcements", not distinct between people.
- **Repeated templates.** Variants U vs A differ precisely because of this; neither is "the truth".
- **Mixed language.** Marathi words are not filtered by the English stopword list (baseline measured:
  0% of Devanagari tokens removed). Unsuffixed/suffixed Marathi forms are separate types
  (e.g. खेळाडू vs खेळाडूंनी), which fragments df.
- **Very small corpus overall.** Scores are unstable: dropping or adding one message can change
  rankings. Results are descriptive of this sample only.

## 6. Preprocessing decisions

Start from the existing analysis layer (`build_analysis_corpus`), so TF-IDF sees the same text as the
n-gram analysis.

| Item | Decision | Rationale |
|---|---|---|
| `[Forwarded]` marker | Already removed from analysis text; `is_forwarded` kept as a column | Metadata, not vocabulary. Forwarded rows can be flagged or compared later. |
| URLs | Already masked to `<URL>`; **excluded from the ranked TF-IDF vocabulary**, but counted in a per-message `has_url` flag | A placeholder is not a lexical term; ranking it would only report "this message contains a link". The information that a link occurred is preserved in metadata. |
| Phone numbers | Already masked to `<PHONE>`; excluded from vocabulary the same way | Same reasoning; also guarantees no raw numbers reach outputs. |
| English stopwords | Use the existing Day 1 list (`tokens_no_stopwords`) | Consistent baseline. IDF down-weights common words automatically, but with a small corpus (a small N in the primary all-message variant; N = 18 in the unique-text sensitivity variant) that down-weighting cannot be relied on, and the resulting TF-IDF rankings should not be treated as generalizable, so explicit removal is kept for comparability. |
| Marathi / Devanagari | **No stopword list yet.** Tokens are kept as-is; Devanagari terms are tagged with a script column in outputs. Multilingual preprocessing remains a separate, later, justified step | Avoids an unjustified hand-made list. The effect of leaving Marathi function words in is then shown, not hidden. |
| Punctuation | Same edge-stripping tokenizer as existing code; no extra stemming/lemmatisation | Keeps behaviour explainable; no Marathi stemmer is validated. |
| Repeated messages | **Not deleted.** Handled through the U/A variants (section 4) | Repetition is part of the real data. |
| Case | Already lowercased upstream | Already implemented. |
| Empty documents | A message with no retained terms after preprocessing (e.g. one that is only `<URL>`) has no TF-IDF vector. It **remains in the document set and counts toward N**, but contributes no term frequency and no document frequency. The number of empty documents is reported separately (count and `line_start` values in `tfidf_run_metadata.json`) | Avoids silent loss of documents; N stays the size of the selected corpus (24 / 18). The L2 normalisation applies only to documents that have terms. |

## 7. Expected output (design)

All outputs go under `results/`, use anonymised data only, and contain no raw phone numbers, names
or URLs.

**7.1 `results/tfidf_terms_by_message.csv`** (long format, one row per message × term, variant U and A
in a `variant` column)

| Column | Meaning / interpretation |
|---|---|
| `variant` | `unique` or `all` (section 4) |
| `line_start` | Traceability key to `analysis_corpus.csv` |
| `sender_anon` | `Sender_N` pseudonym |
| `is_forwarded`, `is_repeat` | Metadata carried through |
| `term` | The word |
| `script` | latin / devanagari / other (existing `token_script`) |
| `tf` | Raw count in this message |
| `df` | Messages in the variant that contain the term |
| `idf` | Smoothed IDF as in section 1 |
| `tfidf_raw` | `tf × idf` |
| `tfidf_norm` | After L2 normalisation (comparable across messages of different length) |
| `rank_in_message` | 1 = highest `tfidf_norm` in that message (ties broken alphabetically) |

**7.2 `results/tfidf_top_terms.csv`** (aggregated across messages, per variant)

| Column | Meaning |
|---|---|
| `variant`, `term`, `script` | as above |
| `df`, `idf` | how many messages, how rare |
| `total_tfidf`, `mean_tfidf_in_docs` | sum over messages, and mean over only the messages containing the term. Both are reported because the sum favours frequent terms, the mean favours rare ones |
| `n_docs_top3` | in how many messages the term is in that message's top 3 |

**7.3 `results/tfidf_variant_comparison.csv`** — term, rank under U, rank under A, rank change,
`count_all` and `count_unique` from the n-gram table. It shows repetition sensitivity and
the frequency-vs-distinctiveness contrast with the n-gram results.

**7.4 `results/tfidf_run_metadata.json`** — N per variant, vocabulary size, number of empty documents,
formulas/parameters (smoothing, norm, stopword list version), library versions.

Design choice for sensitivity: unigrams only in the first version. Bigram TF-IDF is deferred; with a small number of
short documents it would be almost entirely df = 1.

## 8. Interpretation (how results will be worded)

Acceptable, supported wording (template; no real values yet):

- "In message *M*, *X* has one of the highest TF-IDF scores because it occurs in this message and in
  only *k* of the *N* messages in this sample. Within this chat it therefore distinguishes message *M*."
- "*X* ranks high in the primary variant A but lower in the sensitivity variant U (or the reverse),
  which indicates its score depends on how repeated messages are counted."

Not acceptable: "*X* is the most important topic of the group", "*X* shows what people care about",
"the sender prefers *X*", or any claim about other chats. Also avoid over-reading ties: many terms
will share an identical IDF, so differences among them come only from TF and message length.
Every table and chart carries the caption: *descriptive result from this small
sample; not generalisable.*

## 9. Validation and quality checks (to implement after coding)

1. **Formula check:** on a tiny hand-computed corpus (e.g. 3 documents), assert `idf`, `tfidf_raw`
   and `tfidf_norm` equal the values computed by hand in the test.
2. **Independent cross-check:** compare with `sklearn.feature_extraction.text.TfidfVectorizer`
   (identity analyzer on the same token lists, smooth IDF, L2) if scikit-learn is installed; values
   should match to floating-point tolerance. Availability of the library must be verified first.
3. **Normalisation:** each non-empty document's `tfidf_norm` values have L2 norm 1 (± tolerance).
4. **Range/sign:** `idf ≥ 1`; `tfidf_raw > 0` for every listed row; `df ∈ [1, N]`.
5. **df consistency:** `df` matches an independent count from the token lists.
6. **N reconciliation:** variant A N = number of text messages; variant U N = number of unique texts.
   Empty documents still count toward N and are reported separately as a count, with their
   `line_start` values; they must contribute no tf or df.
7. **Repeat behaviour:** identical texts get identical vectors; in variant U they appear once.
8. **Placeholder/privacy:** no `<URL>` or `<PHONE>` in `term`; no `+91`, phone digits or
   `chat.whatsapp.com` in any output file (extends the existing leak test).
9. **Determinism:** two runs give byte-identical files (stable tie-breaking).
10. **Non-interference:** `data/chat.txt`, `processed_chat.csv` and existing n-gram outputs are
    unchanged after a run (md5 check, as before).
11. **Sensitivity report:** top-N term overlap between variants U and A, and after leaving out any one
    message (leave-one-out), to quantify instability rather than assert stability.

## 10. Limitations (what TF-IDF cannot tell us here)

- It does **not** show sentiment, intent, topics, or importance.
- It cannot support conclusions about people: one sender dominates, so no sender comparison.
- It cannot generalise beyond this sample; a handful of tiny documents give unstable, coarse rankings.
- It ignores word order and meaning (no synonymy, no negation, no phrases).
- It treats inflected Marathi forms as different words and leaves Marathi function words uncontrolled
  until multilingual preprocessing exists.
- A high score partly reflects *message brevity and uniqueness*, not linguistic significance.
- It cannot separate genuine content from templating without the variant comparison.
- No accuracy or quality metric is claimed: there is no ground truth; validation is by
  correctness checks and sensitivity analysis only.

## 11. Viva explanation

> "The n-gram analysis tells me which words and phrases occur most often, but in this chat the most
> frequent ones are mostly repeated announcement templates, so frequency alone tells me little about
> what makes messages different. TF-IDF adds a second view: it weights a word by how often it appears
> in a message and down-weights it if it appears in many messages. I treat each message as a document,
> and I compute it both with and without counting repeated messages, so I can show how much repetition
> affects the result. The corpus is only a few dozen messages and mostly from one sender, so I present TF-IDF
> descriptively as 'what is distinctive in this sample', check it against a hand-computed example and
> scikit-learn, and do not claim it generalises."

## 12. Rubric alignment

**Methodology & Implementation (15 marks):** a standard technique chosen for a stated question (RQ6),
with a justified document definition, explicit rejection of unsuitable alternatives, two-variant
design to handle repeated messages, principled preprocessing reused from the tested analysis layer,
and a concrete validation plan (hand-computed test, library cross-check, invariants, leak checks).

**Analysis, Results & Interpretation (10 marks):** structured output tables, planned visualisations
(top distinctive terms per variant; frequency-vs-TF-IDF comparison against n-gram counts; variant
rank change), and a pre-agreed interpretation vocabulary with stated limitations, so results are
explained rather than merely displayed.

## Implementation recommendation

Implement TF-IDF in a **new module `src/tfidf_analysis.py`** (not in the n-gram module), reusing
`build_analysis_corpus()` so preprocessing is identical. Use a small self-written implementation using
pandas/numpy for the formulas above (explainable line by line) and, if scikit-learn is available,
use `TfidfVectorizer` only as an independent test oracle. Scope for the first pass: **unigrams,
one message = one document, variants U and A, outputs in section 7, checks in section 9**. Defer
bigram TF-IDF, day-level documents and similarity/near-duplicate analysis. Add tests
before regenerating results, then report before/after in the same style as previous milestones.

**Please review and accept the design (especially the all-message primary variant, the unique-text
sensitivity variant, and the exclusion of `<URL>`/`<PHONE>` from ranked terms) before implementation
begins.**


## Update from the final audit (2026-10-05)

* **Tokenisation.** Tokens now have punctuation of any Unicode category stripped at their edges (for example the Devanagari danda) and curly
  quotes are normalised, so `don’t` and `don't` are one term and an English stopword. This changed the development chat's vocabulary by a couple of terms
  (`final_audit_fixes.md`). The TF-IDF formula is unchanged.
* **Typed CSV round trip.** Term columns are read as strings (`src/csv_io.py`), so `007` stays `007` and an all-numeric vocabulary no longer crashes.
* **Stability diagnostic.** The leave-one-out check recomputes the whole TF-IDF once per left-out document (about N squared work). It is exact for
  up to 200 documents ("full_leave_one_out"); for larger corpora it leaves out 60 evenly spaced documents ("sampled_leave_one_out"). The mode,
  the number of documents and the number of runs are recorded in `tfidf_run_metadata.json`. The scores, ranks and variants are computed first and
  are not affected by this diagnostic.
