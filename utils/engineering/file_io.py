from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


def atomic_write_text(path: os.PathLike[str] | str, text: str, *, encoding: str = "utf-8") -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding)
    os.replace(tmp, target)


def atomic_write_json(
    path: os.PathLike[str] | str,
    payload: Mapping[str, Any],
    *,
    ensure_ascii: bool = False,
    indent: int = 2,
    encoding: str = "utf-8",
) -> None:
    text = json.dumps(payload, ensure_ascii=ensure_ascii, indent=indent)
    atomic_write_text(path, text, encoding=encoding)
