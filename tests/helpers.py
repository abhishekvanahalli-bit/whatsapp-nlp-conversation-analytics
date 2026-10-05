"""Shared test helpers: fictional fixtures and a once-per-session pipeline run on a synthetic chat.

The generic tests run on the committed FICTIONAL chats in tests/fixtures/. They never need the private
development chat (data/chat.txt); tests that do live in test_private_sample_regression.py and are skipped
when that file is absent.
"""

import atexit
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
for extra in (ROOT / "src", ROOT / "app", ROOT / "tests"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from pipeline_steps import run_all_steps  # noqa: E402

_cache = {}


def fixture_bytes(name):
    return (FIXTURES / name).read_bytes()


def outputs_for(name):
    """Directory holding every pipeline output for tests/fixtures/<name> (built once per test session)."""
    if name not in _cache:
        out = Path(tempfile.mkdtemp(prefix=f"wa_test_{Path(name).stem}_"))
        atexit.register(shutil.rmtree, out, ignore_errors=True)
        run_all_steps(FIXTURES / name, out)
        _cache[name] = out
    return _cache[name]


# The general-purpose sample used by the module-level pipeline tests: a fictional 12-participant group.
SAMPLE_CHAT = FIXTURES / "group_12.txt"
SAMPLE_DIR = outputs_for("group_12.txt")
SAMPLE_CSV = SAMPLE_DIR / "processed_chat.csv"


def corpus_counts(out_dir=None):
    """(messages, unique texts, repeat messages) of the analysis corpus in a pipeline output directory."""
    import pandas as pd
    corpus = pd.read_csv((out_dir or SAMPLE_DIR) / "analysis_corpus.csv", keep_default_na=False)
    repeats = int(corpus["is_repeat"].astype(str).str.lower().eq("true").sum())
    return len(corpus), len(corpus) - repeats, repeats
