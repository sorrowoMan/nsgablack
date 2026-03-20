from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from .contracts import CatalogBundle
from .registry import CatalogEntry, get_catalog
from .sync import build_catalog_bundle


def _render_markdown(entries: Iterable[CatalogEntry], bundle: CatalogBundle, *, profile: str) -> str:
    lines: List[str] = []
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"# COMPONENT API INDEX ({profile})")
    lines.append("")
    lines.append(f"Generated at: {stamp}")
    lines.append("")

    context_map = {c.component_key: c for c in bundle.contexts}
    usage_map = {u.component_key: u for u in bundle.usages}
    health_map = {h.component_key: h for h in bundle.health}
    method_map: dict[str, list[str]] = {}
    for m in bundle.methods:
        status = "ok" if m.implemented else "missing"
        if m.required and not m.implemented:
            status = "missing(required)"
        token = f"{m.name}={status}"
        method_map.setdefault(m.component_key, []).append(token)

    for e in entries:
        lines.append(f"## `{e.key}`")
        lines.append(f"Kind: {e.kind}")
        lines.append(f"Title: {e.title}")
        lines.append(f"Import: `{e.import_path}`")
        if e.summary:
            lines.append(f"Summary: {e.summary}")
        if e.tags:
            lines.append("Tags: " + ", ".join(e.tags))

        ctx = context_map.get(e.key)
        if ctx:
            if ctx.requires or ctx.provides or ctx.mutates or ctx.cache or ctx.notes:
                if ctx.requires:
                    lines.append("Context requires: " + ", ".join(ctx.requires))
                if ctx.provides:
                    lines.append("Context provides: " + ", ".join(ctx.provides))
                if ctx.mutates:
                    lines.append("Context mutates: " + ", ".join(ctx.mutates))
                if ctx.cache:
                    lines.append("Context cache: " + ", ".join(ctx.cache))
                if ctx.notes:
                    lines.append("Context notes: " + " | ".join(ctx.notes))

        usage = usage_map.get(e.key)
        if usage:
            if usage.config_keys:
                lines.append("Config keys: " + ", ".join(usage.config_keys))
            if usage.use_when:
                lines.append("Use when: " + " | ".join(usage.use_when))
            if usage.minimal_wiring:
                lines.append("Minimal wiring: " + " | ".join(usage.minimal_wiring))

        methods = method_map.get(e.key, [])
        if methods:
            lines.append("Methods: " + ", ".join(methods))

        health = health_map.get(e.key)
        if health:
            lines.append(
                "Health: "
                f"import_ok={health.import_ok} context_ok={health.context_ok} "
                f"methods_ok={health.methods_ok} params_ok={health.params_ok}"
            )
            if health.issues:
                lines.append("Health issues: " + " | ".join(health.issues))

        lines.append("")
    return "\n".join(lines)


def export_catalog_docs(*, profile: str, output_path: Path) -> None:
    catalog = get_catalog(profile=profile)
    bundle = build_catalog_bundle(profile=profile, runtime=False)
    content = _render_markdown(catalog.list(), bundle, profile=profile)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def export_default_docs() -> list[Path]:
    out: list[Path] = []
    mapping = {
        "default": Path("docs/development/COMPONENT_API_INDEX_FULL_CN.md"),
        "framework-core": Path("docs/development/COMPONENT_API_INDEX_FRAMEWORK_CORE_CN.md"),
    }
    for profile, path in mapping.items():
        export_catalog_docs(profile=profile, output_path=path)
        out.append(path)
    return out
