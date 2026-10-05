# results/

Outputs of the analysis pipeline.

* `results/sample/` (committed): the 26 output files produced from the fictional `data/sample_chat.txt` with
  `python scripts/run_full_pipeline.py --input data/sample_chat.txt --out results/sample`. They show the exact output
  format. Some of them (`processed_chat.csv`, `analysis_corpus.csv`, `tfidf_terms_by_message.csv`, `key_terms.csv`)
  are INTERNAL tables that contain message text or terms; they are safe here only because the chat is fictional.
* Everything else in `results/` is ignored by Git. Do not write results of a **private** chat to `results/sample/`;
  use `local_private/results` (also ignored).

The dashboard never reads this folder. It runs the same modules in a temporary directory per upload and shows only
anonymised, display-filtered tables.
