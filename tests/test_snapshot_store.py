import uuid

import numpy as np

from nsgablack.core.state.snapshot_store import FileSnapshotStore, InMemorySnapshotStore


def test_snapshot_store_memory_roundtrip() -> None:
    store = InMemorySnapshotStore()
    payload = {
        "population": np.array([[1.0, 2.0]], dtype=float),
        "objectives": np.array([[3.0]], dtype=float),
        "constraint_violations": np.array([0.0], dtype=float),
    }
    handle = store.write(payload, meta={"complete": True})
    record = store.read(handle.key)
    assert record is not None
    assert record.schema == handle.schema
    assert record.meta.get("complete") is True
    assert np.asarray(record.data.get("population")).shape == (1, 2)


def test_snapshot_store_file_roundtrip() -> None:
    store = FileSnapshotStore(base_dir=".", key_prefix="")
    payload = {
        "population": np.array([[5.0, 6.0]], dtype=float),
        "objectives": np.array([[7.0]], dtype=float),
        "constraint_violations": np.array([0.0], dtype=float),
    }
    key = f"snapshot_test_{uuid.uuid4().hex}"
    try:
        handle = store.write(payload, meta={"complete": True}, key=key)
        record = store.read(handle.key)
        assert record is not None
        assert np.asarray(record.data.get("population")).shape == (1, 2)
        assert float(np.asarray(record.data.get("objectives"))[0, 0]) == 7.0
    finally:
        try:
            store.delete(key)
        except Exception:
            pass
