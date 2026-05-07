import json
from collections.abc import Mapping
from typing import Any


def read_json(path: str):
    with open(path, "r") as f:
        data = json.load(f)
    return data


def write_json(path: str, data: Mapping[str, Any] | list):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
