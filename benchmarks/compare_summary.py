from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_summary(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid summary json: {path}")
    return data


def _as_float(value: Any) -> str:
    try:
        return f"{float(value):.6f}"
    except Exception:
        return "-"


def _as_int(value: Any) -> str:
    try:
        return str(int(value))
    except Exception:
        return "-"


def build_markdown_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| run_id | status | steps | elapsed_s | eval_count | throughput_eval_s | best_score |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {run_id} | {status} | {steps} | {elapsed} | {evals} | {throughput} | {best} |".format(
                run_id=str(row.get("run_id", "-")),
                status=str(row.get("status", "-")),
                steps=_as_int(row.get("steps")),
                elapsed=_as_float(row.get("elapsed_s")),
                evals=_as_int(row.get("eval_count")),
                throughput=_as_float(row.get("throughput_eval_s")),
                best=_as_float(row.get("best_score")),
            )
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build benchmark summary comparison table.")
    parser.add_argument("--input-dir", type=str, default="runs", help="Directory containing *.summary.json files.")
    parser.add_argument(
        "--pattern",
        type=str,
        default="*.summary.json",
        help="Glob pattern for summary files (default: *.summary.json).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="runs/benchmark_comparison.md",
        help="Output markdown path.",
    )
    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir).resolve()
    files = sorted(input_dir.glob(str(args.pattern)))
    if not files:
        raise FileNotFoundError(f"no summary files matched: {input_dir} / {args.pattern}")

    rows = [_load_summary(path) for path in files]
    md = build_markdown_table(rows)
    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"[ok] wrote comparison table: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
