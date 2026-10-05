# Documentation index

Start with the first group; the others are design and research notes kept as the project history.

## Current state (read these first)

| Page | Content |
|---|---|
| [`supported_formats.md`](supported_formats.md) | The one supported export format, recognised placeholders, date-order rules, unsupported formats, parser limits |
| [`final_audit_fixes.md`](final_audit_fixes.md) | Problems found by the master audit, the fix and regression test for each, expected differences in results |
| [`final_verification.md`](final_verification.md) | What was tested and how: generalisation matrix, analytical validity, privacy, performance, clean install, reproducible run, browser review |
| [`project_freeze.md`](project_freeze.md) | Frozen scope, module map, final test status, limitations |
| [`dashboard_implementation.md`](dashboard_implementation.md) | How the dashboard is built, including the final light redesign and the theme image |

## Design notes (written during development)

These describe the private development chat and the results at that time; the pages above win where they differ.

* [`project_plan.md`](project_plan.md): milestones, rubric alignment, history
* [`tfidf_design.md`](tfidf_design.md), [`conversation_analytics_design.md`](conversation_analytics_design.md), [`language_and_keyword_design.md`](language_and_keyword_design.md)
* [`dashboard_design.md`](dashboard_design.md)

## Research notes for features that are NOT implemented

[`sentiment_design.md`](sentiment_design.md), [`emotion_sentiment_design.md`](emotion_sentiment_design.md), [`emotion_evaluation_protocol.md`](emotion_evaluation_protocol.md):
feasibility studies kept as future work. Nothing from them is in the code, dashboard, results or requirements.
