"""
Run every validated analysis step on one WhatsApp export and write ALL outputs (including the internal
tables) to a chosen directory. Used by scripts/run_full_pipeline.py (reproducible command-line run) and by the
tests. The dashboard uses run_pipeline.py instead, which runs the same modules in a temporary directory and
loads only the anonymised tables.

    parse -> preprocess -> n-grams -> TF-IDF -> Script Mix -> Key Terms -> conversation analytics

No calculation lives here; each step is the module's own run function.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conversation_analytics as ca  # noqa: E402
import key_terms as kt  # noqa: E402
import ngram_analysis as ng  # noqa: E402
import preprocessor as pp  # noqa: E402
import script_mix_analysis as sm  # noqa: E402
import tfidf_analysis as tf  # noqa: E402

STEPS = ("parse and preprocess", "n-grams", "TF-IDF", "Script Mix", "Key Terms", "conversation analytics")


def run_all_steps(chat_path, out_dir, progress=None):
    """Run all steps. Returns (dataframe, parsing_failures, seconds_per_step). `out_dir` must exist.
    progress(step_name) is called before each step."""
    say = progress or (lambda name: None)
    out_dir = Path(out_dir)
    seconds = {}

    def timed(name, fn):
        say(name)
        t = time.perf_counter()
        result = fn()
        seconds[name] = round(time.perf_counter() - t, 3)
        return result

    df, failures = timed(STEPS[0], lambda: pp.build_dataset(chat_path))
    processed = out_dir / "processed_chat.csv"
    pp.save_processed_csv(df, processed)
    timed(STEPS[1], lambda: ng.run_analysis(processed, out_dir))
    timed(STEPS[2], lambda: tf.run_tfidf(processed, out_dir, out_dir))
    timed(STEPS[3], lambda: sm.run_script_mix(processed, out_dir, out_dir))
    timed(STEPS[4], lambda: kt.run_key_terms(processed, out_dir, out_dir))
    timed(STEPS[5], lambda: ca.run_analytics(processed, out_dir, out_dir))
    return df, failures, seconds
