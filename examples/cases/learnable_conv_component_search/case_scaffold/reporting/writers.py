from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


def _json_default(value: Any):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return str(value)


def _record_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        bundle = dict(record.get("bundle", {}) or {})
        metrics = dict(record.get("metrics", {}) or {})
        rows.append(
            {
                "label": str(record.get("label", "")),
                "search_mode": str(record.get("search_mode", "")),
                "score": float(record.get("score", 0.0) or 0.0),
                "legacy_score": float(record.get("legacy_score", 0.0) or 0.0),
                "test_rmse": float(metrics.get("test_rmse", 0.0) or 0.0),
                "generalization_gap": float(metrics.get("generalization_gap", 0.0) or 0.0),
                "pipeline_output_dim": int(record.get("pipeline_output_dim", 0) or 0),
                "kernel_l2_distance": float(dict(record.get("kernel_alignment", {}) or {}).get("kernel_l2_distance", 0.0) or 0.0),
                "kernel_cosine_similarity": float(dict(record.get("kernel_alignment", {}) or {}).get("kernel_cosine_similarity", 0.0) or 0.0),
                "kernel_recovery_penalty": float(record.get("kernel_recovery_penalty", 0.0) or 0.0),
                "refinement_mode": str(dict(record.get("refinement", {}) or {}).get("mode", "")),
                "refinement_eval_count": int(dict(record.get("refinement", {}) or {}).get("evaluation_count", 0) or 0),
                "refinement_best_score": float(dict(record.get("refinement", {}) or {}).get("best_score", 0.0) or 0.0),
                "symbolic_basis_terms": json.dumps(dict(bundle.get("symbolic_kernel_object", {}) or {}).get("basis_terms", []), ensure_ascii=False),
                "symbolic_kernel_weights": json.dumps(bundle.get("symbolic_kernel_weights", []), ensure_ascii=False),
                "coefficients": json.dumps(bundle.get("coefficients", []), ensure_ascii=False),
                "kernel_shape": json.dumps(bundle.get("kernel_shape", []), ensure_ascii=False),
                "include_input": bool(bundle.get("include_input", False)),
                "stride": int(bundle.get("stride", 1) or 1),
                "stride_shape": json.dumps(bundle.get("stride_shape", []), ensure_ascii=False),
                "padding": str(bundle.get("padding", "")),
                "pooling": str(bundle.get("pooling", "")),
                "output_mode": str(bundle.get("output_mode", "")),
            }
        )
    return rows


def write_search_report(
    *,
    output_dir: str | Path,
    summary: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    summary_path = root / "summary.json"
    table_path = root / "records.csv"
    report_path = root / "report.md"
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(dict(summary), fh, indent=2, ensure_ascii=False, default=_json_default)
    rows = _record_rows(records)
    with table_path.open("w", encoding="utf-8", newline="") as fh:
        if rows:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        else:
            fh.write("")
    best = dict(dict(summary).get("best_result", {}) or {})
    cache_summary = dict(dict(summary).get("structure_cache", {}) or {})
    lines = [
        "# Learnable Conv Component Search",
        "",
        f"- suite_id: `{summary.get('suite_id')}`",
        f"- search_protocol: `{summary.get('protocol')}`",
        f"- evaluation_count: `{summary.get('evaluation_count')}`",
        f"- unique_structure_count: `{cache_summary.get('unique_structure_count')}`",
        f"- structure_cache_hit_count: `{cache_summary.get('cache_hit_count')}`",
        f"- structure_cache_miss_count: `{cache_summary.get('cache_miss_count')}`",
        f"- structure_cache_hit_rate: `{cache_summary.get('cache_hit_rate')}`",
        f"- best_score: `{best.get('score')}`",
        f"- best_legacy_score: `{best.get('legacy_score')}`",
        f"- best_refinement: `{best.get('refinement')}`",
        f"- best_bundle: `{best.get('bundle')}`",
        f"- best_metrics: `{best.get('metrics')}`",
        f"- best_kernel_alignment: `{best.get('kernel_alignment')}`",
        f"- best_kernel_recovery_penalty: `{best.get('kernel_recovery_penalty')}`",
        f"- best_symbolic_terms: `{dict(dict(best).get('bundle', {}) or {}).get('symbolic_kernel_object', {})}`",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "summary_json": str(summary_path),
        "records_csv": str(table_path),
        "report_md": str(report_path),
    }


__all__ = ["write_search_report"]
