from types import SimpleNamespace

from nsgablack.utils.viz.ui.run_view import RunView


def test_context_store_snapshot_masks_redis_password() -> None:
    view = RunView.__new__(RunView)
    solver = SimpleNamespace(
        context_store_backend="redis",
        context_store_ttl_seconds=30,
        context_store_redis_url="redis://user:secret@127.0.0.1:6379/0",
        context_store_key_prefix="nsgablack:demo_project",
    )
    snap = RunView._context_store_snapshot(view, solver)
    assert snap["backend"] == "redis"
    assert snap["ttl_seconds"] == 30
    assert snap["key_prefix"] == "nsgablack:demo_project"
    assert "secret" not in str(snap["redis_url"])
    assert "***" in str(snap["redis_url"])


def test_structure_hash_changes_when_context_store_changes() -> None:
    view = RunView.__new__(RunView)
    base = {
        "adapter": "A",
        "pipeline": {},
        "strategies": [],
        "biases": [],
        "plugins": [],
        "context_store": {
            "backend": "redis",
            "ttl_seconds": 30,
            "key_prefix": "nsgablack:demo",
            "redis_url": "redis://127.0.0.1:6379/0",
        },
    }
    changed = dict(base)
    changed["context_store"] = dict(base["context_store"])
    changed["context_store"]["ttl_seconds"] = 300
    left = RunView._structure_hash(view, base)
    right = RunView._structure_hash(view, changed)
    assert left != right


def test_parse_seed_override_accepts_empty_and_int() -> None:
    assert RunView._parse_seed_override("") is None
    assert RunView._parse_seed_override("  ") is None
    assert RunView._parse_seed_override("42") == 42
    assert RunView._parse_seed_override(" -7 ") == -7


def test_parse_seed_override_rejects_non_int() -> None:
    try:
        RunView._parse_seed_override("abc")
    except ValueError:
        return
    raise AssertionError("expected ValueError for non-int seed override")
