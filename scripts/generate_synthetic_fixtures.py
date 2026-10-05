"""
Generate the larger FICTIONAL test chats in tests/fixtures/ (deterministic: fixed seeds).

Everything here is invented: participant names, phone numbers (+91 9000x xxxxx style placeholders),
links (example.com / example.org and a made-up invite code) and message text. No real chat, name,
number or link is used or copied. Run from the project root:

    python scripts/generate_synthetic_fixtures.py

The smaller, hand-written fixtures (parser_*.txt, media_deleted.txt, privacy_cases.txt, numeric_terms.txt,
zero_text.txt) are committed as plain text and are not produced by this script.
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
LRM = "‎"
NOTICE = LRM + "Messages and calls are end-to-end encrypted. Only people in this chat can read them."

ENGLISH = [
    "see you at the ground at five", "please confirm the number of players", "thanks a lot for the update",
    "ok will join the call", "lunch today anyone?", "the meeting starts at ten please be on time",
    "sent the document to everyone", "good morning team", "practice is cancelled tomorrow",
    "who is bringing the equipment", "reached the venue", "great game today well played",
    "please share the schedule for next week", "running late will be there soon",
    "can someone send the location", "happy birthday have a great day", "the match is on saturday",
    "bring water and snacks", "booking confirmed for the hall", "reminder: fees are due this friday",
]
MARATHI = ["आज सराव आहे", "कृपया उपस्थित रहा।", "धन्यवाद सर्वांचे", "उद्या भेटू", "वेळेत या", "सामना शनिवारी आहे।"]
HINDI = ["कल मैच है", "सब लोग समय पर आना।", "शुक्रिया दोस्तों", "आज प्रैक्टिस नहीं होगी"]
ROMAN = ["kal practice hai kya", "mala sangaa please", "ho barobar", "aaj nahi yenar", "sab log aa rahe ho na",
         "tumhi kadhi yenar", "thik hai bhai"]
MIXED = ["आज practice आहे please come", "tumhi ready ahat ka? ok", "match उद्या ahe, bring water",
         "ठीक hai see you there"]
EMOJI = ["\U0001F44D", "\U0001F600\U0001F600", "\U0001F64F", "❤️", "well done \U0001F389"]
POOL = ENGLISH * 2 + MARATHI + HINDI + ROMAN + MIXED + EMOJI
FORWARDS = ["[Forwarded] Weekly schedule: practice on Monday and Thursday", "[Forwarded] Reminder to carry ID cards"]


def stamp(dt):
    h = dt.hour % 12 or 12
    return f"[{dt.month}/{dt.day}/{dt.strftime('%y')}, {h}:{dt.minute:02d}:{dt.second:02d} {'AM' if dt.hour < 12 else 'PM'}]"


def build(names, n_messages, seed, start, n_days, system_events=True, lrm_system=False, phone_sender=None):
    rng = random.Random(seed)
    lines = [NOTICE]
    t = start
    senders = list(names)
    if phone_sender:
        senders.append(phone_sender)
    if system_events:
        lines.append(f"{stamp(t)} - {senders[0]} created this group")
        lines.append(f"{stamp(t)} {LRM if lrm_system else ''}{senders[0]} added {senders[-1]}")
        lines.append(f"{stamp(t)} - {senders[-1]}'s security code changed. Tap to learn more.")
    step = timedelta(days=n_days) / max(n_messages, 1)
    for i in range(n_messages):
        t = start + step * i + timedelta(seconds=rng.randint(0, 3000))
        who = rng.choice(senders)
        roll = rng.random()
        if roll < 0.06:
            body = "<image omitted>"
        elif roll < 0.09:
            body = "This message was deleted"
        elif roll < 0.12:
            body = rng.choice(FORWARDS)
        elif roll < 0.16:
            body = f"details here https://example.com/demo?id={rng.randint(1, 5)}"
        elif roll < 0.18:
            body = "call me on +91 90000 12345 later"
        elif roll < 0.21:
            body = "first line of a note\nsecond line\n\nlast line after a blank line"
        elif roll < 0.25:
            body = rng.choice(POOL[:6])                         # frequent repeats
        else:
            body = rng.choice(POOL)
        prefix = LRM if (lrm_system and roll < 0.06) else ""
        lines.append(f"{prefix}{stamp(t)} {who}: {body}")
        if system_events and i in (n_messages // 3, 2 * n_messages // 3):
            lines.append(f"{stamp(t)} - {senders[1 % len(senders)]} left")
            lines.append(f"{stamp(t)} {senders[0]} changed the group name to “Fictional Team {i}”")
    return "\n".join(lines) + "\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    one = ["Alex Demo", "Sam Sample"]
    group12 = ["Alex Demo", "Sam Sample", "Riya Testwala", "Kabir Fictional", "Meera Imaginary", "Dev Placeholder",
               "Anya Mockson", "Zoya Samplewala", "Vikram Dummy", "Tara Fakenham", "Omkar Testkar", "Isha Demoji"]
    group30 = [f"Member {i:02d} Fictional" for i in range(1, 31)]
    (OUT / "one_to_one.txt").write_text(
        build(one, 70, 11, datetime(2026, 3, 10, 9, 0), 6, system_events=False), encoding="utf-8")
    (OUT / "group_12.txt").write_text(
        build(group12, 160, 12, datetime(2026, 3, 10, 8, 30), 12, lrm_system=True), encoding="utf-8")
    (OUT / "group_30.txt").write_text(
        build(group30, 130, 13, datetime(2026, 2, 27, 9, 0), 9, phone_sender="+91 90000 00001"), encoding="utf-8")
    (OUT / "single_sender.txt").write_text(
        build(["Solo Fictional"], 32, 14, datetime(2026, 4, 1, 10, 0), 3, system_events=False), encoding="utf-8")
    print("written:", sorted(p.name for p in OUT.glob("*.txt")))


if __name__ == "__main__":
    main()
