"""Shared, versioned framework basics for every AI entry.

Reading this packaged text does not construct a Solver, inspect credentials or
teach a model permanently. Entry-specific capabilities remain separate.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from collections.abc import Mapping


BASICS_ID = "black-framework-basics"
BASICS_VERSION = "1"
_PATH = Path(__file__).with_name("skills") / "framework-experiment-guide" / "FOUNDATIONS.md"


def read_framework_basics() -> dict:
    data = _PATH.read_bytes()
    if not 100 < len(data) <= 24000:
        raise ValueError("framework_basics_invalid")
    content = data.decode("utf-8-sig").replace("\r\n", "\n").strip()
    if not content.startswith("# 框架基础认识"):
        raise ValueError("framework_basics_invalid")
    return {"content": content, "metadata": {
        "id": BASICS_ID, "version": BASICS_VERSION,
        "sha256": hashlib.sha256(data).hexdigest(),
    }}


def verify_framework_basics(metadata: Mapping) -> dict:
    current = read_framework_basics()
    if not isinstance(metadata, Mapping) or dict(metadata) != current["metadata"]:
        raise ValueError("framework_basics_mismatch")
    return current


def framework_system_prompt(role_prompt: str, *, basics=None) -> str:
    if not isinstance(role_prompt, str) or not role_prompt.strip():
        raise ValueError("framework_role_prompt_invalid")
    current = read_framework_basics() if basics is None else verify_framework_basics(basics["metadata"])
    return (current["content"] + "\n\n## 本入口的能力与交付要求\n\n" + role_prompt)
