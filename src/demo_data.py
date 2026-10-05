"""
Synthetic, privacy-safe chat data for the dashboard's demo mode and for tests /
benchmarks. Everything here is invented: made-up names, example.com links, no
real phone numbers, and no text from any real chat. The real project chat is
never used as demo data.

Both generators produce the bracketed export format the parser supports
("[M/D/YY, H:MM:SS AM/PM] Sender: message").
"""

import random

DEMO_FILENAME = "synthetic_demo_chat.txt"
HEADER = ("Messages and calls are end-to-end encrypted. No one outside of this chat, "
          "not even WhatsApp, can read or listen to them.")

_ALEX, _SAM, _JO = "Alex Demo", "Sam Sample", "Jo Placeholder"
_INVITE = "Open this link to join the Demo Club group: https://example.com/join/{code}"

# (month, day, "h:mm:ss AM/PM", sender or None for system, text)
_DEMO_SCRIPT = [
    (3, 10, "9:00:00 AM", None, f"- {_ALEX} created this group"),
    (3, 10, "9:01:10 AM", None, f"- {_ALEX} added {_SAM}"),
    (3, 10, "9:01:12 AM", None, f"- {_ALEX} added {_JO}"),
    (3, 10, "9:05:00 AM", _ALEX, "Welcome everyone to the demo club chat"),
    (3, 10, "9:06:30 AM", _SAM, "Thanks for adding me, happy to be here"),
    (3, 10, "9:07:45 AM", _ALEX, _INVITE.format(code="a1b2")),
    (3, 10, "9:08:20 AM", _ALEX, _INVITE.format(code="c3d4")),
    (3, 10, "9:09:05 AM", _ALEX, _INVITE.format(code="e5f6")),
    (3, 10, "9:15:00 AM", _JO, "<image omitted>"),
    (3, 11, "6:30:00 PM", _ALEX, "Practice starts at 6 pm at the community ground. Please confirm your attendance."),
    (3, 11, "6:32:10 PM", _SAM, "Confirmed, I will be there"),
    (3, 11, "6:35:44 PM", _JO, "Confirmed as well"),
    (3, 12, "7:00:00 AM", _ALEX, "सर्वांनी कृपया वेळेवर यावे"),
    (3, 12, "7:01:00 AM", _ALEX, "उद्या सराव आहे, please be on time"),
    (3, 12, "8:20:00 PM", _SAM, "<video omitted>"),
    (3, 13, "10:10:10 AM", _JO, "Great session today, thanks everyone"),
    (3, 13, "10:12:00 AM", _SAM, "Agreed, the warm up drills were useful"),
    (3, 13, "10:30:00 AM", _ALEX, "Please share your jersey size and preferred number"),
    (3, 13, "10:31:00 AM", _SAM, "Medium and number seven"),
    (3, 13, "10:33:00 AM", _JO, "Large, any number is fine"),
    (3, 14, "5:00:00 PM", _ALEX, "This message was deleted"),
    (3, 14, "5:02:00 PM", _ALEX, "Practice starts at 6 pm at the community ground. Please confirm your attendance."),
    (3, 14, "5:10:00 PM", _JO, "[Forwarded] Weekend workshop schedule is attached below"),
    (3, 14, "5:11:00 PM", _JO, "<album message>"),
    (3, 15, "9:45:00 AM", None, f"- {_ALEX} changed settings: only admins can send messages"),
    (3, 15, "10:00:00 AM", _ALEX, "Team update:\nSaturday practice moved to the north field.\nBring water and shoes."),
    (3, 16, "8:00:00 AM", _ALEX, "Please share your jersey size and preferred number"),
    (3, 16, "8:05:00 AM", _SAM, "<image omitted>"),
    (3, 17, "11:00:00 AM", _ALEX, "सर्वांनी कृपया वेळेवर यावे"),
    (3, 17, "11:02:00 AM", _JO, "Will do, see you at the ground"),
    (3, 18, "6:00:00 PM", _ALEX, "Practice starts at 6 pm at the community ground. Please confirm your attendance."),
    (3, 18, "6:05:00 PM", _SAM, "<unknown message>"),
    (3, 18, "6:06:00 PM", _JO, "Confirmed again"),
    (3, 19, "9:00:00 AM", _ALEX, "This message was deleted"),
    (3, 19, "9:00:01 AM", _ALEX, "This message was deleted"),
    (3, 20, "4:30:00 PM", _SAM, "Match day photos are ready, sharing soon"),
    (3, 21, "3:15:00 PM", _ALEX, "Thanks all, great effort this week"),
]


def build_demo_chat():
    """The fixed demo chat as export text (about 40 rows, English plus Devanagari)."""
    lines = [HEADER]
    for month, day, clock, sender, text in _DEMO_SCRIPT:
        stamp = f"[{month}/{day}/25, {clock}]"
        lines.append(f"{stamp} {text}" if sender is None else f"{stamp} {sender}: {text}")
    return "\n".join(lines) + "\n"


_WORDS = ("practice ground team session drill match photo update schedule water shoes field "
          "morning evening coach captain ready confirm plan today tomorrow thanks great useful "
          "warm cool quick slow group club demo training camp roster jersey number size").split()


def build_synthetic_chat(n_text_messages, seed=0, n_senders=3, repeat_every=7):
    """A deterministic chat with about n_text_messages text messages plus some media,
    deleted and system rows; every `repeat_every`-th message repeats a template.
    Used for tests and for measuring pipeline scaling (scripts/benchmark_pipeline.py)."""
    rng = random.Random(seed)
    senders = [f"Person {chr(65 + i)}" for i in range(n_senders)]
    lines = [HEADER, "[1/1/25, 8:00:00 AM] - Person A created this group"]
    clock_seconds = 8 * 3600
    for i in range(n_text_messages):
        clock_seconds += rng.randint(5, 900)
        day = 1 + (clock_seconds // 86400)
        month = 1 + (day - 1) // 28
        day = 1 + (day - 1) % 28
        secs = clock_seconds % 86400
        hour24, minute, second = secs // 3600, (secs % 3600) // 60, secs % 60
        hour12 = hour24 % 12 or 12
        stamp = f"[{month}/{day}/25, {hour12}:{minute:02d}:{second:02d} {'AM' if hour24 < 12 else 'PM'}]"
        sender = senders[rng.randrange(n_senders)]
        if i % repeat_every == 0:
            text = "Practice starts at six at the ground, please confirm your attendance"
        else:
            text = " ".join(rng.choice(_WORDS) for _ in range(rng.randint(4, 14)))
        lines.append(f"{stamp} {sender}: {text}")
        if i % 11 == 0:
            lines.append(f"{stamp} {sender}: <image omitted>")
        if i % 37 == 0:
            lines.append(f"{stamp} {sender}: This message was deleted")
    return "\n".join(lines) + "\n"
