"""
Build the optional anonymised results download (a zip created in memory).

Contents: the conversation-analytics tables and run metadata (counts, dates,
pseudonyms, generic labels), and the NLP tables AFTER the display privacy
filter. Never included: processed_chat.csv, analysis_corpus.csv, message-level
TF-IDF, raw text, senders, links.
"""

import io
import json
import zipfile

from display_privacy import prepare_display_tables

README = """Anonymised results from the WhatsApp NLP dashboard (one run).

- analytics_*.csv / analytics_run_metadata.json: conversation analytics (counts, dates, Participant_N
  pseudonyms, generic system-message categories, anonymous template ids).
- ngram_*.csv, tfidf_*.csv / tfidf_run_metadata.json, key_terms.csv: aggregate word and phrase tables.
  Terms that occur in only one message are hidden unless you chose to show them. This is a precaution,
  not complete PII detection.
- script_mix_*.csv: how many messages are written in Latin script only, Devanagari only, or both (script
  composition; it does not identify languages).

Descriptive results for one chat; not generalisable. Dates are read as Month/Day/Year as recorded
in the export; the time zone is unverified. Participant_N labels are assigned per run and have no
meaning across runs. The raw chat, sender identifiers, links and message text are not included.
"""

ANALYTICS_TABLES = ("analytics_row_composition", "analytics_metadata_counts", "analytics_daily_activity",
                    "analytics_repetition_summary", "analytics_repetition_groups",
                    "analytics_sender_counts", "analytics_hour_histogram", "analytics_weekday_table",
                    "analytics_text_length_summary")
NLP_TABLES = ("ngram_unigrams", "ngram_unigrams_with_stopwords", "ngram_bigrams", "ngram_trigrams",
              "ngram_script_diagnostics", "tfidf_top_terms", "tfidf_variant_comparison",
              "script_mix_summary", "script_mixing_stats", "key_terms")


def build_bundle(run, min_messages=2, show_single_message_terms=False):
    """Zip bytes for the current run. Uses the same display filter as the UI."""
    display, _ = prepare_display_tables(run.tables, min_messages, show_single_message_terms)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", README)
        for name in ANALYTICS_TABLES + NLP_TABLES:
            z.writestr(f"{name}.csv", display[name].to_csv(index=False))
        z.writestr("analytics_run_metadata.json",
                   json.dumps(run.analytics_meta, indent=2, ensure_ascii=False, sort_keys=True))
        z.writestr("tfidf_run_metadata.json",
                   json.dumps(run.tfidf_meta, indent=2, ensure_ascii=False, sort_keys=True))
    return buffer.getvalue()
