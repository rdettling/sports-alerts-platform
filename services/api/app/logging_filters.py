from __future__ import annotations

import logging


class SuppressLowSignalAccessLogsFilter(logging.Filter):
    def _should_suppress_rendered_message(self, message: str) -> bool:
        if '"OPTIONS ' in message:
            return True
        return '"GET /healthz' in message

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3:
            method = str(args[1]).upper()
            path = str(args[2])
            if method == "OPTIONS":
                return False
            if path.startswith("/healthz"):
                return False

        return not self._should_suppress_rendered_message(record.getMessage())
