"""Read-only presentation of workspace experiment evidence.

These helpers compare recorded facts.  They do not evaluate candidates, infer
final Unit members from accepted history, or choose a multi-objective ranking.
The current trial report only hashes explicitly observed data files; matching
those files does not establish equality of every possible external input.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping


_STATUS = {"queued": "排队中", "running": "运行中", "succeeded": "已完成",
           "failed": "运行失败", "interrupted": "已中断", "cancelled": "已取消"}
_MEASURES = (("steps", "逻辑提交步", "步"),
             ("evaluations", "实际评估次数", "次"),
             ("elapsed_seconds", "运行耗时", "秒"))
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_MISSING_HANDOFF = "当前报告未提供最终成员、精英池、精修结果与返回接纳之间的逐解对应关系。"


def _mapping(value) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _finite(value) -> bool:
    return type(value) is int or type(value) is float and math.isfinite(value)


def _plain(value, *, depth: int = 0):
    """Detach JSON values without copying arbitrary Python object graphs."""
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        return value if math.isfinite(value) else None
    if depth >= 16:
        return None
    if isinstance(value, Mapping):
        return {key: _plain(item, depth=depth + 1) for key, item in value.items()
                if type(key) is str}
    if type(value) in {list, tuple}:
        return [_plain(item, depth=depth + 1) for item in value]
    return None


def _measure_values(result: Mapping) -> dict:
    values = {}
    for key in ("steps", "evaluations"):
        value = result.get(key)
        values[key] = value if type(value) is int and value >= 0 else None
    elapsed = result.get("elapsed_seconds")
    if not _finite(elapsed) or elapsed < 0:
        elapsed = result.get("duration_seconds")
    values["elapsed_seconds"] = elapsed if _finite(elapsed) and elapsed >= 0 else None
    return values


def _metric_rows(value) -> list[dict]:
    rows = []

    def visit(report, *, source: str, path=()):
        if len(rows) >= 128 or len(path) >= 8:
            return
        if isinstance(report, Mapping):
            for key, item in report.items():
                if type(key) is str:
                    visit(item, source=source, path=(*path, key))
        elif path and _finite(report):
            pointer = "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in path)
            rows.append({"key": source + "#" + pointer,
                         "label": (source + " · " if source else "") + " / ".join(path),
                         "value": report})
        # Lists can contain objective vectors or distributions.  They are not
        # individual scalar metrics with a known comparison interpretation.

    if isinstance(value, Mapping):
        visit(value, source="")
    elif type(value) in {list, tuple}:
        for item in value:
            item = _mapping(item)
            source = item.get("path")
            if type(source) is str and source:
                visit(item.get("report"), source=source)
    return rows


def describe_result(job: Mapping) -> dict:
    """Make a UI view of one job while preserving the report's evidence scope."""
    if not isinstance(job, Mapping):
        raise TypeError("experiment must be a Mapping")
    result = _mapping(job.get("result"))
    status = job.get("status")
    status = status if type(status) is str else "unknown"
    succeeded = (status == "succeeded" and bool(result) and result.get("success") is not False
                 and result.get("status") not in ("failed", "interrupted", "cancelled"))
    warnings, missing = [], []
    if status == "succeeded" and not succeeded:
        warnings.append("任务状态与结果状态不一致，请查看本次运行依据。")
    if not succeeded:
        missing.append("本次任务尚未交付成功结果，已有记录不构成算法效果验证。")
    if not result:
        missing.append("尚无运行报告。")
    values = _measure_values(result)
    measures = [{"key": key, "label": label, "value": values[key], "unit": unit}
                for key, label, unit in _MEASURES]
    if result and any(item["value"] is None for item in measures):
        warnings.append("部分运行计数或耗时缺失或无效，未将其显示为零。")
    raw = _mapping(result.get("raw_results"))
    scope = raw.get("scope") if type(raw.get("scope")) is str else None
    scope_label = ("最近 16 条接纳历史（不是算法最终成员）" if scope == "last_16_accepted"
                   else "报告中的候选切片（范围未核验）" if raw else "尚无候选切片")
    rows = []
    if raw:
        candidates, objectives, violations = (raw.get(key) for key in
                                               ("candidates", "raw_objectives", "raw_violations"))
        aligned = (all(type(value) in {list, tuple} for value in (candidates, objectives, violations))
                   and len(candidates) == len(objectives) == len(violations))
        if not aligned:
            warnings.append("候选与原始反馈行数不一致，未生成可能错配的候选表。")
        else:
            refs = raw.get("refs")
            refs = refs if type(refs) in {list, tuple} else ()
            aligned_refs = len(refs) == len(candidates)
            if not aligned_refs and candidates:
                warnings.append("精确候选引用缺失或未对齐，未按数值相等推断身份。")
            for index, (candidate, objective, violation) in enumerate(zip(candidates, objectives, violations)):
                valid = (type(candidate) in {list, tuple}
                         and type(objective) in {list, tuple} and bool(objective)
                         and all(_finite(value) for value in (*candidate, *objective))
                         and _finite(violation))
                if not valid:
                    warnings.append(f"候选切片第 {index + 1} 行包含缺失或非有限数值，未用于候选表。")
                    continue
                rows.append({"index": index, "candidate": _plain(candidate),
                             "raw_objectives": _plain(objective), "raw_violation": violation,
                             "solution_ref": _plain(refs[index]) if aligned_refs else None})
        missing.append(_MISSING_HANDOFF)
    elif succeeded:
        missing.extend(("当前报告没有原始候选与反馈切片。", _MISSING_HANDOFF))
    metric_rows = _metric_rows(result.get("metrics"))
    if metric_rows:
        warnings.append("业务指标按报告原值显示；未声明优化方向，不自动判断变好或变差。")
    return {"status": status, "status_label": _STATUS.get(status, "状态未知"),
            "succeeded": succeeded, "measures": measures, "raw_rows": rows,
            "scope": scope, "scope_label": scope_label, "metric_rows": metric_rows,
            "missing_evidence": missing, "warnings": warnings}


def _same_value(left, right):
    if type(left) is not str or not left or type(right) is not str or not right:
        return None
    return left == right


def _snapshot(job: Mapping):
    declared = job.get("source_digest")
    reported = _mapping(job.get("result")).get("project_revision")
    valid = lambda item: type(item) is str and _DIGEST.fullmatch(item) is not None
    if declared is not None and reported is not None and declared != reported:
        return None
    return declared if valid(declared) else reported if valid(reported) else None


def _data_files(job: Mapping):
    data = _mapping(_mapping(job.get("result")).get("effective_data"))
    files = data.get("files")
    if data.get("unresolved_path_fields") or not isinstance(files, Mapping) or not files:
        return None
    captured = {}
    for name, row in files.items():
        row = _mapping(row)
        path, digest, size = row.get("path"), row.get("sha256"), row.get("size_bytes")
        if (type(name) is not str or not name or type(path) is not str or not path
                or type(digest) is not str or _DIGEST.fullmatch(digest) is None
                or type(size) is not int or size < 0):
            return None
        captured[name] = {"path": path, "sha256": digest, "size_bytes": size}
    return captured


def _proposal(job: Mapping) -> Mapping:
    return _mapping(job.get("proposal") or _mapping(job.get("result")).get("proposal"))


def _delta(current, baseline):
    if not _finite(current) or not _finite(baseline):
        return None
    try:
        delta = current - baseline
    except OverflowError:
        return None
    return delta if _finite(delta) else None


def compare_experiments(job: Mapping, baseline: Mapping) -> dict:
    """Compare two recorded experiments without claiming comparable quality.

    ``can_compare`` means the same workspace and Case have been identified.  It
    permits factual configuration/resource deltas, not a claim of improvement.
    ``data_status`` covers only explicitly hashed observed files.
    """
    if not isinstance(job, Mapping) or not isinstance(baseline, Mapping):
        raise TypeError("experiments must be Mappings")
    same_workspace = _same_value(job.get("workspace_id"), baseline.get("workspace_id"))
    same_case = _same_value(job.get("case_name"), baseline.get("case_name"))
    same_snapshot = _same_value(_snapshot(job), _snapshot(baseline))
    reasons, notices = [], []
    if same_workspace is not True:
        reasons.append("两个实验不属于同一工作区。" if same_workspace is False else "工作区身份缺失，无法核对。")
    if same_case is not True:
        reasons.append("两个实验运行的 Case 不同。" if same_case is False else "Case 身份缺失，无法核对。")
    if same_snapshot is False:
        notices.append("两个实验使用了不同工程快照，差异可能包括 Problem、算法和输入文件。")
    elif same_snapshot is None:
        notices.append("工程快照摘要缺失或不一致，尚未核对源码一致性。")
    current_data, base_data = _data_files(job), _data_files(baseline)
    if current_data is None or base_data is None:
        data_status, data_label = "unverified", "缺少可对齐的数据文件摘要，未核验输入数据一致性。"
    elif current_data == base_data:
        data_status, data_label = "matched", "已登记数据文件一致；未声明的输入尚未核验。"
    else:
        data_status, data_label = "different", "已登记数据文件不同，请结合数据变化解释结果。"
    notices.append(data_label)
    current_view, base_view = describe_result(job), describe_result(baseline)
    if not current_view["succeeded"] or not base_view["succeeded"]:
        notices.append("至少一个实验没有成功结果，仅对照已有运行事实。")
    notices.append("差值为当前实验减去基线；指标方向和最终成员未核验，不据此判定算法优劣。")
    can_compare = not reasons
    configuration, measures, metrics = [], [], []
    if can_compare:
        current_proposal, base_proposal = _proposal(job), _proposal(baseline)

        def config_row(key, label, current, before, current_present=True, baseline_present=True):
            configuration.append({"key": key, "label": label,
                                  "current": _plain(current), "baseline": _plain(before),
                                  "current_present": current_present, "baseline_present": baseline_present,
                                  "changed": current_present != baseline_present or current != before})

        config_row("revision_id", "代码版本", job.get("revision_id"), baseline.get("revision_id"))
        config_row("source_digest", "工程快照", _snapshot(job), _snapshot(baseline))
        config_row("seed", "随机种子", current_proposal.get("seed"), base_proposal.get("seed"),
                   "seed" in current_proposal, "seed" in base_proposal)
        current_budget, base_budget = (_mapping(item.get("budget")) for item in (current_proposal, base_proposal))
        for key, label in (("max_steps", "逻辑步预算"), ("timeout_seconds", "超时预算（秒）")):
            config_row("budget." + key, label, current_budget.get(key), base_budget.get(key),
                       key in current_budget, key in base_budget)
        current_parameters, base_parameters = (_mapping(item.get("parameters")) for item in (current_proposal, base_proposal))
        for key in sorted(key for key in current_parameters.keys() | base_parameters.keys() if type(key) is str):
            config_row("parameters." + key, "参数 · " + key,
                       current_parameters.get(key), base_parameters.get(key),
                       key in current_parameters, key in base_parameters)
        current_values = {item["key"]: item["value"] for item in current_view["measures"]}
        base_values = {item["key"]: item["value"] for item in base_view["measures"]}
        measures = [{"key": key, "label": label, "current": current_values[key],
                     "baseline": base_values[key], "delta": _delta(current_values[key], base_values[key]),
                     "unit": unit} for key, label, unit in _MEASURES]
        current_metrics = {item["key"]: item for item in current_view["metric_rows"]}
        base_metrics = {item["key"]: item for item in base_view["metric_rows"]}
        for key in sorted(current_metrics.keys() | base_metrics.keys()):
            current, before = current_metrics.get(key), base_metrics.get(key)
            metrics.append({"key": key, "label": (current or before)["label"],
                            "current": current["value"] if current else None,
                            "baseline": before["value"] if before else None,
                            "delta": _delta(current["value"], before["value"]) if current and before else None})
    return {"can_compare": can_compare, "reasons": reasons, "notices": notices,
            "same_workspace": same_workspace, "same_case": same_case,
            "same_snapshot": same_snapshot, "data_status": data_status, "data_label": data_label,
            "configuration_rows": configuration, "measure_rows": measures, "metric_rows": metrics,
            "quality_conclusion": None}


__all__ = ["describe_result", "compare_experiments"]
