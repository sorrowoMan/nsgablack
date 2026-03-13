from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_vscode_tasks_contains_doctor_problem_task() -> None:
    tasks_file = REPO_ROOT / ".vscode" / "tasks.json"
    assert tasks_file.is_file(), "missing .vscode/tasks.json"
    payload = _load_json(tasks_file)
    tasks = payload.get("tasks", [])
    assert isinstance(tasks, list) and tasks, "tasks.json has no tasks"

    by_label = {str(t.get("label", "")): t for t in tasks if isinstance(t, dict)}
    assert "doctor: strict (problem)" in by_label
    assert "doctor: watch (problem)" in by_label

    strict_task = by_label["doctor: strict (problem)"]
    strict_pm = strict_task.get("problemMatcher")
    assert isinstance(strict_pm, list) and strict_pm, "strict task missing problemMatcher"


def test_vscode_settings_contains_trigger_task_on_save() -> None:
    settings_file = REPO_ROOT / ".vscode" / "settings.json"
    assert settings_file.is_file(), "missing .vscode/settings.json"
    settings = _load_json(settings_file)

    assert settings.get("triggerTaskOnSave.on") is True
    assert settings.get("triggerTaskOnSave.delay") == 300
    assert settings.get("triggerTaskOnSave.restart") is True
    assert settings.get("triggerTaskOnSave.showNotifications") is True

    task_map = settings.get("triggerTaskOnSave.tasks")
    assert isinstance(task_map, dict), "triggerTaskOnSave.tasks must be an object"
    assert "doctor: strict (problem)" in task_map

    patterns = task_map["doctor: strict (problem)"]
    assert isinstance(patterns, list) and patterns, "doctor trigger patterns should be non-empty"
    expected = {"**/*.py", "**/*.toml", "**/*.json", "**/*.yml", "**/*.yaml", "**/*.md"}
    assert expected.issubset(set(str(p) for p in patterns))


def test_trigger_task_label_matches_existing_task() -> None:
    tasks_payload = _load_json(REPO_ROOT / ".vscode" / "tasks.json")
    settings_payload = _load_json(REPO_ROOT / ".vscode" / "settings.json")

    task_labels = {
        str(t.get("label", ""))
        for t in tasks_payload.get("tasks", [])
        if isinstance(t, dict) and t.get("label")
    }
    trigger_map = settings_payload.get("triggerTaskOnSave.tasks", {})
    assert isinstance(trigger_map, dict)

    missing = [label for label in trigger_map.keys() if label not in task_labels]
    assert not missing, f"triggerTaskOnSave references unknown tasks: {missing}"
