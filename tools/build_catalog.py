import ast
import datetime as dt
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_defs(text: str) -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]]]:
    classes: List[Tuple[str, int]] = []
    funcs: List[Tuple[str, int]] = []
    try:
        tree = ast.parse(text)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                name = node.name
                if not name.startswith("_"):
                    classes.append((name, node.lineno))
            elif isinstance(node, ast.FunctionDef):
                name = node.name
                if not name.startswith("_"):
                    funcs.append((name, node.lineno))
        return classes, funcs
    except SyntaxError:
        pass

    for idx, line in enumerate(text.splitlines(), 1):
        if line.lstrip() != line:
            continue
        class_match = re.match(r"class\s+([A-Za-z_]\w*)", line)
        if class_match:
            name = class_match.group(1)
            if not name.startswith("_"):
                classes.append((name, idx))
            continue
        func_match = re.match(r"def\s+([A-Za-z_]\w*)", line)
        if func_match:
            name = func_match.group(1)
            if not name.startswith("_"):
                funcs.append((name, idx))
    return classes, funcs


def _module_summary(text: str) -> str:
    try:
        tree = ast.parse(text)
        doc = ast.get_docstring(tree)
        if doc:
            return doc.strip().splitlines()[0].strip()
    except SyntaxError:
        pass

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        if stripped:
            break
    return ""


def _iter_py_files(base: Path) -> Iterable[Path]:
    if base.is_file():
        if base.suffix == ".py":
            yield base
        return
    for path in sorted(base.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def _format_defs(classes: List[Tuple[str, int]], funcs: List[Tuple[str, int]]) -> List[str]:
    lines: List[str] = []
    if classes:
        items = ", ".join([f"{name} (L{line})" for name, line in classes])
        lines.append(f"  - 类: {items}")
    if funcs:
        items = ", ".join([f"{name} (L{line})" for name, line in funcs])
        lines.append(f"  - 函数: {items}")
    return lines


def _write_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _header(title: str) -> List[str]:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return [
        f"# {title}",
        "",
        f"生成时间: {now}",
        "",
    ]


def build_tools_index() -> str:
    sections = _header("工具索引")
    targets = [
        ("core（核心）", ROOT / "core"),
        ("solvers（求解器）", ROOT / "solvers"),
        ("multi_agent（多智能体）", ROOT / "multi_agent"),
        ("utils（工具）", ROOT / "utils"),
        ("surrogate（代理模型）", ROOT / "surrogate"),
        ("ml（机器学习）", ROOT / "ml"),
        ("algorithms（算法）", ROOT / "algorithms"),
        ("architecture（架构）", ROOT / "architecture"),
        ("development（开发）", ROOT / "development"),
    ]

    for name, base in targets:
        if not base.exists():
            continue
        sections.append(f"## {name}")
        sections.append("")
        for path in _iter_py_files(base):
            rel = path.relative_to(ROOT).as_posix()
            text = _read_text(path)
            classes, funcs = _extract_defs(text)
            if not classes and not funcs:
                continue
            sections.append(f"- {rel}")
            sections.extend(_format_defs(classes, funcs))
        sections.append("")
    return "\n".join(sections).rstrip() + "\n"


def build_bias_index() -> str:
    sections = _header("偏置索引")
    bias_root = ROOT / "bias"
    if not bias_root.exists():
        sections.append("未找到 bias 目录。")
        return "\n".join(sections).rstrip() + "\n"

    groups: Dict[str, List[Path]] = {}
    for path in _iter_py_files(bias_root):
        rel = path.relative_to(bias_root).as_posix()
        group = rel.split("/")[0] if "/" in rel else "root"
        groups.setdefault(group, []).append(path)

    group_map = {
        "algorithmic": "algorithmic（算法偏置）",
        "domain": "domain（领域偏置）",
        "specialized": "specialized（专用偏置）",
        "managers": "managers（管理器）",
        "core": "core（核心）",
        "utils": "utils（工具）",
        "root": "root（根目录）",
    }
    for group in sorted(groups.keys()):
        sections.append(f"## {group_map.get(group, group)}")
        sections.append("")
        for path in sorted(groups[group]):
            rel = path.relative_to(ROOT).as_posix()
            text = _read_text(path)
            classes, funcs = _extract_defs(text)
            if not classes and not funcs:
                continue
            sections.append(f"- {rel}")
            sections.extend(_format_defs(classes, funcs))
        sections.append("")
    return "\n".join(sections).rstrip() + "\n"


def build_representation_index() -> str:
    sections = _header("表征索引")
    base = ROOT / "utils" / "representation"
    if not base.exists():
        sections.append("未找到 representation 目录。")
        return "\n".join(sections).rstrip() + "\n"

    sections.append("## representation（表征/编码）")
    sections.append("")
    for path in _iter_py_files(base):
        rel = path.relative_to(ROOT).as_posix()
        text = _read_text(path)
        classes, funcs = _extract_defs(text)
        if not classes and not funcs:
            continue
        sections.append(f"- {rel}")
        sections.extend(_format_defs(classes, funcs))
    sections.append("")
    return "\n".join(sections).rstrip() + "\n"


def build_examples_index() -> str:
    sections = _header("示例索引")
    base = ROOT / "examples"
    if not base.exists():
        sections.append("未找到 examples 目录。")
        return "\n".join(sections).rstrip() + "\n"

    sections.append("## examples（示例脚本）")
    sections.append("")
    for path in sorted(base.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if path.name == "__init__.py":
            continue
        rel = path.relative_to(ROOT).as_posix()
        text = _read_text(path)
        summary = _module_summary(text)
        if summary:
            sections.append(f"- {rel} - {summary}")
        else:
            sections.append(f"- {rel}")
    sections.append("")
    sections.append("## notebooks（Notebook）")
    sections.append("")
    sections.append("- examples/jupyter_tutorials/zh/（Notebook 文件夹）")
    sections.append("")
    return "\n".join(sections).rstrip() + "\n"


def build_catalog_index() -> str:
    sections = _header("项目目录索引")
    sections.extend(
        [
            "索引文件：",
            "",
            "- docs/TOOLS_INDEX.md",
            "- docs/BIAS_INDEX.md",
            "- docs/REPRESENTATION_INDEX.md",
            "- docs/EXAMPLES_INDEX.md",
            "",
            "如何更新：",
            "",
            "  python tools/build_catalog.py",
            "",
        ]
    )
    return "\n".join(sections).rstrip() + "\n"


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    _write_file(DOCS / "TOOLS_INDEX.md", build_tools_index())
    _write_file(DOCS / "BIAS_INDEX.md", build_bias_index())
    _write_file(DOCS / "REPRESENTATION_INDEX.md", build_representation_index())
    _write_file(DOCS / "EXAMPLES_INDEX.md", build_examples_index())
    _write_file(DOCS / "PROJECT_CATALOG.md", build_catalog_index())


if __name__ == "__main__":
    main()
