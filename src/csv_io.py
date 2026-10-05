"""
Typed CSV reading for the analysis modules.

pandas' default CSV reader guesses types and treats words such as "None", "NA", "null" or "nan"
as missing values. Both are wrong for a text-analysis pipeline: the term 007 must not become 7, a
chat consisting only of numbers must not turn text columns into integers, and a message that is
literally "None" must stay text. This module reads text and term columns as strings and treats ONLY an
empty field as missing. It does not change any calculation.
"""

import pandas as pd

TEXT_COLUMNS = ("message", "clean_message", "tokens", "tokens_no_stopwords", "sender", "date_str",
                "time_str", "text_masked", "sender_anon", "media_type", "term", "ngram")


def read_csv_typed(path, **kwargs):
    """Read a pipeline CSV: text/term columns as str, only empty fields are NaN."""
    header = pd.read_csv(path, nrows=0, encoding="utf-8").columns
    dtype = {c: str for c in header if c in TEXT_COLUMNS}
    return pd.read_csv(path, encoding="utf-8", dtype=dtype, keep_default_na=False, na_values=[""], **kwargs)
