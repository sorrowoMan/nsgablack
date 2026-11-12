"""Run the bounded probe through the shared Project runner."""

from pathlib import Path
import os
import sys


def main(argv=None):
    project_root = Path(__file__).resolve().parent
    repo_root = project_root.parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from nsgablack.project.project_runner import build_parser, main as project_main
    forwarded = list(sys.argv[1:] if argv is None else argv)
    run_id = os.environ.get("NSGABLACK_RUNTIME_COST_RUN_ID", "manual")
    supplied_run_id = build_parser().parse_args(forwarded).run_id
    if supplied_run_id is not None and supplied_run_id != run_id:
        raise ValueError("--run-id must equal NSGABLACK_RUNTIME_COST_RUN_ID")
    if supplied_run_id is None:
        forwarded += ["--run-id", run_id]
    return project_main(project_root=project_root, argv=forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
