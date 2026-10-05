"""
Pre-commit privacy check: scan the files Git would commit for private or sensitive content.

    python scripts/check_repo_privacy.py            # check files Git would add (needs a Git repository)
    python scripts/check_repo_privacy.py --all      # check every file under the project (ignores .gitignore)

What it looks for (it prints the file, line number and KIND only, never the matched text):
  * phone numbers (international "+CC ..." and 10-digit local numbers) that are not marked fictional
  * WhatsApp invite links and wa.me links that are not marked fictional
  * http(s) URLs and e-mail addresses outside a small allow-list (example.* and documentation hosts)
  * secret-looking strings (API keys, tokens, passwords, private keys)
  * if a private export exists at data/chat.txt: its sender names, phone numbers, URLs and messages (derived in
    memory at run time; nothing about the private chat is stored in this script or printed)
  * real chat exports and archives that should never be committed (e.g. WhatsApp Chat*.txt, *.zip)

Exit code 0 = no findings. It is a safety net, not a guarantee: read `git status` and `git diff --cached` as well.
"""

import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Substrings that mark a number / link / host as one of the invented examples used in tests and fixtures.
FICTIONAL_NUMBER_MARKERS = ("9000", "11111", "22222", "33333", "44444", "99999", "88888", "555 010", "5550100", "12345", "00000", "0000",
                            "0123456789", "9876543210", "98765", "10-03-2025", "2345 6789", "6789")
FICTIONAL_LINK_MARKERS = ("FICTIONAL", "AAA", "BBB", "DEMO", "EXAMPLE", "XYZ", "SECRETCODE", "OTHER456", "ABC", "DEMO0INVITE")
ALLOWED_HOSTS = ("example.com", "example.org", "example.net", "localhost", "127.0.0.1", "github.com", "streamlit.io",
                 "plotly.com", "pandas.pydata.org", "scikit-learn.org", "python.org", "pypi.org", "huggingface.co",
                 "unicode.org", "docs.streamlit.io", "playwright.dev", "opensource.org", "w3.org", "numpy.org",
                 "x.io", "mail.com")          # x.io / mail.com: invented hosts used only in test strings
SECRET_ALLOW = ("topsecretmarker",)
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".pyc"}
NEVER_COMMIT = [re.compile(p, re.I) for p in (r"(^|/)WhatsApp Chat", r"(?<!sample)_chat\.txt$", r"(^|/)data/chat\.txt$", r"\.zip$",
                                              r"(^|/)local_private/", r"(^|/)\.env$", r"\.pem$")]

PHONE_INTL = re.compile(r"\+\d(?:[\s\-().]?\d){7,14}")
PHONE_LOCAL = re.compile(r"(?<![\d.\-/:])\d{10}(?![\d.\-/:])")
INVITE = re.compile(r"(?:chat\.whatsapp\.com|wa\.me)/(\S*)", re.I)
URL = re.compile(r"https?://([^\s/)>\]\"'`]+)", re.I)
EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
SECRETS = [("api key / token", re.compile(r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|hf_[A-Za-z0-9]{30,})")),
           ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
           ("password / secret assignment", re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*['\"][^'\"\s]{6,}['\"]"))]
LINE = re.compile(r"^‎?\[(\d{1,2})/(\d{1,2})/(\d{2}), (\d{1,2}):(\d{2}):(\d{2})\s?([AP]M)\] (.*)$")


def candidate_files(everything):
    if not everything:
        try:
            out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, check=True,
                                 capture_output=True, text=True).stdout.splitlines()
            return [ROOT / p for p in out if p]
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Not a Git repository (or git missing): checking every file; use --all to silence this note.")
    return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts]


def private_strings():
    """Strings derived from the private export (if present). Never printed."""
    path = ROOT / "data" / "chat.txt"
    if not path.exists():
        return None
    senders, sysn, msgs = set(), set(), []
    for ln in path.read_text(encoding="utf-8").split("\n"):
        m = LINE.match(ln)
        if not m:
            continue
        rest = m.group(8).lstrip("‎")
        if rest.startswith("- "):
            sysn.add(rest[2:])
        elif ": " in rest:
            s, t = rest.split(": ", 1)
            senders.add(s)
            msgs.append(t)
    phones = {x.strip() for t in msgs + list(sysn) + list(senders) for x in re.findall(r"\+\d[\d \-]{7,}\d", t)}
    urls = {x.rstrip(".,)") for t in msgs for x in re.findall(r"(?:https?://|www\.)\S+", t)}
    generic = ("omitted", "deleted", "unknown message", "album message", "missed voice call")
    texts = {t.strip().lower() for t in msgs if len(t.strip()) >= 20 and not any(g in t.lower() for g in generic)}
    sender_names = {s.lower() for s in senders if s and not re.search(r"\d{5}", s)}
    digits = {re.sub(r"\D", "", x) for x in phones | senders if len(re.sub(r"\D", "", x)) >= 8}
    return {"sender name": sender_names, "private phone": {p.lower() for p in phones}, "private phone digits": digits,
            "private URL": {u.lower() for u in urls}, "private message text": texts}


def read_text(path):
    if path.suffix.lower() == ".zip":
        try:
            z = zipfile.ZipFile(path)
            return "\n".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist())
        except zipfile.BadZipFile:
            return None
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def fictional_number(text):
    return any(m in text for m in FICTIONAL_NUMBER_MARKERS)


def scan_file(path, private):
    rel = path.relative_to(ROOT).as_posix()
    findings = []
    for pat in NEVER_COMMIT:
        if pat.search(rel):
            findings.append((rel, 0, "file that must not be committed (private export, archive, env or key file)"))
    if path.suffix.lower() in SKIP_SUFFIXES:
        return findings
    text = read_text(path)
    if text is None:
        return findings
    for i, line in enumerate(text.split("\n"), 1):
        for m in PHONE_INTL.finditer(line):
            if line[max(m.start() - 1, 0):m.start()] == "U":      # Unicode code point notation such as U+2066-2069
                continue
            if not fictional_number(m.group(0)):
                findings.append((rel, i, "phone-like number"))
        for m in PHONE_LOCAL.finditer(line):
            if not fictional_number(m.group(0)):
                findings.append((rel, i, "phone-like number"))
        for m in INVITE.finditer(line):
            code = m.group(1)
            if len(code) > 3 and not code.startswith((".", "`", "…")) and not any(k in code.upper() for k in FICTIONAL_LINK_MARKERS):   # real invite codes are ~22 characters
                findings.append((rel, i, "WhatsApp invite / wa.me link"))
        for m in URL.finditer(line):
            host = m.group(1).lower().split(":")[0]
            if host in ("chat.whatsapp.com", "wa.me"):
                continue                                       # judged by the invite-link rule above
            if not any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS):
                findings.append((rel, i, "URL outside the allow-list"))
        for m in EMAIL.finditer(line):
            if not m.group(1).lower().startswith(("example.", "mail.com", "users.noreply.github.com")):
                findings.append((rel, i, "e-mail address"))
        for kind, rx in SECRETS:
            if rx.search(line) and not any(a in line for a in SECRET_ALLOW):
                findings.append((rel, i, kind))
        if private:
            low = line.lower()
            for kind, items in private.items():
                if any(x and x in (re.sub(r"\D", "", line) if "digits" in kind else low) for x in items):
                    findings.append((rel, i, f"{kind} from the private chat"))
    return findings


def main(argv):
    everything = "--all" in argv
    private = private_strings()
    print("private chat found: scanning for its names/numbers/messages too" if private else
          "no private chat at data/chat.txt: pattern checks only")
    files = candidate_files(everything)
    findings = []
    for p in sorted(files):
        if p.is_file():
            findings += scan_file(p, private)
    for rel, line, kind in findings:
        print(f"  {rel}:{line}: {kind}")
    print(f"checked {len(files)} files; findings: {len(findings)}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
