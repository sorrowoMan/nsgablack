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
        prior = dict(record.get("prior_summary", {}) or {})
        raw_terms = dict(record.get("raw_objective_terms", {}) or {})
        weighted_terms = dict(record.get("weighted_objective_terms", {}) or {})
        rows.append(
            {
                "label": str(record.get("label", "")),
                "search_mode": str(record.get("search_mode", "")),
                "score": float(record.get("score", 0.0) or 0.0),
                "strict_primary_loss": float(record.get("strict_primary_loss", record.get("score", 0.0)) or 0.0),
                "classification_error": float(raw_terms.get("classification_error", 0.0) or 0.0),
                "generalization_gap": float(raw_terms.get("generalization_gap", metrics.get("generalization_gap", 0.0)) or 0.0),
                "feature_complexity": float(raw_terms.get("feature_complexity", 0.0) or 0.0),
                "kernel_prior_penalty": float(raw_terms.get("kernel_prior_penalty", 0.0) or 0.0),
                "weighted_accuracy_term": float(weighted_terms.get("accuracy", 0.0) or 0.0),
                "weighted_gap_term": float(weighted_terms.get("gap", 0.0) or 0.0),
                "weighted_complexity_term": float(weighted_terms.get("complexity", 0.0) or 0.0),
                "weighted_prior_term": float(weighted_terms.get("prior", 0.0) or 0.0),
                "test_accuracy": float(metrics.get("test_accuracy", 0.0) or 0.0),
                "test_macro_f1": float(metrics.get("test_macro_f1", 0.0) or 0.0),
                "pipeline_output_dim": int(record.get("pipeline_output_dim", 0) or 0),
                "term_count": int(prior.get("term_count", 0) or 0),
                "prior_strength": float(prior.get("prior_strength", 0.0) or 0.0),
                "symbolic_basis_terms": json.dumps(dict(bundle.get("symbolic_kernel_object", {}) or {}).get("basis_terms", []), ensure_ascii=False),
                "symbolic_kernel_weights": json.dumps(bundle.get("symbolic_kernel_weights", []), ensure_ascii=False),
                "coefficients": json.dumps(bundle.get("coefficients", []), ensure_ascii=False),
                "kernel_shape": json.dumps(bundle.get("kernel_shape", []), ensure_ascii=False),
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
    summary_dict = dict(summary)
    best = dict(summary_dict.get("best_result", {}) or {})
    best_accuracy = dict(summary_dict.get("best_accuracy_result", {}) or {})
    best_macro_f1 = dict(summary_dict.get("best_macro_f1_result", {}) or {})
    cache_summary = dict(dict(summary).get("structure_cache", {}) or {})
    top_accuracy_rows = sorted(rows, key=lambda row: float(row.get("test_accuracy", 0.0) or 0.0), reverse=True)[:5]
    top_score_rows = sorted(rows, key=lambda row: float(row.get("score", 0.0) or 0.0))[:5]
    lines = [
        "# Symbolic Kernel Digits Outer Search",
        "",
        f"- suite_id: `{summary.get('suite_id')}`",
        f"- search_protocol: `{summary.get('protocol')}`",
        f"- evaluation_count: `{summary.get('evaluation_count')}`",
        f"- unique_structure_count: `{cache_summary.get('unique_structure_count')}`",
        f"- cache_hit_rate: `{cache_summary.get('cache_hit_rate')}`",
        f"- best_score: `{best.get('score')}`",
        f"- best_strict_primary_loss: `{best.get('strict_primary_loss')}`",
        f"- best_score_bundle: `{best.get('bundle')}`",
        f"- best_score_metrics: `{best.get('metrics')}`",
        f"- best_score_raw_objective_terms: `{best.get('raw_objective_terms')}`",
        f"- best_score_weighted_objective_terms: `{best.get('weighted_objective_terms')}`",
        f"- best_score_prior_summary: `{best.get('prior_summary')}`",
        f"- best_accuracy: `{dict(best_accuracy.get('metrics', {}) or {}).get('test_accuracy')}`",
        f"- best_accuracy_bundle: `{best_accuracy.get('bundle')}`",
        f"- best_accuracy_metrics: `{best_accuracy.get('metrics')}`",
        f"- best_accuracy_raw_objective_terms: `{best_accuracy.get('raw_objective_terms')}`",
        f"- best_accuracy_weighted_objective_terms: `{best_accuracy.get('weighted_objective_terms')}`",
        f"- best_macro_f1: `{dict(best_macro_f1.get('metrics', {}) or {}).get('test_macro_f1')}`",
        f"- best_macro_f1_bundle: `{best_macro_f1.get('bundle')}`",
        f"- best_macro_f1_metrics: `{best_macro_f1.get('metrics')}`",
        "",
        "## Top By Accuracy",
        "",
        "| label | test_accuracy | test_macro_f1 | score | pipeline_output_dim | basis_terms | kernel_shape | stride_shape | padding | pooling | output_mode |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in top_accuracy_rows:
        lines.append(
            "| {label} | {test_accuracy:.6f} | {test_macro_f1:.6f} | {score:.6f} | {pipeline_output_dim} | {basis} | {kernel_shape} | {stride_shape} | {padding} | {pooling} | {output_mode} |".format(
                label=str(row.get("label", "")),
                test_accuracy=float(row.get("test_accuracy", 0.0) or 0.0),
                test_macro_f1=float(row.get("test_macro_f1", 0.0) or 0.0),
                score=float(row.get("score", 0.0) or 0.0),
                pipeline_output_dim=int(row.get("pipeline_output_dim", 0) or 0),
                basis=str(row.get("symbolic_basis_terms", "")),
                kernel_shape=str(row.get("kernel_shape", "")),
                stride_shape=str(row.get("stride_shape", "")),
                padding=str(row.get("padding", "")),
                pooling=str(row.get("pooling", "")),
                output_mode=str(row.get("output_mode", "")),
            )
        )
    lines.extend(
        [
            "",
            "## Top By Score",
            "",
            "| label | test_accuracy | test_macro_f1 | score | pipeline_output_dim | basis_terms | kernel_shape | stride_shape | padding | pooling | output_mode |",
            "| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in top_score_rows:
        lines.append(
            "| {label} | {test_accuracy:.6f} | {test_macro_f1:.6f} | {score:.6f} | {pipeline_output_dim} | {basis} | {kernel_shape} | {stride_shape} | {padding} | {pooling} | {output_mode} |".format(
                label=str(row.get("label", "")),
                test_accuracy=float(row.get("test_accuracy", 0.0) or 0.0),
                test_macro_f1=float(row.get("test_macro_f1", 0.0) or 0.0),
                score=float(row.get("score", 0.0) or 0.0),
                pipeline_output_dim=int(row.get("pipeline_output_dim", 0) or 0),
                basis=str(row.get("symbolic_basis_terms", "")),
                kernel_shape=str(row.get("kernel_shape", "")),
                stride_shape=str(row.get("stride_shape", "")),
                padding=str(row.get("padding", "")),
                pooling=str(row.get("pooling", "")),
                output_mode=str(row.get("output_mode", "")),
            )
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "summary_json": str(summary_path),
        "records_csv": str(table_path),
        "report_md": str(report_path),
    }


__all__ = ["write_search_report"]
