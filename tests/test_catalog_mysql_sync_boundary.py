from __future__ import annotations

from nsgablack.catalog.store.mysql import MySQLCatalogStore


class _Cursor:
    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple[object, ...] | None]] = []

    def execute(self, statement: str, params=None) -> None:
        normalized = " ".join(statement.split())
        self.statements.append((normalized, None if params is None else tuple(params)))

    def fetchall(self):
        return [(1, "keep"), (2, "retired")]

    def close(self) -> None:
        return None


class _Connection:
    def __init__(self) -> None:
        self.cursor_value = _Cursor()
        self.commits = 0

    def cursor(self) -> _Cursor:
        return self.cursor_value

    def commit(self) -> None:
        self.commits += 1


def test_mysql_materialization_removes_components_absent_from_current_source() -> None:
    conn = _Connection()

    MySQLCatalogStore._delete_stale_components(
        object(),
        conn,
        current_keys=("keep",),
    )

    deletes = [item for item in conn.cursor_value.statements if item[0].startswith("DELETE FROM")]
    assert len(deletes) == 7
    assert all(params == (2,) for _statement, params in deletes)
    assert deletes[-1][0].startswith("DELETE FROM catalog_component")
    assert conn.commits == 1
