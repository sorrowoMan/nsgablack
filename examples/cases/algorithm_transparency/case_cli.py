"""单 Case CLI 仍由正式 Project 分配资源和建立 CaseRuntime。"""
from pathlib import Path
import sys

from _bootstrap import bootstrap


CASE_GROUPS = {"matrix": "matrix", **{name: f"case_{name}" for name in
    ("parallel_a", "parallel_b", "bare_inner", "nested_outer")}}


def main(case_name, argv=None):
    bootstrap()
    from nsgablack.project.project_runner import build_parser, run_project

    if case_name not in CASE_GROUPS:
        raise ValueError(f"unknown transparency Case: {case_name}")
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.group != "default":
        parser.error("a Case CLI selects its own Case; use run_project.py for --group")
    forwarded = tuple(args.case_args or ())
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]
    return run_project(Path(__file__).resolve().parent, group=CASE_GROUPS[case_name],
        check=bool(args.check), build_check=bool(args.check or args.build_check),
        case_args=forwarded, record=not args.no_record, run_id=args.run_id,
        resume_from=args.resume_from)
