"""Central logging configuration.

Primary sink is **stdout** (captured by the Docker json-file log driver, which also handles rotation in production).
A secondary RotatingFileHandler writes the same records to `<DATA_DIR>/logs/latest.log` so the in-Discord `/log` view (`classes/log_view.py`) still has a file to tail; stdout stays authoritative.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_TRUTHY = ("1", "true", "yes", "on")


def _data_dir() -> str:
    return os.environ.get("DATA_DIR", ".")


def log_file_path() -> str:
    """Path of the rotating log file the ``/log`` command reads."""
    return os.path.join(_data_dir(), "logs", "latest.log")


def setup_logging() -> None:
    level = (
        logging.DEBUG
        if os.environ.get("DEBUG", "").strip().lower() in _TRUTHY
        else logging.INFO
    )
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)

    path = log_file_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    file = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    file.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers[:] = [stream, file]

    # Tame py-cord/discord internals (their gateway chatter is noisy at DEBUG).
    logging.getLogger("discord").setLevel(logging.INFO)
