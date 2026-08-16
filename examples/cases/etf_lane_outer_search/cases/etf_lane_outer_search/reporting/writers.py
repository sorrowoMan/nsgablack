from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in dict(value).items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    return str(value)


def write_search_report(*, output_dir: Path, summary: Mapping[str, Any], records: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "etf_lane_outer_summary.json"
    table_path = output_dir / "etf_lane_outer_table.csv"
    md_path = output_dir / "etf_lane_outer_table.md"

    summary_path.write_text(json.dumps(_jsonable(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    items = [dict(row) for row in records]
    fields = [
        "label",
        "status",
        "score",
        "obj_weighted_neg_net_sharpe",
        "obj_weighted_mdd_abs",
        "obj_weighted_turnover",
        "obj_weighted_neg_rank_ic",
        "obj_weighted_rank_ic_std",
        "raw_neg_net_sharpe",
        "raw_mdd_abs",
        "raw_turnover",
        "raw_neg_rank_ic",
        "raw_rank_ic_std",
        "fold_count",
        "bundle_key",
    ]
    with table_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in items:
            obj = tuple(row.get("objectives", ()) or ())
            writer.writerow(
                {
                    "label": row.get("label", ""),
                    "status": row.get("status", ""),
                    "score": row.get("score", ""),
                    "obj_weighted_neg_net_sharpe": obj[0] if len(obj) > 0 else "",
                    "obj_weighted_mdd_abs": obj[1] if len(obj) > 1 else "",
                    "obj_weighted_turnover": obj[2] if len(obj) > 2 else "",
                    "obj_weighted_neg_rank_ic": obj[3] if len(obj) > 3 else "",
                    "obj_weighted_rank_ic_std": obj[4] if len(obj) > 4 else "",
                    "raw_neg_net_sharpe": (row.get("raw_objectives", {}) or {}).get("neg_net_sharpe", ""),
                    "raw_mdd_abs": (row.get("raw_objectives", {}) or {}).get("max_drawdown_abs", ""),
                    "raw_turnover": (row.get("raw_objectives", {}) or {}).get("turnover_proxy", ""),
                    "raw_neg_rank_ic": (row.get("raw_objectives", {}) or {}).get("neg_rank_ic_mean", ""),
                    "raw_rank_ic_std": (row.get("raw_objectives", {}) or {}).get("rank_ic_std", ""),
                    "fold_count": row.get("fold_count", ""),
                    "bundle_key": row.get("bundle_key", ""),
                }
            )

    lines = [
        "# ETF Lane Outer Search",
        "",
        f"suite_id: `{summary.get('suite_id', '')}`",
        f"eval_count: `{summary.get('evaluation_count', '')}`",
        "",
        "| label | status | score | w_neg_sharpe | w_mdd | w_turnover | w_neg_rank_ic | w_rank_ic_std | raw_neg_sharpe | raw_mdd | raw_turnover | raw_neg_rank_ic | raw_rank_ic_std | folds |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in items:
        obj = tuple(row.get("objectives", ()) or ())
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("label", "")),
                    str(row.get("status", "")),
                    str(row.get("score", "")),
                    str(obj[0] if len(obj) > 0 else ""),
                    str(obj[1] if len(obj) > 1 else ""),
                    str(obj[2] if len(obj) > 2 else ""),
                    str(obj[3] if len(obj) > 3 else ""),
                    str(obj[4] if len(obj) > 4 else ""),
                    str((row.get("raw_objectives", {}) or {}).get("neg_net_sharpe", "")),
                    str((row.get("raw_objectives", {}) or {}).get("max_drawdown_abs", "")),
                    str((row.get("raw_objectives", {}) or {}).get("turnover_proxy", "")),
                    str((row.get("raw_objectives", {}) or {}).get("neg_rank_ic_mean", "")),
                    str((row.get("raw_objectives", {}) or {}).get("rank_ic_std", "")),
                    str(row.get("fold_count", "")),
                ]
            )
            + " |"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "summary_json": str(summary_path),
        "table_csv": str(table_path),
        "table_md": str(md_path),
    }


__all__ = ["write_search_report"]
