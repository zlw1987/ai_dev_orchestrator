"""ASCII-safe JSON emission for the AR1 experiment.

Windows legacy consoles are cp1252, and this experiment prints text that came
from a subprocess and from a model. That is exactly the class of text that broke
stdout before commit ``80395ff``.

This is an experiment-local helper on purpose: importing the production private
``_echo_json_model`` would couple an experiment to a private CLI symbol, and
production code must not be modified to share it.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def dumps_ascii(value: Any, *, indent: int | None = 2) -> str:
    """Serialize to JSON with every non-ASCII character escaped."""
    return json.dumps(value, ensure_ascii=True, indent=indent, sort_keys=False)


def echo_ascii(value: Any, *, indent: int | None = 2) -> None:
    """Print ASCII-safe JSON, tolerating a console that cannot encode it."""
    text = dumps_ascii(value, indent=indent)
    try:
        sys.stdout.write(text + "\n")
    except UnicodeEncodeError:  # pragma: no cover - console-dependent
        sys.stdout.buffer.write(text.encode("ascii", "backslashreplace") + b"\n")
    sys.stdout.flush()


def is_ascii_representable(value: Any) -> bool:
    """Whether ``value`` serializes to pure ASCII (the emitted-JSON property)."""
    return dumps_ascii(value).isascii()
