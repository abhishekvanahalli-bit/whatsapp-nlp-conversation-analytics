# data/

| File | In Git? | What it is |
|---|---|---|
| `sample_chat.txt` | yes | A **fictional** 12-participant group chat (a copy of `tests/fixtures/group_12.txt`). All names, numbers and links are invented. Used as the default input of the command-line scripts and in the documentation. |
| `chat.txt` (or any other export you place here) | **no** (ignored) | A real WhatsApp export. It stays on your own machine. `.gitignore` excludes everything in this folder except this README and `sample_chat.txt`. |

Rules for this project:

* Never commit a real chat export, a screenshot of one, or any file generated from one.
* To analyse a private chat, upload it in the dashboard (it is processed in a temporary folder that is deleted
  afterwards) or run `python scripts/run_full_pipeline.py --input data/chat.txt --out local_private/results`
  (`local_private/` is ignored by Git).
* To create more fictional data, run `python scripts/generate_synthetic_fixtures.py` (see `tests/fixtures/`).
