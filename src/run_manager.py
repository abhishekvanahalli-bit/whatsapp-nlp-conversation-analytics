"""
Session run management (no Streamlit dependency, so it is directly testable).

Rules:
- only the current SUCCESSFUL run is retained (in memory, in this object);
- a successful new upload replaces it;
- a failed new upload leaves the previous successful run visible and records
  the error;
- the same content is not processed again on Streamlit reruns;
- nothing is written to disk and nothing is shared between sessions.
"""

import hashlib

from app_config import DEFAULT_CONFIG
from run_pipeline import UserFacingError, run_pipeline


class RunManager:
    def __init__(self, config=DEFAULT_CONFIG, runner=run_pipeline):
        self.config = config
        self.runner = runner
        self.current = None          # last successful RunResult
        self.last_error = None       # UserFacingError of the last failed attempt, else None
        self._last_attempt_key = None

    def submit(self, data, filename, progress=None):
        """Process an upload. Returns 'unchanged', 'replaced' or 'failed'."""
        key = (hashlib.sha256(data).hexdigest(), str(filename))
        if key == self._last_attempt_key:
            return "unchanged"                       # rerun with the same file: do nothing
        self._last_attempt_key = key
        try:
            result = self.runner(data, filename, config=self.config, progress=progress)
        except UserFacingError as error:
            self.last_error = error
            return "failed"
        except Exception:                            # never surface internals or file content
            self.last_error = UserFacingError(
                "analysis_failed", "The analysis stopped unexpectedly. Your file was not stored.")
            return "failed"
        self.current = result                        # replace only after full success
        self.last_error = None
        return "replaced"

    def clear(self):
        self.current = None
        self.last_error = None
        self._last_attempt_key = None
