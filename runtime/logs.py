"""Runtime logging: console and a rotating file, with every line redacted before it is written.

Redaction removes URL credentials (scheme://user:pass@host) and every secret value registered at runtime (camera
passwords read from environment variables), including in exception tracebacks.
"""
import logging
import logging.handlers
import re
import threading
from urllib.parse import urlsplit

_secrets: set = set()
_lock = threading.Lock()
URL_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s@]+@")
LOGGER = "safesight.runtime"


def register_secret(value: str):
    if value and len(value) >= 3:  # very short values would redact ordinary text
        with _lock:
            _secrets.add(value)


def redact(text: str) -> str:
    text = URL_USERINFO.sub(r"\1***@", text)
    with _lock:
        secrets = sorted(_secrets, key=len, reverse=True)
    for s in secrets:
        text = text.replace(s, "***")
    return text


def redact_url(url: str) -> str:
    """scheme://host:port/path, without credentials or query values."""
    u = urlsplit(url)
    host = u.hostname or ""
    port = f":{u.port}" if u.port else ""
    return f"{u.scheme}://{host}{port}{u.path}" + ("?…" if u.query else "")


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


def setup(log_file=None, level="INFO") -> logging.Logger:
    log = logging.getLogger(LOGGER)
    log.setLevel(level)
    log.propagate = False
    for h in list(log.handlers):
        log.removeHandler(h)
        h.close()
    fmt = RedactingFormatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    log.addHandler(console)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)
    return log


def get(name=None) -> logging.Logger:
    return logging.getLogger(f"{LOGGER}.{name}" if name else LOGGER)
