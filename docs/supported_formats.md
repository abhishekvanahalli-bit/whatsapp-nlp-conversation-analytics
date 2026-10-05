# Supported WhatsApp export format

This project does **not** claim to read every WhatsApp export. It supports one precisely defined text format and rejects
everything else with a clear message. This page states what is supported, how each rule is implemented
(`src/preprocessor.py`, `src/run_pipeline.py`), what was verified, and what is not supported.

## 1. The supported format

A UTF-8 `.txt` file ("Export chat" → "Without media") in which every message starts a new line with a bracketed timestamp:

```
[M/D/YY, H:MM:SS AM/PM] Sender: message text          user row
[M/D/YY, H:MM:SS AM/PM] - system text                 system row ("- " style)
[M/D/YY, H:MM:SS AM/PM] system text                   system row (no sender)
```

| Element | Rule |
|---|---|
| Timestamp | `[M/D/YY, H:MM:SS AM/PM]`: month and day without padding allowed, **two-digit year**, seconds present, 12-hour clock with upper-case `AM`/`PM`. A normal space or a narrow no-break space before AM/PM is accepted. |
| Date order | **Month/Day/Year** only (see section 3). |
| First line | An optional **untimed** first line (the end-to-end-encryption notice) is stored as a `header` row. A timestamped encryption notice is a system row. |
| User row | `Sender: message`, split at the **first** `": "`. Sender names are taken literally (a name or a phone number). |
| System row | After the timestamp: `- text`, or any text without a `": "`. System text is reduced to four generic categories (security code changed, member added/joined, settings or group-info changed, other) and never displayed. |
| System sentence with a colon | `Alex changed the subject from "Plan: A" to "Plan: B"` contains `": "` but is not a message. A part before the colon is treated as a system sentence only when it contains a system verb (added, left, joined, created, changed, removed, ...) **and** has four or more words or a quotation mark. Otherwise the line is a user row. |
| Continuation lines | Any line that does not start with a timestamp belongs to the previous row (multi-line messages, blank lines inside a message). A message that merely *contains* `[3/10/26, 9:00:00 AM]` somewhere in its text stays one message. |
| Invisible marks | U+200E, U+200F, U+202A-202E, U+2066-2069 and U+FEFF before the bracket (common in iOS-style exports) are ignored when a new row is detected, and are removed from cleaned text. |
| Line endings | LF and CRLF. The file's final newline is not part of the last message. |

## 2. Placeholders that are not text

Placeholder rows are counted as **media** or **deleted** rows and never enter the NLP corpus.

| Kind | Recognised when | Examples |
|---|---|---|
| Bracketed media placeholders | the message **contains** the marker (a caption on the same row is ignored) | `<image omitted>`, `<video omitted>`, `<audio omitted>`, `<sticker omitted>`, `<GIF omitted>`, `<document omitted>`, `<Media omitted>`, `<unknown message>`, `<album message>`, `<attached: 0001-PHOTO.jpg>` |
| Bare media placeholders (iOS wording) | the **whole** message is the placeholder | `image omitted`, `sticker omitted`, `audio omitted`, `GIF omitted`, `document omitted`, `Contact card omitted`, `Missed voice call`, `Voice call, 2 min` |
| Deleted messages | the message **starts with** the wording (an optional leading symbol is allowed) | `This message was deleted`, `You deleted this message`, `This message was deleted by admin ...` |
| Forwarded | the message starts with `[Forwarded]` (kept as a flag, removed from the NLP text) | |
| Edited | a trailing `<This message was edited>` is removed from the NLP text (the message stays text) | |

Ordinary sentences that mention a bare placeholder (`I said image omitted yesterday`, `the file was deleted by mistake`) stay text.
A one-to-three word message ending in "omitted" that matches none of the above is counted as text and triggers a warning.
Call rows (`Missed voice call`) are counted as media rows because they carry no text; the dashboard label "Media / Deleted"
therefore means "non-text placeholders".

## 3. Date order and time zone

* Dates are read as **Month/Day/Year**. The file is rejected when this reading is impossible or unsafe:
  * a first number above 12 appears (Day/Month export) -> error `date_order_unsupported`;
  * both numbers exceed 12 in some rows -> error `date_order_inconsistent`;
  * no timestamp can be read at all -> error `dates_invalid`.
* When **every** month/day value is 12 or below, the date order cannot be confirmed from the data. The file is analysed, but a
  prominent warning says that, for a Day/Month export, every date, the timeline and the weekday table would be wrong.
* Timestamps are shown **as recorded**. The time zone of the export is unknown and is never assumed.

## 4. What was verified

| Evidence | What it shows |
|---|---|
| A private Android-style development export (not in the repository) | Parsing, all analyses and the dashboard on real data; aggregate results unchanged by the final fixes (a local-only, git-ignored regression test). |
| Fictional fixtures in `tests/fixtures/` | One-to-one, 12- and 30-participant groups, single sender, zero text, system events, Unicode and invisible marks, media and deleted placeholders (Android and iOS wording), numeric terms, privacy cases. |
| iOS-style conventions | Verified **only on fictional fixtures that imitate them** (invisible marks before the bracket, sender-less system lines, bare placeholders). **No real iOS export was available**, so real iOS compatibility is not claimed. |

## 5. Not supported (rejected with a message, or documented)

| Input | Behaviour |
|---|---|
| Android style without brackets: `3/10/25, 9:05 AM - Name: text` | Rejected (`unsupported_format`). |
| 24-hour clock, timestamps without seconds, four-digit years (`[3/10/2025, 9:05:00 AM]`) | Rejected (`unsupported_format`). |
| Day/Month/Year dates | Rejected when a first number exceeds 12; ambiguous (warning only) otherwise. |
| Lower-case or localised am/pm markers, non-Latin digits | Not recognised, so the file is rejected. |
| Non-UTF-8 files (for example UTF-16), `.crypt` backups, `.zip` exports | Rejected (`not_utf8`, `wrong_type`). |
| Media files, captions on the same row as a bracketed placeholder | Not read; the caption is not analysed. |
| Other placeholder wording (other languages, polls, live location, ...) | Counted as text. Only "omitted"-style one-to-three word lines trigger a warning. |

### Why Android support was not added

Android exports follow the device locale: date order (D/M/Y or M/D/Y), two- or four-digit years, and 12- or 24-hour clocks all vary,
and the bracket-free line shape `date, time - Sender: text` cannot be told apart from message text as safely as a leading `[`.
Supporting it correctly needs several regular expressions plus date-order inference for each, and none could be verified on real files
here. Adding a partial reader would risk silently misreading dates, which this project rules out, so it stays unsupported and documented.
Adding it later means: new line patterns, a date-order detector, fixtures for each variant, and tests.

## 6. Parser limits worth knowing

* A sender name that itself contains `": "` is split at the first `": "` (inherent ambiguity of the format).
* A user message that starts a line with a bracketed timestamp would be read as a new row (inherent to all line-based parsers).
* The system-sentence rule is a heuristic; a participant whose display name contains a system verb and four or more words could be
  read as a system event (not observed).
* Two-digit years are read as 20YY by pandas' two-digit-year rule.
