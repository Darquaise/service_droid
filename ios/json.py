import json
import os
import tempfile
from collections.abc import Mapping
from typing import Any


def read_json(path: str):
    with open(path, "r") as f:
        data = json.load(f)
    return data


def write_json(path: str, data: Mapping[str, Any] | list):
    directory = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
