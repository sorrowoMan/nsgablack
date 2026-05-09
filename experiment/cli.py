from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

if __package__ in {None, ""}:
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from nsgablack.plugins import (
        list_runtime_artifact_surfaces,
        list_runtime_run_surfaces,
        runtime_surface_summary,
        show_runtime_artifact_surface,
        show_runtime_run_surface,
    )
else:
    from ..plugins import (
        list_runtime_artifact_surfaces,
        list_runtime_run_surfaces,
        runtime_surface_summary,
        show_runtime_artifact_surface,
        show_runtime_run_surface,
    )
    from .db import experiment_db_config_info, resolve_experiment_db_target

if __package__ in {None, ""}:
    from nsgablack.experiment.db import experiment_db_config_info, resolve_experiment_db_target


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _resolved_db_target(raw: Any) -> str:
    return resolve_experiment_db_target(None if raw is None else str(raw))


def _cmd_summary(args: argparse.Namespace) -> int:
    print(_json_dumps(runtime_surface_summary(_resolved_db_target(args.db))))
    return 0


def _cmd_list_runs(args: argparse.Namespace) -> int:
    rows = list_runtime_run_surfaces(
        _resolved_db_target(args.db),
        run_id=args.run_id,
        status=args.status,
        surface_key=args.surface_key,
        driver_ref=args.driver_ref,
        family_ref=args.family_ref,
        assembly_signature=args.assembly_signature,
        screening_protocol=args.screening_protocol,
        outer_search_protocol=args.outer_search_protocol,
        joint_core_score_min=args.joint_core_score_min,
        limit=int(args.limit),
    )
    print(_json_dumps(rows))
    return 0


def _cmd_show_run(args: argparse.Namespace) -> int:
    row = show_runtime_run_surface(_resolved_db_target(args.db), run_id=str(args.run_id))
    print(_json_dumps(row or {}))
    return 0 if row is not None else 1


def _cmd_list_artifacts(args: argparse.Namespace) -> int:
    rows = list_runtime_artifact_surfaces(
        _resolved_db_target(args.db),
        run_id=args.run_id,
        artifact_role=args.artifact_role,
        producer_ref=args.producer_ref,
        surface_key=args.surface_key,
        assembly_signature=args.assembly_signature,
        limit=int(args.limit),
    )
    print(_json_dumps(rows))
    return 0


def _cmd_show_artifact(args: argparse.Namespace) -> int:
    row = show_runtime_artifact_surface(
        _resolved_db_target(args.db),
        run_id=str(args.run_id),
        artifact_id=str(args.artifact_id),
    )
    print(_json_dumps(row or {}))
    return 0 if row is not None else 1


def _cmd_ui(args: argparse.Namespace) -> int:
    from .dashboard import build_streamlit_command

    command = build_streamlit_command(
        db_path=_resolved_db_target(args.db),
        limit=int(args.limit),
        column_mode=str(args.column_mode),
        page_size=int(args.page_size),
        results_collapse=str(args.results_collapse),
        host=args.host,
        port=args.port,
        headless=bool(args.headless),
    )
    proc = subprocess.run(command, check=False)
    return int(proc.returncode)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="nsgablack runtime experiment surface")
    sub = parser.add_subparsers(dest="cmd", required=True)

    default_info = experiment_db_config_info()
    default_hint = str(default_info.get("db_target") or "runs/runtime_surface.sqlite3")
    db_help = (
        "Optional experiment DB target. Accepts a sqlite path or postgresql://... URL. "
        f"Defaults to experiment/db.toml, env, catalog fallback, then local sqlite ({default_hint})."
    )

    p_summary = sub.add_parser("summary", help="Summarize runtime run/artifact surface tables")
    p_summary.add_argument("--db", default=None, help=db_help)
    p_summary.set_defaults(_fn=_cmd_summary)

    p_list_runs = sub.add_parser("list-runs", help="List runtime run surface rows as JSON")
    p_list_runs.add_argument("--db", default=None, help=db_help)
    p_list_runs.add_argument("--run-id", default=None, help="Optional run_id filter")
    p_list_runs.add_argument("--status", default=None, help="Optional status filter")
    p_list_runs.add_argument("--surface-key", default=None, help="Optional surface_key filter")
    p_list_runs.add_argument("--driver-ref", default=None, help="Optional driver_ref filter")
    p_list_runs.add_argument("--family-ref", default=None, help="Optional family_ref filter")
    p_list_runs.add_argument("--assembly-signature", default=None, help="Optional assembly_signature filter")
    p_list_runs.add_argument("--screening-protocol", default=None, help="Optional screening_protocol filter")
    p_list_runs.add_argument("--outer-search-protocol", default=None, help="Optional outer_search_protocol filter")
    p_list_runs.add_argument("--joint-core-score-min", type=float, default=None, help="Optional minimum joint_core_score filter")
    p_list_runs.add_argument("--limit", type=int, default=50, help="Max rows to return")
    p_list_runs.set_defaults(_fn=_cmd_list_runs)

    p_show_run = sub.add_parser("show-run", help="Show one runtime run surface row as JSON")
    p_show_run.add_argument("--db", default=None, help=db_help)
    p_show_run.add_argument("--run-id", required=True, help="Run identifier")
    p_show_run.set_defaults(_fn=_cmd_show_run)

    p_list_artifacts = sub.add_parser("list-artifacts", help="List runtime artifact surface rows as JSON")
    p_list_artifacts.add_argument("--db", default=None, help=db_help)
    p_list_artifacts.add_argument("--run-id", default=None, help="Optional run_id filter")
    p_list_artifacts.add_argument("--artifact-role", default=None, help="Optional artifact_role filter")
    p_list_artifacts.add_argument("--producer-ref", default=None, help="Optional producer_ref filter")
    p_list_artifacts.add_argument("--surface-key", default=None, help="Optional surface_key filter")
    p_list_artifacts.add_argument("--assembly-signature", default=None, help="Optional assembly_signature filter")
    p_list_artifacts.add_argument("--limit", type=int, default=50, help="Max rows to return")
    p_list_artifacts.set_defaults(_fn=_cmd_list_artifacts)

    p_show_artifact = sub.add_parser("show-artifact", help="Show one runtime artifact surface row as JSON")
    p_show_artifact.add_argument("--db", default=None, help=db_help)
    p_show_artifact.add_argument("--run-id", required=True, help="Run identifier")
    p_show_artifact.add_argument("--artifact-id", required=True, help="Artifact identifier")
    p_show_artifact.set_defaults(_fn=_cmd_show_artifact)

    p_ui = sub.add_parser("ui", help="Launch runtime experiment dashboard")
    p_ui.add_argument("--db", default=None, help=db_help)
    p_ui.add_argument("--limit", type=int, default=500, help="Max result rows to query per view")
    p_ui.add_argument(
        "--column-mode",
        choices=("compact", "standard", "full"),
        default="standard",
        help="Initial results table column layout",
    )
    p_ui.add_argument("--page-size", type=int, default=50, help="Initial visible result count window")
    p_ui.add_argument(
        "--results-collapse",
        choices=("expanded", "collapsed"),
        default="expanded",
        help="Initial state of the results expander",
    )
    p_ui.add_argument("--host", type=str, default=None, help="Optional Streamlit server address")
    p_ui.add_argument("--port", type=int, default=None, help="Optional Streamlit server port")
    p_ui.add_argument("--headless", action="store_true", help="Launch Streamlit without opening a browser window")
    p_ui.set_defaults(_fn=_cmd_ui)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args._fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
