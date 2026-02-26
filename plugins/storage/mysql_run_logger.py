"""
MySQL run logger plugin.

Writes run metadata + report paths into a MySQL table.
This is a lightweight bridge for external experiment tracking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import json

from ..base import Plugin
from ...utils.context.context_keys import KEY_BEST_OBJECTIVE, KEY_BEST_X


@dataclass
class MySQLRunLoggerConfig:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "nsgablack"
    table: str = "nsgablack_runs"
    connect_timeout: int = 10
    print_latest_summary: bool = True


class MySQLRunLoggerPlugin(Plugin):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Reads solver/result metadata and writes run record to external MySQL table."
    )
    """
    Log run metadata and report paths into MySQL.

    Requires either `mysql-connector-python` or `pymysql` installed.
    """

    def __init__(
        self,
        name: str = "mysql_run_logger",
        *,
        config: Optional[MySQLRunLoggerConfig] = None,
        priority: int = 50,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or MySQLRunLoggerConfig()

    def _get_connection(self):
        # Prefer mysql-connector; fallback to pymysql only when driver import is missing.
        try:
            import mysql.connector as mysql_connector  # type: ignore
        except Exception:
            mysql_connector = None

        if mysql_connector is not None:
            # Connection/config errors should surface as-is (e.g. unknown database).
            return mysql_connector.connect(
                host=self.cfg.host,
                port=int(self.cfg.port),
                user=self.cfg.user,
                password=self.cfg.password,
                database=self.cfg.database,
                connection_timeout=int(self.cfg.connect_timeout),
            )

        try:
            import pymysql  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "MySQLRunLoggerPlugin requires mysql-connector-python or pymysql."
            ) from exc

        # Connection/config errors should surface as-is.
        return pymysql.connect(
            host=self.cfg.host,
            port=int(self.cfg.port),
            user=self.cfg.user,
            password=self.cfg.password,
            database=self.cfg.database,
            connect_timeout=int(self.cfg.connect_timeout),
        )

    def _ensure_table(self, conn) -> None:
        table = self.cfg.table
        ddl = f"""
CREATE TABLE IF NOT EXISTS `{table}` (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_id VARCHAR(64),
  status VARCHAR(32),
  steps INT NULL,
  best_objective DOUBLE NULL,
  modules_path TEXT,
  bias_path TEXT,
  summary_json TEXT,
  extra_json TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""
        cur = conn.cursor()
        cur.execute(ddl)
        conn.commit()
        cur.close()

    def on_solver_finish(self, result: Dict[str, Any]):
        solver = self.solver
        if solver is None:
            return None

        artifacts = result.get("artifacts") if isinstance(result, dict) else {}
        modules_path = None
        bias_path = None
        if isinstance(artifacts, dict):
            modules_path = artifacts.get("modules_report_json")
            bias_path = artifacts.get("bias_report_json")

        payload = {
            "status": result.get("status") if isinstance(result, dict) else None,
            "steps": result.get("steps") if isinstance(result, dict) else None,
            "best_objective": self._resolve_context_value(solver, KEY_BEST_OBJECTIVE, "best_objective"),
            "best_x": self._resolve_context_value(solver, KEY_BEST_X, "best_x"),
        }
        payload_jsonable = self._to_jsonable(payload)
        result_jsonable = self._to_jsonable(result if isinstance(result, dict) else None)
        best_obj_value = payload_jsonable.get("best_objective")
        if isinstance(best_obj_value, (list, dict)):
            best_obj_value = None

        run_id = self._resolve_run_id(solver, result, artifacts)

        conn = self._get_connection()
        try:
            self._ensure_table(conn)
            cur = conn.cursor()
            cur.execute(
                f"""INSERT INTO `{self.cfg.table}`
(run_id, status, steps, best_objective, modules_path, bias_path, summary_json, extra_json)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
""",
                (
                    str(run_id) if run_id is not None else None,
                    payload.get("status"),
                    payload.get("steps"),
                    best_obj_value,
                    str(modules_path) if modules_path else None,
                    str(bias_path) if bias_path else None,
                    json.dumps(payload_jsonable, ensure_ascii=False),
                    json.dumps(result_jsonable, ensure_ascii=False),
                ),
            )
            inserted_id = getattr(cur, "lastrowid", None)
            conn.commit()
            cur.close()
            if bool(self.cfg.print_latest_summary):
                self._print_latest_summary(conn, inserted_id)
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return None

    def _print_latest_summary(self, conn, inserted_id: Any = None) -> None:
        query = (
            f"SELECT id, run_id, status, steps, best_objective, created_at "
            f"FROM `{self.cfg.table}` WHERE id=%s"
            if inserted_id
            else f"SELECT id, run_id, status, steps, best_objective, created_at "
                 f"FROM `{self.cfg.table}` ORDER BY id DESC LIMIT 1"
        )
        cur = conn.cursor()
        try:
            if inserted_id:
                cur.execute(query, (inserted_id,))
            else:
                cur.execute(query)
            row = cur.fetchone()
            if not row:
                return
            if isinstance(row, dict):
                rid = row.get("run_id")
                status = row.get("status")
                steps = row.get("steps")
                best = row.get("best_objective")
                created_at = row.get("created_at")
                db_id = row.get("id")
            else:
                db_id, rid, status, steps, best, created_at = row[:6]
            print(
                "[mysql-run] "
                f"id={db_id} run_id={rid} status={status} "
                f"steps={steps} best_objective={best} created_at={created_at}"
            )
        finally:
            try:
                cur.close()
            except Exception:
                pass

    def _to_jsonable(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(k): self._to_jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._to_jsonable(v) for v in value]
        # numpy/pandas style scalars and arrays
        if hasattr(value, "item") and callable(getattr(value, "item", None)):
            try:
                return self._to_jsonable(value.item())
            except Exception:
                pass
        if hasattr(value, "tolist") and callable(getattr(value, "tolist", None)):
            try:
                return self._to_jsonable(value.tolist())
            except Exception:
                pass
        return str(value)

    def _resolve_context_value(self, solver: Any, key: str, attr_fallback: str) -> Any:
        getter = getattr(solver, "get_context", None)
        if callable(getter):
            try:
                ctx = getter()
            except Exception:
                ctx = None
            if isinstance(ctx, dict) and key in ctx:
                return ctx.get(key)
        try:
            return getattr(solver, attr_fallback, None)
        except Exception:
            return None

    def _resolve_run_id(self, solver: Any, result: Dict[str, Any], artifacts: Dict[str, Any] | None) -> Optional[str]:
        # 1) explicit result-level run_id
        if isinstance(result, dict):
            rid = result.get("run_id")
            if rid:
                return str(rid)

        # 2) artifact metadata
        if isinstance(artifacts, dict):
            rid = artifacts.get("run_id")
            if rid:
                return str(rid)

        # 3) known solver attributes (ui / scripts may set these)
        for attr in ("run_id", "_last_run_id", "benchmark_run_id"):
            try:
                rid = getattr(solver, attr, None)
            except Exception:
                rid = None
            if rid:
                return str(rid)

        # 4) discover from plugin configs (BenchmarkHarness / ModuleReport / Profiler ...)
        pm = getattr(solver, "plugin_manager", None)
        if pm is not None and hasattr(pm, "list_plugins"):
            try:
                for plugin in pm.list_plugins(enabled_only=False):
                    cfg = getattr(plugin, "cfg", None)
                    rid = getattr(cfg, "run_id", None) if cfg is not None else None
                    if rid:
                        return str(rid)
            except Exception:
                pass
        return None

