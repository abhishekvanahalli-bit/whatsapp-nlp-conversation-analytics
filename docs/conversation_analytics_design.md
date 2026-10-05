# Conversation Analytics Design Note (Milestone 4, design only)

> **Status note (2026-10-05).** This note was written during development about the private development chat (`data/chat.txt`, not in the repository) and describes the validated results at that time. The current behaviour of the pipeline is described in `supported_formats.md`, `final_audit_fixes.md` and `final_verification.md`; where they differ, those pages win.

> Status: **design approved and implemented** (`src/conversation_analytics.py`; see the final section).
> The design text below is kept as originally reviewed. No dashboard has been built and no
> packages were installed.
>
> Counts quoted below are **verified dataset facts** (read-only inspection of `results/processed_chat.csv`
> and `results/analysis_corpus.csv`) used to judge feasibility. They are not analysis outputs and are
> descriptive of this one small chat only.

## Development dataset (described generically)

The design was developed on one small private group-chat export that is not published. Its exact counts, dates and
participants are deliberately omitted here. What mattered for the design decisions was its **shape**:

* a short span (a few weeks) with a handful of busy dates and several empty calendar dates;
* user rows that were mostly media placeholders and deleted-message tombstones, with only a small share of real text;
* a few forwarded rows, some messages containing links, and some multi-line messages;
* one dominant sender and very few others (so sender comparison would have been meaningless);
* several repeated announcement-style messages that become identical once links are masked;
* system rows made mostly of security-code notices, plus a few "added" and "settings changed" events;
* time zone and export locale not verified: timestamps are treated as written in the export.

The public fictional chats in `tests/fixtures/` reproduce each of these situations with invented data, and the
sample results in `results/sample/` show every table the design describes.

Existing fields that support the analytics: `message_type`, `sender`, `datetime`, `year/month/day`,
`day_name`, `hour`, `minute`, `period` (an **hourly bin** such as "15-16", not morning/afternoon),
`media_type`, `is_media`, `is_deleted`, `is_forwarded`, `line_start/line_end`, and, from the analysis
layer, `is_repeat`, `text_masked`, `has_url`, `sender_anon`.

---

## 1. Purpose

- **n-grams** describe which words/phrases occur. **TF-IDF** describes which terms distinguish messages.
  Both operate only on the real text messages and ignore everything else.
- **Conversation analytics** describes the *structure and activity* of the chat as a whole: how the
  parsed rows divide into user, system and header rows, what the user rows are (text, media, deleted,
  forwarded), when activity happened, how much of it is repetition, and who is present.
- It answers questions the NLP layers cannot (RQ1 composition, RQ2 timing, RQ3 sender contribution, and
  the repetition part of RQ4), and it puts the NLP results in context: it shows that the texts are
  only a small share of the rows and mostly one sender's announcements.
- It relies on metadata that already exists, so it adds no new preprocessing and no new modelling.

## 2. Temporal Analysis

Assessment per analysis; none is assumed to be implemented.

**2.1 Messages by date (activity timeline)**
- *Question:* On which days was the chat active, and were there bursts?
- *Fields:* `datetime` (date part), `message_type`, `is_media`, `is_deleted`.
- *Visualisation:* one daily count chart over the **full calendar range** (zero-filled, so the empty
  dates are visible), stacked by row kind (text / media / deleted / system).
- *Interpretation:* descriptive: concentration of activity on particular dates (for example one date
  can hold a large share of the user rows).
- *Limitation:* few active dates over a short span; a couple of dates dominate, so no trend or
  seasonality can be claimed. Bulk actions (many deletions within two seconds on one date) are single
  events, not "activity".

**2.2 Messages by day of week**
- *Question:* Are some weekdays busier?
- *Fields:* `day_name`.
- *Visualisation:* a small table only (no chart).
- *Interpretation:* none beyond "which weekdays occur in this sample".
- *Limitation:* each weekday appears only a few times in a short span, some weekdays may not
  appear at all, and one weekday's count can be dominated by a couple of dates. A weekday "pattern" would be an artefact
  of the calendar and one busy day.

**2.3 Messages by hour**
- *Question:* At what times of day do messages arrive?
- *Fields:* `hour` (user rows; system rows optionally separate).
- *Visualisation:* one small histogram, labelled exploratory.
- *Interpretation:* descriptive clustering of timestamps.
- *Limitation:* bursty data (a few minutes of many messages) dominate the histogram; time zone of the
  export device is unverified; no claim about habits.

**2.4 Messages by period (morning/afternoon/evening/night)**
- *Question:* Same as 2.3 at coarser grain.
- *Fields:* would have to be derived from `hour` (the existing `period` column is an hourly bin).
- *Assessment:* **adds no information over 2.3** and requires arbitrary cut-offs. Not proposed.

**2.5 Activity timeline** — see 2.1 (the primary temporal analysis).

**2.6 Message length over time**
- *Question:* Do messages get longer or shorter over time?
- *Fields:* `message` length or token count against `datetime`.
- *Assessment:* only a few dozen text messages over a handful of dates (most with only 1 to 3 texts), and a few long messages
  dominate. A time trend would be meaningless. Not proposed. A **length distribution** (not over time)
  is acceptable as a limited descriptive table.

## 3. Participant/Sender Analysis

Facts: nearly all user rows are from one sender and only a few from two others. Nearly all text
messages are from the dominant sender; one other sender has none
message (its single row is a deletion tombstone).

| Measure | Assessment |
|---|---|
| Total user messages by sender | Reportable as counts (one dominant sender, two minor ones). |
| Text messages by sender | Almost all from one sender; a single message is a few percent of the total. |
| Media by sender | 32 / 1 / 0 (from the row table; all but one media row are the dominant sender's). |
| Message length by sender | Not meaningful: one sender has almost all messages, another has one. |
| Percentages | Misleading: they describe one organiser, and small counts (1 or 2) give percentages that look meaningful but are single events. Ownership of the deletion tombstone from "deleted by admin" is also ambiguous. |

Options: A. include normally; B. include only as descriptive metadata; C. exclude from comparative claims.

**Recommendation: B, sender information kept as descriptive metadata only, which by definition
excludes comparative claims (the substance of C).** Report counts with denominators using
pseudonyms, with a dominance note ("one sender wrote almost all user rows"). No rankings, no "most
active member", no per-sender behaviour, sentiment or vocabulary comparisons. Rationale: the counts are
true and useful context for interpreting the NLP results, but no comparison between senders is
statistically or semantically supported.

## 4. Message-Type / Metadata Analysis

| Category | Question answered | Supporting field(s) | Proposed metric | Visualisation | Limitation |
|---|---|---|---|---|---|
| User vs system vs header | What share of parsed rows is conversation? | `message_type` | counts (user / system / header rows) | composition table / stacked bar | System rows are export events, not participants' words. |
| Text vs media vs deleted (user rows) | What do user rows consist of? | `is_media`, `is_deleted` | counts (text / media / deleted of the user rows) | same stacked bar | Media and deleted content is not observable, only counted. |
| Media types | Which media forms appear? | `media_type` | counts per media type (image, video, unknown, album) | small table | "unknown" is a parser category, not a real type. |
| Deleted messages | How much content was deleted, and was it bulk? | `is_deleted`, `datetime` | count; number of deletions on the same date / within seconds | daily timeline layer | The original content and reason are unknown; one tombstone says "deleted by admin", which does not identify the author reliably. |
| Forwarded messages | How much content was forwarded? | `is_forwarded` | count and share of user rows and of text messages | table | Original author unknown and not inferred. |
| Repeated messages | How much text repeats? | `is_repeat`, `text_masked` | see section 5 | table | Depends on the masking rule. |
| URLs | How often were links shared? | `has_url` (analysis layer), masking rule | count of messages with a URL | table | Links themselves are never shown. |
| Phone numbers | Does any user-authored text contain a phone number? | masking rule / `has_phone` | count (expected 0 in text; phone numbers appear in system rows and sender fields) | table (single line) | Detects only `+CC …` patterns; names/other formats are not detected. |
| Albums / media placeholders | Are albums present? | `media_type == "album"` | count (1) | included in media table | Single instance. |

## 5. Repetition Analysis

Repeated messages are **never deleted**; repetition is measured and reported.

**Distinctions**
- **Exact repeated raw text:** identical `message` text. Verified: 2 groups (4 messages, 2 repeat rows).
- **Repeated templates after URL masking:** identical `text_masked`. Verified: 3 groups holding 9
  messages (group sizes 5, 2, 2), giving a number of repeat messages and fewer unique texts. The largest group is the
  group-invite message: 5 messages that differ only in the link, so they are **not** exact raw repeats
  and become identical only after masking.
- **Occurrences:** size of each group.
- **Unique vs repeated content:** text messages = unique texts + repeats.

**Proposed measures:** number of text messages, unique texts, repeat messages, repeat share, number of
template groups and their sizes, dates on which each group occurred. Report groups as anonymous
template identifiers (T1, T2, T3) with size and dates, not as message text.

**How repetition affects other layers**
- *n-grams:* repeated templates produce the top phrases (already shown by the all-versus-unique counts).
- *TF-IDF:* repeats change document frequencies and therefore IDF (already handled with the all-message
  primary and unique-text sensitivity variants).
- *Interpretation:* repeated announcements suggest broadcast behaviour (the same instruction sent
  several times, often to different sub-groups), not several people saying the same thing. Interpretation
  must stay descriptive: the data cannot show *why* messages were repeated.

## 6. System Messages

- **Not user-authored text.** They are excluded from NLP and are analysed only as events.
- **Proposed descriptive analysis:** count of system rows by category, derived by pattern classification
  of the message (security-code change, member added, settings change, other), and system events per
  date on the timeline. Category labels must be generic; the raw text is never shown.
- **Composition:** system rows: mostly "security code changed" (some with a phone-number
  subject and 1 with a personal name), 1 member added, 1 settings change.
- **Interpretation:** administrative/encryption events; for example, a cluster of security-code
  changes is a group-membership/device event, not conversation.
- **Limitation:** small counts; no participant-level claims (the events name people, which is a privacy
  issue, see section 8).

## 7. Forwarded Messages

Using `is_forwarded` only:
- **Forwarded count:** a few user rows (text and media).
- **Forwarded proportion among user messages:** report as counts with
  denominators.
- **Forwarded text vs non-forwarded text:** number of text messages in each group, with the NLP layers
  already treating the `[Forwarded]` marker as metadata. Separate reporting of forwarded rows is
  recommended (consistent with the sentiment decision).
- **Not inferred:** the original author or source of forwarded content is unknown and must not be
  guessed, including from the forwarded text's names or links.
- **Limitation:** all forwarded rows come from the dominant sender; no comparison is possible.

## 8. Privacy

**Must never appear in the dashboard or report:**
- Phone numbers (in `sender`, in system rows, in the "deleted by admin" text).
- Personal names, including names inside system rows and names of people, teams or schools inside
  message text.
- Raw message text where aggregate counts suffice (which is nearly everywhere in this module).
- URLs, in particular group-invite links, which are access tokens and may identify the group and allow
  joining it.
- The raw `sender` value, the `message`, `clean_message` and token columns of `processed_chat.csv`, and
  `data/chat.txt`.

**Anonymisation design:**
1. Read `processed_chat.csv` only; never write it or copy identifying columns.
2. Replace senders with pseudonyms assigned by **order of first appearance** using a deterministic rule.
3. Derive from text only the boolean/categorical facts needed (`has_url`, `is_forwarded`, `is_repeat`,
   system category, deleted-by-admin flag). Do not output the text.
4. Represent repeated messages as anonymous template IDs (T1..Tn) with counts and dates.
5. System-message categories are generic labels.
6. Add automated leak tests that load sender values, system-row text and URLs from the raw data
   **at test time** and assert none appear in any output file.

**Pseudonym consistency issue found during this review.** The existing outputs
(`analysis_corpus.csv`, TF-IDF outputs) build `Sender_N` from the *text* rows only. Over **all user
rows** the first-appearance order differs: the sender who wrote the one non-dominant text message is
`Sender_2` in the existing outputs, but would be third in an all-user-rows ordering (a sender who has only
a deletion tombstone appears earlier). Using `Sender_N` in a new module with all-rows ordering would give
the same label to different people in different files. Existing outputs must not be regenerated in
this milestone. **Recommendation:** the new module uses a **different prefix** (for example
`Participant_N`) derived from all user rows, and a documented crosswalk between `Sender_N` and
`Participant_N` (pseudonyms only) is kept in the report. Alternative for later review: a single shared
pseudonym function, with regenerated outputs.

**Residual risk:** even pseudonymised counts can identify a role (the dominant sender is obviously the
organiser to group members). Outputs are for local/academic use and must be verified before submission.
Privacy is an ongoing requirement, not a solved property.

## 9. Proposed Metrics

Only metrics defensible for this dataset. Every metric is a count or a simple ratio with its
denominator shown.

| Metric | Purpose | Data field | Visualisation | Interpretation | Limitation |
|---|---|---|---|---|---|
| Row composition: user / system / header | Show the conversational share of the export | `message_type` | stacked bar / table | Only some of the rows are user rows | Export events are not conversation |
| User-row kind: text / media / deleted | Show what user rows contain | `is_media`, `is_deleted` | same stacked bar | Only a minority of user rows have text | Media/deleted content unobservable |
| Media type counts | Describe media placeholders | `media_type` | table | Image/video/other/album counts | "unknown" is a parser category |
| Daily row counts by kind (zero-filled calendar) | Show activity over time and empty days | `datetime` (date), kind | timeline (stacked bars) | Activity is concentrated on a few dates | few active dates; no trend claims |
| Hour-of-day counts (limited) | Describe time-of-day distribution | `hour` | small histogram | Descriptive clustering only | Bursts dominate; time zone unverified |
| Weekday counts (limited) | Sample coverage description | `day_name` | table | Which weekdays occur | Two or three occurrences each; no pattern claims |
| Deleted count and same-date/same-second clusters | Distinguish bulk deletion from activity | `is_deleted`, `datetime` | timeline layer / table | Deletions occur in bursts | Reasons unknown |
| Forwarded count and share | Describe forwarded content | `is_forwarded` | table | a few user rows | Author unknown, one sender |
| Repeat statistics (unique / repeat / groups / sizes) | Separate repetition from lexical variety | `is_repeat`, `text_masked` | table + small bar | text = unique + repeats | Depends on the masking rule |
| URL presence count | Describe link sharing | `has_url` | table | a few text messages | Links never shown |
| Sender counts (pseudonymised, descriptive) | Give context on authorship | `sender` → pseudonym | small table with dominance note | One sender wrote almost all user rows | Not comparable across senders |
| System-message categories | Describe export events | pattern of `message` (system rows) | small table | Mostly security-code events | Small counts; text never shown |
| Text-length distribution (limited) | Describe message sizes | `message` length / token count | table of summary statistics | Mostly short messages plus two long notices | Two long messages dominate |

## 10. Proposed Visualisations

A small set, each answering a stated question and explainable in a viva:

1. **Row composition stacked bar** (user / system / header, with user rows split into text / media /
   deleted): answers RQ1 and sets the context for the NLP results.
2. **Daily activity timeline** over the full calendar range, stacked by row kind: answers RQ2.
3. **Repetition summary** (text = unique + repeats, with template group sizes): links the
   analytics to the n-gram and TF-IDF interpretation (RQ4).
4. **Metadata summary table** (forwarded, media types, URL presence, deleted, system categories, sender
   counts with dominance note): a table, not a chart, for the descriptive metadata.

Optional appendix material only, not dashboard charts: hour-of-day histogram and weekday table
(section 2 limits).

Deliberately **not** proposed: per-sender comparison charts, weekday/period charts, message-length
trend, word clouds, network or "who replies to whom" graphs (the data have almost no exchanges).

## 11. Dataset Limitations

- **Few real text messages:** most parsed rows are system, media or deleted rows.
- **Sender imbalance:** almost all user rows and text messages come from one sender.
- **Announcement-heavy chat:** mostly invitations, requests and notices; no discussion, replies or
  turn-taking to analyse.
- **Short time span:** only a few weeks of timestamps (few
  active dates). This is too short for trends and weekly cycles.
- **Concentration:** one date holds a large share of the user rows.
- **Repeated messages:** a share of the text messages repeat earlier ones.
- **Mixed language:** English and Marathi (Devanagari) text; length and token counts are approximate for
  Devanagari.
- **System and media rows:** system rows and media placeholders carry no analysable text.
- **Timestamps:** time zone and device locale of the export are unverified.
- Everything reported is descriptive of this sample and not generalisable.

## 12. Evaluation / Validation

Analytics are validated by **data-quality checks**, not model metrics.

1. **Row reconciliation:** user + system + header = parsed rows (the counts reconcile exactly).
2. **User-row reconciliation:** text + media + deleted = user rows (text + media + deleted = user rows).
3. **Text reconciliation:** unique + repeat = text messages (unique + repeats = text messages).
4. **Media reconciliation:** media-type counts sum to media rows (the counts reconcile exactly).
5. **Sender reconciliation:** per-pseudonym counts sum to user rows (the counts reconcile exactly); text-by-sender sums
   to the text-message total.
6. **Metadata reconciliation:** forwarded = text + media; URL message count agrees with the analysis-layer
   flag; system categories sum to the system-row count.
7. **Timeline reconciliation:** daily counts (zero-filled) sum to the timestamped rows; active plus
   empty dates cover the calendar range; per-kind daily counts sum to the kind totals.
8. **Repetition reconciliation:** group sizes sum to repeated + first-occurrence rows; results agree with
   `is_repeat` and the TF-IDF unique-variant N.
9. **Cross-check with existing outputs:** counts agree with the existing n-gram and TF-IDF metadata
   (text messages, unique texts, repeats).
10. **Privacy:** no phone numbers, personal names, sender values, URLs or raw message/system text in any
    output (the leak test loads these from the raw data at test time).
11. **Pseudonym consistency:** pseudonym mapping is deterministic and the crosswalk with existing
    `Sender_N` labels is validated.
12. **Determinism:** two runs give byte-identical output.
13. **Non-interference:** `data/chat.txt`, `processed_chat.csv`, existing n-gram and TF-IDF outputs, and
    existing tests are unchanged (md5 checks).
14. **Edge cases:** empty categories, dates with no rows, and single-row groups handled without error.

## 13. Final Scope Decision

| Candidate analysis | Decision | Reason |
|---|---|---|
| Row composition (user / system / header; text / media / deleted) | **IMPLEMENT** | Directly answers RQ1 and contextualises the NLP results |
| Daily activity timeline (zero-filled calendar, stacked by kind) | **IMPLEMENT** | Answers RQ2; robust at date level; empty dates visible |
| Repetition analysis (exact vs template repeats, group sizes) | **IMPLEMENT** | Central to interpretation of the n-gram and TF-IDF results (RQ4) |
| Forwarded metadata (count, share, text vs media) | **IMPLEMENT** | Cheap, already-supported field; needed for separate reporting |
| Media types, deleted counts, URL presence | **IMPLEMENT** | Simple, verifiable counts from existing fields |
| System-message categories | **IMPLEMENT** (generic categories only) | Small, descriptive, privacy-safe when text is not shown |
| Sender counts | **LIMITED / DESCRIPTIVE ONLY** | Context only; no comparative claims (section 3) |
| Hour-of-day histogram | **LIMITED / DESCRIPTIVE ONLY** | Bursty, unverified time zone; appendix only |
| Weekday table | **LIMITED / DESCRIPTIVE ONLY** | Two or three occurrences per weekday; table only |
| Text-length distribution | **LIMITED / DESCRIPTIVE ONLY** | Two long messages dominate; summary statistics only |
| Period (morning/afternoon/evening/night) | **EXCLUDE** | No added information over hour; arbitrary cut-offs |
| Message length over time | **EXCLUDE** | a few texts over a handful of dates; no trend can be supported |
| Per-sender comparisons (length, vocabulary, activity patterns) | **EXCLUDE** | one dominant sender; unsupported |
| Reply / interaction network | **EXCLUDE** | Almost no exchanges in an announcement chat |

## 14. Viva Explanation

> "For conversation analytics I chose a small set of analyses that the data can actually support. The
> parsed export has many rows, but only a few are real text, so I first show the composition: user, system,
> media, deleted, forwarded. I then show a daily activity timeline, and a repetition analysis, because
> announcement-style repetition shapes the n-gram and TF-IDF results: a share of the text messages repeat.
> I kept sender information as descriptive context only, because almost all user rows come from one sender,
> so comparing people would be misleading. I excluded analyses such as message length over time, time-of-day
> periods and reply networks because there is too little data or no real conversation. Everything is
> reported as counts with denominators, is checked with reconciliation tests, and uses pseudonyms so no
> phone numbers, names, links or message text appear."

## 15. Rubric Alignment

- **Methodology & Implementation (15):** each analysis is selected against the data with a stated
  question, field, metric and limitation; unsupported analyses are explicitly excluded; validation is by
  reconciliation and privacy tests; the design reuses existing parsed metadata (no duplicate
  preprocessing) and surfaces a real pseudonym-consistency risk before implementation.
- **Analysis, Results & Interpretation (10):** a small number of clear visuals (composition, timeline,
  repetition summary, metadata table) that directly answer RQ1, RQ2 and RQ4, plus a metadata table for
  the descriptive facts, with interpretation limited to what counts can support.
- **Conclusion & Future Work:** documents the limits (tiny sample, sender imbalance, short time span,
  announcement content) and defines what a larger or more conversational dataset would allow:
  sender comparisons, reply and turn-taking analysis, weekday and hour patterns.

## Implementation shape

A new `src/conversation_analytics.py` reading `processed_chat.csv` (read-only) and the analysis
layer, writing a few small anonymised CSVs and a metadata JSON, for example `results/analytics_*.csv`,
with tests written before results are generated. No dashboard code is part of this step.
(Implemented as described; see the final section.)

---

## Conversation Analytics Implementation Decision

**Recommended (by this design note): implement the analyses marked IMPLEMENT in section 13, report the
LIMITED / DESCRIPTIVE ONLY items as small tables with captions, and exclude the EXCLUDE items.**
**Before implementation, resolve the pseudonym-consistency point in section 8.**

**Review outcome (approved with three required changes), as implemented:**
1. The new module uses an independent `Participant_N` pseudonym scheme (first appearance across all
   user rows). The NLP `Sender_N` labels are not reused, and no crosswalk to real identities (or to
   `Sender_N`) is created or written.
2. Privacy leak tests are required and were added (`tests/test_conversation_analytics.py`): outputs
   are tested for phone numbers, personal names from system messages, invite/access URLs, raw sender
   identifiers, and raw message/system text. The forbidden values are loaded from the raw data at test
   time and are never stored.
3. The approved scope was kept exactly as documented in section 13, with no added analytics or
   dashboard features.

**Status: IMPLEMENTED**

Implemented in `src/conversation_analytics.py`. Ten result files were generated under `results/`
(`analytics_*.csv` and `analytics_run_metadata.json`); 28 reconciliation checks pass; the full test
suite passes (58 passed, 0 failed). No dashboard components were built and no packages were
installed. Timestamps are used as written in the export; the export time zone remains unverified.


## Update from the final audit (2026-10-05)

* Timestamped lines without a sender are system rows (`supported_formats.md`); they can no longer produce an unclassified row type.
* `system_category` keeps its four generic labels: `security_code_changed`, `member_added` (added or joined), `settings_changed` (settings, group
  name, subject, description or icon) and `other_system_event` (everything else, including left/removed and encryption notices).
* Metadata wording is generic ("this chat only"), not "small chat".
