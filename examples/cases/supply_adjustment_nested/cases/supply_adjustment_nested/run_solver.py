"""Case CLI：装配检查只构造，联合求解复用正式 Project/L0 入口。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from blackbase.project import (
    build_case,
    execute_project,
    load_case_builder,
    load_resource_context_from_env,
    print_case_check,
)
from blackbase.project.runtime import close_case_after_build_check


def main(argv=None) -> int:
    contract = argparse.ArgumentParser(add_help=False)
    contract.add_argument("--check", action="store_true")
    contract.add_argument("--ui", action="store_true")
    forwarded = list(sys.argv[1:] if argv is None else argv)
    args, _ = contract.parse_known_args(forwarded)
    if args.ui:
        contract.error("联合求解需要正式 Project runtime；请通过 Project 工作区运行")
    project_root = Path(__file__).resolve().parents[2]
    case_name = Path(__file__).resolve().parent.name
    if args.check or "--help" in forwarded or "-h" in forwarded:
        builder = load_case_builder(project_root, case_name)
        case = build_case(
            builder,
            resource_context=load_resource_context_from_env("nsgablack"),
            component_overrides={"argv": forwarded},
        )
        try:
            print_case_check(case)
        finally:
            close_case_after_build_check(case)
        return 0
    # The Project owns grants, nested invocation, cancellation and publication.
    # This temporary CLI input only supplies the direct Stage's assembly args.
    key = "NSGABLACK_SUPPLY_CASE_ARGV"
    previous = os.environ.get(key)
    os.environ[key] = json.dumps(forwarded, ensure_ascii=False)
    try:
        result = execute_project(project_root, group="direct", framework="nsgablack")
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous
    print(f"done: status={result.status} exit_code={result.exit_code}")
    return int(result.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
