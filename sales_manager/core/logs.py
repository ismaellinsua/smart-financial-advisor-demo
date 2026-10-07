"""The server log: one line per event, `key=value` pairs, never personal data or secrets.

What goes here: errors with their reference (the same one the person sees), sign-in blocks (by hashed address),
Stripe and email failures, webhooks. Customers' names, emails and amounts stay out. The one exception is the
traceback of an unexpected error, which only the owner can read and which is needed to fix it. Read it in «Manage app → Logs» (Streamlit) or the Render dashboard. LOG_LEVEL changes the detail.
"""

import json
import logging
import re
import sys

from . import config

ROOT = "nirkana"
_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


_PAIR = re.compile(r"(\w+)=(\S+)")


class JsonFormatter(logging.Formatter):
    """One JSON object per line: time, level, logger, message and every key=value of the message as a field."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        entry = {"time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname,
                 "logger": record.name, "message": message}
        for key, value in _PAIR.findall(message):
            entry.setdefault(key, value)
        if record.exc_info:
            entry["traceback"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup() -> logging.Logger:
    """Configure the app's loggers once (later calls do nothing) and return the root one."""
    root = logging.getLogger(ROOT)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter() if config.value("log_format").lower() == "json"
                             else logging.Formatter(_FORMAT, "%Y-%m-%dT%H:%M:%S"))
        root.addHandler(handler)
        root.setLevel(config.value("log_level").upper() or "INFO")
        root.propagate = False
    return root


def get(name: str) -> logging.Logger:
    setup()
    return logging.getLogger(f"{ROOT}.{name}")
