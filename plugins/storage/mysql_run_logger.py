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


@dataclass
class MySQLRunLoggerConfig:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "nsgablack"
    table: str = "nsgablack_runs"
    connect_timeout: int = 10


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
        # Try mysql-connector first, fallback to pymysql.
        try:
            import mysql.connector as mysql_connector  # type: ignore

            return mysql_connector.connect(
                host=self.cfg.host,
                port=int(self.cfg.port),
                user=self.cfg.user,
                password=self.cfg.password,
                database=self.cfg.database,
                connection_timeout=int(self.cfg.connect_timeout),
            )
        except Exception:
            try:
                import pymysql  # type: ignore

                return pymysql.connect(
                    host=self.cfg.host,
                    port=int(self.cfg.port),
                    user=self.cfg.user,
                    password=self.cfg.password,
                    database=self.cfg.database,
                    connect_timeout=int(self.cfg.connect_timeout),
                )
            except Exception as exc:
                raise RuntimeError(
                    "MySQLRunLoggerPlugin requires mysql-connector-python or pymysql."
                ) from exc

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
            "best_objective": getattr(solver, "best_objective", None),
            "best_x": getattr(solver, "best_x", None),
        }

        run_id = None
        try:
            run_id = getattr(getattr(self, "cfg", None), "run_id", None)
        except Exception:
            run_id = None
        if run_id is None and isinstance(artifacts, dict):
            run_id = artifacts.get("run_id")

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
                    payload.get("best_objective"),
                    str(modules_path) if modules_path else None,
                    str(bias_path) if bias_path else None,
                    json.dumps(payload, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else None,
                ),
            )
            conn.commit()
            cur.close()
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return None

