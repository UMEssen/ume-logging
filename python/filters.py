# Purpose: Filters for PII scrubbing and context propagation
# Just some examples, to be improved.

import logging, re
from typing import Iterable

_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE = re.compile(r"(?<!\d)(\+?\d{1,3}[\s-]?)?(\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}(?!\d)")

def _mask(s: str) -> str:
    s = _EMAIL.sub("[email]", s)
    s = _PHONE.sub("[phone]", s)
    return s

class PiiScrubberFilter(logging.Filter):
    # Purpose: scrub common PII-like tokens from log messages
    def __init__(self, fields: Iterable[str] = ("msg",)):
        super().__init__()
        self.fields = set(fields)

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = _mask(str(record.getMessage()))
        except Exception:
            pass
        return True