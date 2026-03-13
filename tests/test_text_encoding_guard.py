from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_vscode_settings_pin_utf8_encoding() -> None:
    settings_path = REPO_ROOT / ".vscode" / "settings.json"
    settings = json.loads(_read_utf8(settings_path))
    assert settings.get("files.encoding") == "utf8"
    assert settings.get("files.autoGuessEncoding") is False


def test_start_here_doctor_section_has_no_mojibake() -> None:
    text = _read_utf8(REPO_ROOT / "START_HERE.md")
    assert "## Doctor IDE 自动诊断" in text
    assert "为什么 Notebook 里看不到爆红" in text
    assert "## Doctor IDE ?????" not in text
