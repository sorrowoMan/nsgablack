from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(raw) for key, raw in dict(value).items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    return str(value)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    items = [dict(row) for row in rows]
    if not items:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in items:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(items)


def write_search_report(*, output_dir: Path, summary: Mapping[str, Any], records: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "phi_bundle_outer_summary.json"
    table_path = output_dir / "phi_bundle_outer_table.csv"
    md_path = output_dir / "phi_bundle_outer_table.md"
    summary_path.write_text(json.dumps(_jsonable(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    flat_rows = []
    for row in records:
        metrics = dict(row.get("metrics", {}) or {})
        rep = dict(row.get("representation_report", {}) or {})
        src = dict(row.get("source_report", {}) or {})
        bundle = dict(row.get("bundle", {}) or {})
        lane_params = tuple(dict(lane) for lane in tuple(bundle.get("lanes", ()) or ()) if isinstance(lane, Mapping))
        flat_rows.append(
            {
                "label": row.get("label", ""),
                "score": row.get("score", ""),
                "objectives": row.get("objectives", ""),
                "best_accuracy": metrics.get("best_accuracy", ""),
                "best_feature_space": metrics.get("best_feature_space", ""),
                "selected_accuracy": metrics.get("selected_accuracy", ""),
                "augmented_accuracy": metrics.get("augmented_accuracy", ""),
                "allowed_families": rep.get("allowed_families", ""),
                "allowed_lanes": rep.get("allowed_lanes", ""),
                "lane_params": lane_params,
                "selected_count": rep.get("selected_count", ""),
                "selected_source_count": src.get("selected_source_count", ""),
                "mean_source_stability": src.get("mean_source_stability", ""),
                "pair_abs_corr_mean": src.get("pair_abs_corr_mean", ""),
                "artifact_dir": row.get("artifact_dir", ""),
            }
        )
    _write_csv(table_path, flat_rows)
    lines = [
        "# Phi Bundle Outer Search",
        "",
        "| label | score | best_accuracy | best_feature_space | allowed_families | selected_count | selected_source_count |",
        "| --- | ---: | ---: | --- | --- | ---: | ---: |",
    ]
    for row in flat_rows:
        lines.append(
            "| "
            + " | ".join(
                str(row.get(col, "")).strip()
                for col in (
                    "label",
                    "score",
                    "best_accuracy",
                    "best_feature_space",
                    "allowed_families",
                    "selected_count",
                    "selected_source_count",
                )
            )
            + " |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "summary_json": str(summary_path),
        "table_csv": str(table_path),
        "table_md": str(md_path),
    }


__all__ = ["write_search_report"]
