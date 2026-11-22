"""Log file for the desktop app, used by "Report a bug" and support.

A packaged OVC.exe has no console: without a log, an error leaves no trace.
The log lives in ``~/.ovc/logs/ovc-app.log`` (rotated at 1 MB, 3 copies)
and records start-up, the window, shutdown reasons and unexpected errors.
A hard crash in a native library is written there by ``faulthandler``.
"""

from __future__ import annotations

import faulthandler
import logging
import logging.handlers
import platform
import sys
from pathlib import Path

LOGGER = "ovc.app"
_fault_file = None


def log_dir() -> Path:
    return Path.home() / ".ovc" / "logs"


def log_path() -> Path:
    return log_dir() / "ovc-app.log"


def setup_logging() -> Path | None:
    """Send app logging, stray prints and native crashes to the log file."""
    global _fault_file
    try:
        log_dir().mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            log_path(), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
    except OSError:
        return None
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger = logging.getLogger(LOGGER)
    logger.setLevel(logging.INFO)
    if not any(
        isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers
    ):
        logger.addHandler(handler)
    # A windowed exe has no console: keep stray output and tracebacks.
    if sys.stdout is None or sys.stderr is None:
        stream = open(log_path(), "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = stream
        if sys.stderr is None:
            sys.stderr = stream
    try:
        _fault_file = open(log_dir() / "ovc-crash.log", "a", encoding="utf-8")
        faulthandler.enable(file=_fault_file)
    except Exception:
        pass
    return log_path()


def get_logger(name: str = "") -> logging.Logger:
    return logging.getLogger(LOGGER + ("." + name if name else ""))


def tail(lines: int = 150) -> str:
    """The last lines of the log (and of the crash log, when it has content)."""
    out = []
    for path in (log_dir() / "ovc-crash.log", log_path()):
        try:
            text = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        if text:
            out.append(f"--- {path.name} ---")
            out.extend(text[-lines:])
    return "\n".join(out)


def environment() -> dict:
    from ovc import __version__
    from ovc.app import updates

    return {
        "version": __version__,
        "install": updates.install_kind(),
        "os": platform.platform(),
        "python": platform.python_version(),
    }
