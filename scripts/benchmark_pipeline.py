"""
Measure how the (unchanged) analysis pipeline scales on synthetic chats.

Usage:  python scripts/benchmark_pipeline.py [size ...]

Prints wall-clock seconds per stage on THIS machine for synthetic chats with
the given numbers of text messages (default sizes below). The numbers are
measurements, not guarantees: they depend on hardware and on the content. They
are used to set the configurable limits in src/app_config.py and are recorded
in docs/dashboard_implementation.md.
"""

import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import demo_data  # noqa: E402
from app_config import AppConfig  # noqa: E402
from run_pipeline import run_pipeline  # noqa: E402

DEFAULT_SIZES = (25, 100, 300, 1000, 2000, 3000)


def main(sizes):
    unlimited = AppConfig(max_upload_mb=1024, max_parsed_rows=10**9, max_text_messages=10**9)
    run_pipeline(demo_data.build_demo_chat().encode("utf-8"), "warmup.txt", unlimited)  # import warm-up
    print(f"{'text msgs':>9} {'file KB':>8} {'total s':>8} {'tfidf s':>8} {'analytics s':>11} {'ngram s':>8}")
    for n in sizes:
        data = demo_data.build_synthetic_chat(n).encode("utf-8")
        t = time.perf_counter()
        result = run_pipeline(data, f"synthetic_{n}.txt", unlimited)
        total = time.perf_counter() - t
        s = result.stage_seconds
        print(f"{n:>9} {len(data) / 1024:>8.0f} {total:>8.2f} {s['TF-IDF']:>8.2f} "
              f"{s['Conversation analytics']:>11.2f} {s['N-gram analysis']:>8.2f}", flush=True)


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or DEFAULT_SIZES)
