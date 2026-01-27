"""
轻量依赖检查工具。

提供快速依赖检测报告，便于在求解器初始化时提前提示缺失依赖。
"""
from __future__ import annotations

import importlib
import importlib.util
from importlib import metadata
from typing import Dict, Iterable, Optional, Tuple


def _get_version(pkg: str) -> Optional[str]:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return None
    except Exception:
        return None


def check_dependency(pkg: str, min_version: Optional[str] = None) -> Dict[str, Optional[str]]:
    """检查单个依赖的可用性与版本。"""
    spec = importlib.util.find_spec(pkg)
    available = spec is not None
    version = _get_version(pkg) if available else None
    meets_min = None
    if available and min_version and version:
        try:
            from packaging import version as packaging_version

            meets_min = packaging_version.parse(version) >= packaging_version.parse(min_version)
        except Exception:
            meets_min = None
    return {
        "name": pkg,
        "available": available,
        "version": version,
        "meets_min": meets_min,
        "min_required": min_version,
    }


def dependency_report(
    required: Iterable[Tuple[str, Optional[str]]] = (),
    optional: Iterable[Tuple[str, Optional[str]]] = (),
) -> Dict[str, Dict[str, Optional[str]]]:
    """生成依赖报告，区分必需与可选。"""
    req_report = {name: check_dependency(name, min_ver) for name, min_ver in required}
    opt_report = {name: check_dependency(name, min_ver) for name, min_ver in optional}
    return {"required": req_report, "optional": opt_report}


def ensure_dependencies(
    required: Iterable[Tuple[str, Optional[str]]],
    raise_on_missing: bool = True,
    logger=None,
) -> Dict[str, Dict[str, Optional[str]]]:
    """验证必需依赖；缺失或不满足版本时可选择抛错。"""
    report = dependency_report(required=required, optional=())
    missing = []
    for name, info in report["required"].items():
        if not info["available"]:
            missing.append(f"{name} (missing)")
        elif info["meets_min"] is False:
            missing.append(
                f"{name} (requires >= {info['min_required']}, found {info['version']})"
            )

    if missing:
        message = "Missing or incompatible dependencies: " + ", ".join(missing)
        if logger:
            logger.error(message)
        if raise_on_missing:
            raise ImportError(message)
    return report


def summarize_report(report: Dict[str, Dict[str, Dict[str, Optional[str]]]]) -> str:
    """将依赖报告转换为可读字符串。"""
    lines = []
    for section in ("required", "optional"):
        lines.append(f"[{section}]")
        for name, info in report.get(section, {}).items():
            status = "ok" if info["available"] else "missing"
            version = info.get("version") or "-"
            extra = ""
            if info.get("meets_min") is False:
                extra = f" (< {info['min_required']})"
            lines.append(f"- {name}: {status}, version={version}{extra}")
    return "\n".join(lines)
