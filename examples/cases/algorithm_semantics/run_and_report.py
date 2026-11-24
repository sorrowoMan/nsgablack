"""Run the formal Project, then save its actual structured Case evidence."""
from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
from pathlib import Path

from nsgablack.project.project_runner import execute_project


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", default="default")
    parser.add_argument("--output", default="results/project_run.json")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    result = execute_project(root, group=args.group)
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Project run: {result.run_id}; ok={result.ok}; evidence={output}")
    for case in result.case_results:
        report = case.output.get("report", {}) if isinstance(case.output, Mapping) else {}
        print(f"{case.request.case_name}: status={case.status}; "
              f"steps={report.get('steps')}; evaluations={report.get('evaluation_count')}")
        if result.ok:
            publication = case.artifact_publications.get("summary")
            if publication is None or not publication.metadata.get("case_finalization_sealed"):
                raise ValueError(f"{case.request.case_name}: no sealed semantic summary")
            binding = result.artifact_bindings.get(f"{case.request.case_name}.summary")
            if binding is None or binding.publication != publication or binding.ref != publication.ref:
                raise ValueError("Project summary binding differs from the actual Case publication")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
