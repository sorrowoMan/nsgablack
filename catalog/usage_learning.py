"""Explain a published fragment's placement and external names without imports."""
from __future__ import annotations

import builtins
import posixpath
import re
from typing import Any, Sequence
import symtable
from collections.abc import Mapping


_EXTERNAL_OBJECTS = {
    "solver": "`solver` 是本 Case 的 `build_solver()` 中创建的求解器。把挂载代码放在创建它之后、`return solver` 之前。",
    "problem": "`problem` 来自本 Case 的问题工厂 `build_problem()`，负责原始目标、约束和候选含义。",
    "pipeline": "`pipeline` 来自本 Case 的候选管线工厂 `build_pipeline()`；把初始化、变化或问题修复组件接到对应位置。",
    "adapter": "`adapter` 是本 Case 创建的算法实例，最后通过 `solver.set_adapter(adapter)` 挂载。",
    "bias_module": "`bias_module` 是本 Case 的 `BiasModule()` 实例；注册偏好后，在求解器装配时传入它。",
    "context": "`context` 是框架调用算子或回调时传入的参数；写回调时接收它，不必在模块全局手工创建。",
    "request": "`request` 是框架调用 change/selector 等回调时传入的请求；示例函数由所属 Adapter 调用。",
    "rng": "`rng` 是调用方提供的随机数生成器；回调沿用传入实例，保持本次运行的随机种子可追踪。",
    "candidate": "`candidate` 是当前调用传入的单个候选；其数据含义和维度须符合此组件的输入说明。",
    "feedback": "`feedback` 是评估后传入的反馈，包含原始目标与选择视图；不在装配代码中凭空构造评估结果。",
    "data_view": "`data_view` 来自 ML Case 的数据准备工厂，先按该 DataView 的接口提供训练数据及需要的标签。",
    "unit": "`unit` 是所属 Adapter 按需建立的算法结构；不要为了复制这段用法在问题管线中另建一个 Unit。",
    "resource_context": "`resource_context` 由正式 Project 入口传给 Case 的 `build_solver()`；Case 不自行发放资源授权。",
}


def external_names(source: str) -> tuple[str, ...]:
    """Find unresolved Python names, respecting local/function/class scopes."""
    try:
        table = symtable.symtable(source, "<catalog-fragment>", "exec")
    except (SyntaxError, ValueError, TypeError):
        return ()
    defined = {item.get_name() for item in table.get_symbols()
               if item.is_assigned() or item.is_imported() or item.is_namespace()}
    standard = set(vars(builtins)) | {"__name__", "__file__", "__package__", "__annotations__"}
    names = set()

    def visit(scope):
        for item in scope.get_symbols():
            if item.is_referenced() and item.is_global() and item.get_name() not in defined | standard:
                names.add(item.get_name())
        for child in scope.get_children():
            visit(child)

    visit(table)
    return tuple(sorted(names))


def external_preparation(source: str) -> tuple[str, ...]:
    names = external_names(source)
    known = [_EXTERNAL_OBJECTS[name] for name in names if name in _EXTERNAL_OBJECTS]
    unknown = [name for name in names if name not in _EXTERNAL_OBJECTS]
    if unknown:
        known.append("片段还使用了这些外部输入，须在同一工厂或回调中明确提供："
                     + "、".join(f"`{name}`" for name in unknown) + "。")
    return tuple(known)


def source_link_text(text: str, source_path: str = "") -> str:
    """Show repository source references as paths, leaving external URLs/code."""
    link = re.compile(r"(?<!!)\[([^\]\n]+)\]\(([^)\n]+)\)")

    def replace(match):
        target = match[2].strip()
        if not target:
            return match[1]
        target = target[1:target.find(">")] if target.startswith("<") and ">" in target else target.split()[0]
        if target.startswith("//") or re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", target):
            return match[0]
        path, separator, anchor = target.partition("#")
        if path.startswith("/"):
            qualified = posixpath.join(source_path.split("/", 1)[0], path.lstrip("/")) if source_path else path
        else:
            qualified = posixpath.normpath(posixpath.join(posixpath.dirname(source_path), path)) if path else source_path
        reference = (qualified or target) + (separator + anchor if separator else "")
        return match[1] + "（`" + reference.replace("`", "") + "`）"

    result, fence = [], None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if fence:
            result.append(line)
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
        elif marker:
            fence = (marker[1][0], len(marker[1]))
            result.append(line)
        else:
            segments = re.split(r"(`+[^`]*`+)", line)
            result.append("".join(segment if segment.startswith("`") else link.sub(replace, segment) for segment in segments))
    return "".join(result)


def assembly_location(entry: Mapping) -> str:
    role = str(entry.get("role") or (entry.get("contract") or {}).get("catalog", {}).get("role")
               or entry.get("kind") or "")
    if role == "unit_feature":
        return "放在所属 Unit 或算子/回调的特征消费处；通过该 Unit 的 `unit.feature(spec)`（`FeatureUnit.feature`）读取，所依赖字段须由特征显式声明。"
    if role in {"unit", "unit_builder", "unit_binding"}:
        return "放在 Case 的 `adapter/` 结构工厂中，通过 `UnitBinding` 交给所属 Adapter；实际运行时再按需创建。"
    kind = str(entry.get("kind") or "")
    if kind == "adapter" or role in {"adapter", "orchestration"}:
        return "在 Case 的 `adapter/` 工厂构造，在 `build_solver.py` 创建 solver 后挂载，最后返回 solver。"
    if kind == "bias":
        return "放在 Case 的 `bias/` 工厂，注册到 `BiasModule`，再由 `build_solver.py` 装配。"
    if kind in {"plugin", "capability"}:
        return "放在 Case 的 `plugins/` 工厂，由 `build_solver.py` 挂载；具体注册方式以本片段为准。"
    if kind in {"representation", "pipeline", "codec", "data_view", "numericizer"}:
        return "放在 Case 的 `pipeline/` 对应组件工厂；候选处理与 ML 模型编解码都从这里接入。"
    if kind in {"problem", "problem_bridge"}:
        return "放在 Case 的 `problem/` 工厂，返回问题对象，再交给 `build_solver.py` 装配。"
    if kind == "trainer":
        return "仍使用 Case 的 `build_solver.py` 作为正式装配入口；`build_trainer.py` 保持薄别名。"
    return ""


__all__ = ["external_names", "external_preparation", "assembly_location"]


def markdown_parts(text: str) -> tuple[tuple[str, str, str | None], ...]:
    """Split source prose and fenced code without evaluating either of them."""
    parts: list[tuple[str, str, str | None]] = []
    lines: list[str] = []
    fence: str | None = None
    language: str | None = None
    for line in text.splitlines():
        if fence is None:
            opening = re.match(r"^ {0,3}(`{3,}|~{3,})([^`]*)$", line)
            if opening:
                if lines:
                    parts.append(("text", "\n".join(lines), None))
                    lines = []
                fence = opening.group(1)
                info = opening.group(2).strip().split()
                language = info[0].lower() if info else None
                language = {"py": "python", "sh": "bash", "shell": "bash",
                            "console": "bash"}.get(language, language)
                continue
        elif re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line):
            parts.append(("code", "\n".join(lines), language))
            lines, fence, language = [], None, None
            continue
        lines.append(line)
    if lines:
        parts.append(("code" if fence else "text", "\n".join(lines), language))
    return tuple(parts)


def display_items(values: Sequence[str]) -> tuple[str, ...]:
    """Discard empty list markers in prose; fenced code remains literal."""
    marker = re.compile(r"^\s*(?:\d+[.)]|[-*+])(?:\s+|$)")
    visible = []
    for value in values:
        if not isinstance(value, str):
            continue
        lines, fence = [], None
        for line in value.splitlines():
            opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
            if fence:
                lines.append(line)
                if opening and opening[1][0] == fence[0] and len(opening[1]) >= len(fence) and not opening[2].strip():
                    fence = None
                continue
            if opening:
                fence = opening[1]
                lines.append(line)
                continue
            content = line
            while match := marker.match(content):
                content = content[match.end():]
            if line.strip() and not content.strip():
                continue
            lines.append(line)
        text = "\n".join(lines).strip("\r\n")
        if any(part.strip() for _, part, _ in markdown_parts(text)):
            visible.append(text)
    return tuple(visible)


def snippet_parts(snippet: Mapping[str, Any]) -> tuple[tuple[str, str, str | None], ...]:
    path = str(snippet["path"]).lower()
    if path.endswith((".md", ".rst")):
        return markdown_parts(str(snippet["text"]))
    return (("code", str(snippet["text"]), "python" if path.endswith(".py") else None),)


_VARIATION = re.compile(r"^ {0,3}###\s+((?:变体|变化用法|延拓用法)[^\n]*)$", re.MULTILINE)
_DOCUMENTATION_LABELS = (
    "输入与前提", "输入与位置", "输入", "预期结果", "预期输出", "输出与消费",
    "边界", "依赖与边界", "依赖", "装配位置", "什么时候用", "先准备什么", "放在哪",
    "接入步骤", "运行入口", "怎样判断接对", "配套组件 key", "接口依据与验证状态",
)
_DOCUMENTATION_FIELD = re.compile(
    r"^(" + "|".join(re.escape(label) for label in _DOCUMENTATION_LABELS) + r")[：:]\s*(.*)$",
    re.DOTALL,
)


def _documentation_plain(paragraph: str) -> str:
    # Only the leading field label may be wrapped in bold. Removing every **
    # also corrupts Python powers and keyword unpacking inside inline code.
    return re.sub(r"^\*\*([^*\n]+)\*\*", r"\1", paragraph.strip())


def documentation_baseline_parts(snippet: Mapping[str, Any]) -> tuple[tuple[str, str, str | None], ...]:
    """Keep baseline prose and code together; a variation starts a new use case."""
    result = []
    for kind, text, language in snippet_parts(snippet):
        variation = _VARIATION.search(text) if kind == "text" else None
        if variation:
            text = text[:variation.start()]
        if text.strip():
            result.append((kind, text, language))
        if variation:
            break
    return tuple(result)


def documentation_baseline_code(snippet: Mapping[str, Any]) -> tuple[tuple[str, str | None], ...]:
    """Return every baseline block before a variation, in source order."""
    result = []
    for kind, text, language in documentation_baseline_parts(snippet):
        if kind == "code" and text.strip():
            result.append((text, language))
    return tuple(result)


def documentation_followup_parts(snippet: Mapping[str, Any]) -> tuple[tuple[str, ...], tuple[tuple[str, str, str | None], ...]]:
    """Keep file instructions and explanations between baseline code blocks.

    Preparation and explicit result/entry fields have their own UI positions.
    Only their labelled paragraphs are omitted here; ordinary narrative must
    not disappear just because it was not another indexed field.
    """
    parts = documentation_baseline_parts(snippet)
    first = next((i for i, part in enumerate(parts) if part[0] == "code"), None)
    if first is None:
        return (), ()
    before = "\n\n".join(text for kind, text, _ in parts[:first] if kind == "text")
    leading_steps, in_steps = [], False
    for paragraph in re.split(r"\n\s*\n", before):
        plain = _documentation_plain(paragraph)
        field = _DOCUMENTATION_FIELD.match(plain)
        if field:
            in_steps = field[1] == "接入步骤"
            if in_steps and field[2].strip():
                leading_steps.append(field[2].strip())
        elif in_steps and plain:
            leading_steps.append(paragraph.strip())
    fields = documentation_fields((snippet,))
    repeated = {_documentation_plain(value) for key, values in fields.items()
                if key != "接入步骤" for value in values}
    followup = []
    for kind, text, language in parts[first + 1:]:
        if kind == "code":
            followup.append((kind, text, language))
            continue
        for paragraph in re.split(r"\n\s*\n", text):
            plain = _documentation_plain(paragraph)
            field = _DOCUMENTATION_FIELD.match(plain)
            if field:
                if field[1] == "接入步骤" and field[2].strip():
                    followup.append(("text", field[2].strip(), None))
                continue
            if plain and plain not in repeated:
                followup.append(("text", paragraph.strip(), None))
    return tuple(leading_steps), tuple(followup)


def documentation_variations(snippets: Sequence[Mapping[str, Any]]) -> tuple[dict, ...]:
    """Keep complete variation prose and code together, without executing it."""
    result = []
    for snippet in snippets:
        if not str(snippet.get("path", "")).lower().endswith((".md", ".rst")):
            continue
        active = None
        for kind, text, language in snippet_parts(snippet):
            if kind == "code":
                if active is not None:
                    active["parts"].append((kind, text, language))
                continue
            for line in text.splitlines(keepends=True):
                match = _VARIATION.fullmatch(line.rstrip("\r\n"))
                if match:
                    if active is not None:
                        result.append(active)
                    active = {"title": match[1].strip(), "parts": []}
                elif re.match(r"^ {0,3}#{1,3}\s", line):
                    if active is not None:
                        result.append(active)
                        active = None
                elif active is not None:
                    parts = active["parts"]
                    if parts and parts[-1][0] == "text":
                        parts[-1] = ("text", parts[-1][1] + line, None)
                    else:
                        parts.append(("text", line, None))
        if active is not None:
            result.append(active)
    return tuple(item for item in result if any(part.strip() for _, part, _ in item["parts"]))


def select_documentation_guide(examples: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """Use the same teaching source on the page and in read-only acceptance."""
    candidates = [example for example in examples
                  if example.get("binding") == "focused" and example.get("kind") == "documentation"
                  and {"放在哪", "先准备什么"} <= documentation_fields(example.get("snippets", ())).keys()]
    rank = {"executed": 0, "source_checked": 1, "unverified": 2}
    return max(candidates, key=lambda item: (item.get("usage_status") == "migration_reference",
                                           len(documentation_variations(item.get("snippets", ()))),
                                           -rank.get(item.get("verification", {}).get("status"), 3)), default=None)


def documentation_fields(snippets: Sequence[Mapping[str, Any]]) -> dict[str, tuple[str, ...]]:
    """Read explicit usage labels, keeping boundaries outside collapsed details."""
    fields: dict[str, list[str]] = {}
    for snippet in snippets:
        if not str(snippet["path"]).lower().endswith((".md", ".rst")):
            continue
        active, continuation = None, False
        for kind, text, _ in snippet_parts(snippet):
            if kind != "text":
                continue
            variation = _VARIATION.search(text)
            stop = variation is not None
            if variation:
                text = text[:variation.start()]
            for paragraph in re.split(r"\n\s*\n", text):
                plain = _documentation_plain(paragraph)
                match = _DOCUMENTATION_FIELD.match(plain)
                if match:
                    active = match[1]
                    continuation = not match[2].strip() and active in {
                        "接入步骤", "先准备什么", "怎样判断接对", "运行入口", "配套组件 key"}
                    if match[2].strip():
                        fields.setdefault(active, []).append(match[2].strip())
                elif continuation and active and plain and not plain.startswith("#"):
                    fields.setdefault(active, []).append(paragraph.strip())
            if stop:
                break
    return {name: tuple(dict.fromkeys(values)) for name, values in fields.items()}
