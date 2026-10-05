"""
Configurable limits and display settings for the dashboard application.

Every value can be overridden with an environment variable (see FIELDS). The
limits are protective settings, not performance guarantees: their defaults were
chosen from the measurements recorded in docs/dashboard_implementation.md
(scripts/benchmark_pipeline.py), and should be re-measured on the target
machine before deployment.
"""

import os
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class AppConfig:
    # --- protective limits (reject with a clear message when exceeded) ---
    max_upload_mb: float = 10.0        # WA_MAX_UPLOAD_MB (file size is a weak cost driver: ~95 KB per 1,000 text messages)
    max_parsed_rows: int = 10_000      # WA_MAX_PARSED_ROWS
    max_text_messages: int = 1_000     # WA_MAX_TEXT_MESSAGES (TF-IDF stability check grows ~quadratically)
    # --- limited-data warnings (never a rejection) ---
    tiny_chat_text_messages: int = 3   # WA_TINY_CHAT_TEXT_MESSAGES: rankings/stability not meaningful
    small_chat_text_messages: int = 50  # WA_SMALL_CHAT_TEXT_MESSAGES: interpret with strong caution
    # --- display layer (does not alter the underlying analysis) ---
    min_term_messages: int = 2         # WA_MIN_TERM_MESSAGES: hide terms occurring in fewer messages
    top_k_default: int = 15            # WA_TOP_K_DEFAULT

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)

    @classmethod
    def from_env(cls, environ=None):
        env = os.environ if environ is None else environ
        values = {}
        for f in fields(cls):
            raw = env.get(f"WA_{f.name.upper()}")
            if raw is None or raw == "":
                continue
            try:
                values[f.name] = f.type(raw) if callable(f.type) else float(raw)
            except (TypeError, ValueError):
                continue                                   # ignore malformed overrides
        return cls(**values)


DEFAULT_CONFIG = AppConfig()
