import json

from nsgablack.utils.engineering.config_loader import (
    apply_config,
    build_dataclass_config,
    ConfigError,
    load_config,
    merge_dicts,
)
from nsgablack.core.config import SolverConfig


def test_load_config_from_dict():
    data = load_config({"pop_size": 12})
    assert data["pop_size"] == 12


def test_load_config_from_file(tmp_path):
    path = tmp_path / "solver.json"
    path.write_text(json.dumps({"max_generations": 5}), encoding="utf-8")
    data = load_config(path)
    assert data["max_generations"] == 5


def test_merge_dicts_deep():
    base = {"a": 1, "nested": {"x": 1}}
    override = {"nested": {"y": 2}}
    merged = merge_dicts(base, override)
    assert merged["nested"]["x"] == 1
    assert merged["nested"]["y"] == 2


def test_apply_config_strict_unknown():
    class Dummy:
        def __init__(self):
            self.value = 1

    dummy = Dummy()
    apply_config(dummy, {"value": 2})
    assert dummy.value == 2

    try:
        apply_config(dummy, {"missing": 1}, allow_unknown=False)
        raised = False
    except ConfigError:
        raised = True
    assert raised


def test_build_dataclass_config():
    cfg, unknown = build_dataclass_config(SolverConfig, {"pop_size": 64})
    assert cfg.pop_size == 64
    assert not list(unknown)
