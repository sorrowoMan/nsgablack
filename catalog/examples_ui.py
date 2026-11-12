"""Read-only component examples from the deployment's fixed source index.

Displaying a recipe never imports its component, builds a Unit, runs a Case or
calls a model. Source and receipt validation belongs to ``catalog.examples``.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import ast
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import os
from pathlib import Path
import re
from typing import Any

from .usage_learning import (markdown_parts as _markdown_parts, snippet_parts as _snippet_parts,
                             documentation_fields as _documentation_fields, display_items as _display_items,
                             documentation_variations as _documentation_variations,
                             documentation_baseline_parts as _documentation_baseline_parts,
                             _documentation_plain, _DOCUMENTATION_FIELD,
                             select_documentation_guide as _select_documentation_guide,
                             source_link_text as _source_link_text)


INDEX_ENV = "NSGABLACK_CATALOG_EXAMPLES_INDEX"
_MAX_INDEX_BYTES = 16 * 1024 * 1024
_DISPLAY_TIMEZONE = timezone(timedelta(hours=8))


def _read_index(path: str) -> dict[str, Any]:
    from .examples import load_example_index

    return load_example_index(Path(path))


@lru_cache(maxsize=4)
def _load_snapshot(index_path: str, revision: tuple[int, int]) -> dict[str, Any]:
    del revision
    try:
        index = _read_index(index_path)
        return {"configured": True, "available": True, "index": index,
                "material_categories": _material_categories(index)}
    except Exception as exc:
        # File errors can contain private deployment paths. Never expose them.
        return {"configured": True, "available": False, "error_type": type(exc).__name__}


def _material_categories(index: Mapping[str, Any]) -> dict[str, str]:
    # The same offline inventory owns teaching completeness on the page and in
    # maintenance reports. It only parses supplied text, never component code.
    from .material_plan import build_material_plan

    return {item["key"]: item["category"] for item in build_material_plan(index)["entries"]}


def examples_snapshot() -> dict[str, Any]:
    """Read the operator-selected immutable index, never a browser parameter."""
    path = os.environ.get(INDEX_ENV, "").strip()
    if not path:
        return {"configured": False, "available": False}
    try:
        source = Path(path)
        stat = source.stat()
        if not source.is_file() or stat.st_size > _MAX_INDEX_BYTES:
            raise ValueError("Example index is absent or oversized")
    except (OSError, ValueError) as exc:
        return {"configured": True, "available": False, "error_type": type(exc).__name__}
    return _load_snapshot(path, (stat.st_mtime_ns, stat.st_size))


def _strings(value: object, *, preserve_whitespace: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    if preserve_whitespace:
        return tuple(item for item in value if isinstance(item, str))
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _examples(entry: Mapping[str, Any], snapshot: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    if not snapshot.get("available"):
        return ()
    index = snapshot["index"]
    identifiers = index["entries"].get(str(entry.get("key", "")), ())
    issues: dict[str, list[str]] = {}
    for issue in index.get("issues", ()):
        issues.setdefault(issue["example_id"], []).append(issue["error"])
    examples = tuple({**index["examples"][identifier], "_index_issues": issues.get(identifier, ())}
                     for identifier in identifiers)
    # Prefer the most useful example while preserving declared order on ties.
    rank = {"executed": 0, "source_checked": 1, "unverified": 2}
    return tuple(sorted(examples, key=lambda item: (
        rank.get(item.get("verification", {}).get("status"), 3),
        0 if item.get("binding") == "focused" else 1,
    )))


def _broken(example: Mapping[str, Any]) -> bool:
    verification = example.get("verification", {})
    return (verification.get("status") == "unverified"
            and bool(example.get("_index_issues")) and not example.get("snippets"))


def _covered_documentation_sources(entry: Mapping[str, Any], examples: Sequence[Mapping[str, Any]]) -> set[tuple[str, str]]:
    """Only a complete, component-bound section can replace its book's preface."""
    key = str(entry.get("key", ""))
    section_keys = {key, str((entry.get("metadata") or {}).get("catalog_original_key", ""))} - {""}
    covered = set()
    for example in examples:
        if (example.get("binding") != "focused" or example.get("kind") != "documentation"
                or key not in example.get("component_keys", ())
                or example.get("verification", {}).get("status") not in {"source_checked", "executed"}
                or example.get("issues") or example.get("_index_issues")):
            continue
        for snippet in example.get("snippets", ()):
            path, digest = str(snippet.get("path", "")), str(snippet.get("file_sha256", ""))
            text = str(snippet.get("text", ""))
            heading = re.match(r"\A\s{0,3}#{1,6}\s+(`?[^\s`]+`?)(?:\s|$)", text)
            if (not path.endswith(".md") or not digest or snippet.get("complete") is not True
                    or heading is None or heading[1].strip("`") not in section_keys):
                continue
            # A heading alone is not a usable component section.
            body = text.split("\n", 1)[1] if "\n" in text else ""
            if _display_items((body,)):
                covered.add((path, digest))
    return covered


def _redundant_declared_book(example: Mapping[str, Any], covered: set[tuple[str, str]]) -> bool:
    if (example.get("binding") != "declared" or example.get("kind") != "documentation"
            or example.get("run_command") or example.get("verification", {}).get("status") == "executed"):
        return False
    snippets = tuple(example.get("snippets", ()))
    return bool(snippets) and all(
        str(snippet.get("path", "")).endswith(".md")
        and snippet.get("start_line") == 1 and 1 <= snippet.get("end_line", 0) <= 40
        and (str(snippet.get("path", "")), str(snippet.get("file_sha256", ""))) in covered
        for snippet in snippets
    )


def example_status(entry: Mapping[str, Any], snapshot: Mapping[str, Any] | None = None) -> str:
    """A short search-result label; a declaration alone is never execution."""
    state = examples_snapshot() if snapshot is None else snapshot
    examples = _examples(entry, state)
    if any(item.get("verification", {}).get("status") == "executed" for item in examples):
        return "已运行示例"
    categories = state.get("material_categories")
    if examples and not isinstance(categories, Mapping):
        key = str(entry.get("key", ""))
        categories = _material_categories({"entries": {key: [item["id"] for item in examples]},
                                           "examples": {item["id"]: item for item in examples}})
    category = categories.get(str(entry.get("key", ""))) if isinstance(categories, Mapping) else None
    if any(item.get("binding") == "focused" and item.get("kind") == "documentation"
           and item.get("verification", {}).get("status") == "source_checked" for item in examples):
        return {"detailed_with_variants": "详细用法", "complete_main": "详细用法",
                "migration_reference": "迁移说明",
                "documentation_navigation": "文档入口", "missing_source": "待补用法"}.get(category, "用法片段")
    if any(item.get("verification", {}).get("status") == "source_checked" for item in examples):
        return "示例待验证"
    if examples and all(_broken(item) for item in examples):
        return "入口失效"
    if _strings(entry.get("minimal_wiring")):
        return "装配片段"
    if examples or str(entry.get("example_entry", "") or "").strip():
        return "示例待验证"
    return "待补示例"


def render_material_status(st: Any, *, snapshot: Mapping[str, Any] | None = None) -> None:
    """Show source-guide coverage without relabeling it as AI or execution."""
    state = examples_snapshot() if snapshot is None else snapshot
    if not state.get("available"):
        return
    categories = state.get("material_categories")
    if not isinstance(categories, Mapping) or not categories:
        return
    from collections import Counter

    counts = Counter(categories.values())
    complete = counts["detailed_with_variants"] + counts["complete_main"]
    navigation = counts["documentation_navigation"] + counts["project_case_navigation"]
    # An unrecognized material category must not imply complete coverage.
    pending = len(categories) - complete - counts["migration_reference"] - navigation
    st.caption(f"用法资料 · 全部索引 {len(categories)} 项：详细用法 {complete} · "
               f"迁移说明 {counts['migration_reference']} · 导航 {navigation} · 待补资料 {pending}")
    st.caption("详细用法提供装配与检查步骤；迁移说明列出当前限制及替代接线；导航只提供文档或项目入口。"
               "源码说明、AI 审核和实际运行分别统计，资料覆盖不代表全部组件可直接使用或已通过运行验收。")


def _list(st: Any, title: str, values: Sequence[str], *, numbered: bool = False) -> None:
    visible = _display_items(values)
    if not visible:
        return
    st.markdown(f"**{title}**", unsafe_allow_html=False)
    for index, value in enumerate(visible, start=1):
        existing_list = re.match(r"(?:\d+[.)]|[-*+])(?:\s+|$)", value.lstrip())
        fenced_code = any(kind == "code" for kind, _, _ in _markdown_parts(value))
        content = value if existing_list or fenced_code else (f"{index}. {value}" if numbered else f"- {value}")
        st.markdown(content, unsafe_allow_html=False)






class _SourceMarkdown:
    def __init__(self, target: Any, source_path: str):
        self._target, self._source_path = target, source_path

    def __getattr__(self, name):
        return getattr(self._target, name)

    def markdown(self, text, **kwargs):
        return self._target.markdown(_source_link_text(text, self._source_path), **kwargs)


def _snippet(st: Any, snippet: Mapping[str, Any]) -> None:
    """Show the original excerpt in details, with native copyable code blocks."""
    st = _SourceMarkdown(st, str(snippet["path"]))
    st.caption(f"{snippet['path']}:{snippet['start_line']}-{snippet['end_line']}")
    for kind, text, language in _snippet_parts(snippet):
        if kind == "code":
            st.code(text, language=language, wrap_lines=True)
        elif text.strip():
            # Source headings describe the whole usage book; they are not page
            # hierarchy inside the selected component's details.
            prose = re.sub(r"(?m)^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", r"**\1**", text)
            st.markdown(prose, unsafe_allow_html=False)
    if snippet.get("complete") is False:
        st.caption("以上为关键代码节选；完整入口见示例来源。")




def _verification_note(st: Any, example: Mapping[str, Any], *, detailed: bool = False) -> None:
    status = example.get("verification", {}).get("status", "unverified")
    prefix = "" if detailed else "**用法** · "
    if status == "executed":
        st.caption(prefix + "已有运行收据，结果对应本页源码、命令和运行环境。")
    elif status == "source_checked":
        if detailed:
            st.caption("示例源码已核对，尚无当前版本的成功运行记录；预期输出不代表实际运行结果。")
        else:
            st.caption(prefix + "源码已核对，未记录运行结果。")
    elif _broken(example):
        st.info("声明的示例入口无法与当前发布源码对应，暂不能作为可运行用例。")
    else:
        st.caption(prefix + "已声明用法，尚未完成源码或运行验证。")
    if example.get("binding") == "declared":
        st.caption("组件声明的关联入口；尚未确认此组件在入口中实际装配。")


def _recorded_time(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return value
        return parsed.astimezone(_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S UTC+08:00")
    except ValueError:
        return value


def _documentation_body_parts(snippet: Mapping[str, Any]):
    """Keep every baseline paragraph, excluding fields shown in the shared UI."""
    fields = _documentation_fields((snippet,))
    repeated = {_documentation_plain(value) for label, values in fields.items()
                if label != "接入步骤" for value in values}
    for kind, text, language in _documentation_baseline_parts(snippet):
        if kind == "code":
            yield kind, text, language
            continue
        for paragraph in re.split(r"\n\s*\n", text):
            # Attachment section IDs bind a source excerpt; the human variant
            # titles below already explain the use case. Keep IDs in source
            # evidence rather than adding a dangling heading to the main page.
            if re.fullmatch(r"\s*#{1,6}\s+extension\.[A-Za-z0-9_.-]+\s*", paragraph):
                continue
            plain = _documentation_plain(paragraph)
            field = _DOCUMENTATION_FIELD.match(plain)
            if field:
                if field[1] == "接入步骤":
                    yield "text", "**接下来怎么接**" + (" · " + field[2].strip() if field[2].strip() else ""), None
                continue
            if plain and plain not in repeated:
                yield "text", paragraph.strip(), None


def _render_one(st: Any, example: Mapping[str, Any], *, entry: Mapping[str, Any] | None = None) -> None:
    snippets = tuple(example.get("snippets", ()))
    target = st
    st = _SourceMarkdown(st, str(snippets[0]["path"]) if snippets else "")
    # A record can continue in another section or book. Resolve each field at
    # its own source before aggregating shared preparation/result fields.
    fields: dict[str, tuple[str, ...]] = {}
    for snippet in snippets:
        for label, values in _documentation_fields((snippet,)).items():
            fields[label] = tuple(dict.fromkeys((*fields.get(label, ()), *(
                _source_link_text(value, str(snippet["path"])) for value in values))))
    verification = example.get("verification", {})
    status = verification.get("status", "unverified")
    _verification_note(st, example)
    if example.get("usage_status") == "migration_reference":
        st.markdown("**迁移说明** · 本页说明原组件当前的限制与替代接线；替代示例不表示原组件已经实现或可直接装配。",
                    unsafe_allow_html=False)

    # Keep preparation and file instructions with their calls. Native st.code
    # supplies a copy action and preserves indentation without executing it.
    code_blocks = tuple((snippet, part) for snippet in snippets for part in _documentation_baseline_parts(snippet)
                        if part[0] == "code" and part[1].strip())
    placement = _display_items(fields.get("放在哪") or fields.get("装配位置", ()))
    if not placement and entry:
        from .usage_learning import assembly_location
        location = assembly_location(entry)
        placement = (location,) if location else ()
    use_when = _display_items(fields.get("什么时候用", ()))
    if use_when:
        st.markdown("**什么时候用** · " + "\n\n".join(use_when), unsafe_allow_html=False)
    if placement:
        st.markdown("**放在哪** · " + "\n\n".join(placement), unsafe_allow_html=False)

    inputs = _display_items(fields.get("先准备什么") or fields.get("输入与前提") or fields.get("输入与位置")
                            or fields.get("输入") or _strings(example.get("inputs")))
    outputs = _display_items(fields.get("怎样判断接对") or fields.get("预期输出") or fields.get("预期结果")
                             or fields.get("输出与消费") or _strings(example.get("expected_outputs")))
    inputs = tuple(value for value in inputs if not value.startswith("同一正式Case已构造的solver与问题候选管线"))
    if outputs and outputs[0].startswith("得到已装配组件或回调返回值"):
        outputs = ()
    if inputs:
        _list(st, "输入与准备", inputs)
    preparation = ()
    if code_blocks and not fields.get("先准备什么"):
        from .usage_learning import external_preparation
        preparation = external_preparation(code_blocks[0][1][1])
        if preparation:
            _list(st, "片段里的对象从哪里来", preparation)
    if not inputs and not preparation:
        st.caption("输入说明待补充：本节尚未交代完整调用前提，请先核对接口和源码。")
    steps = _display_items(fields.get("接入步骤", ()))
    structured = bool(fields.get("先准备什么") and fields.get("放在哪") and any(
        str(snippet.get("path", "")).lower().endswith((".md", ".rst")) for snippet in snippets))
    if structured:
        for snippet in snippets:
            source_view = _SourceMarkdown(target, str(snippet["path"]))
            for kind, text, language in _documentation_body_parts(snippet):
                if kind == "code":
                    source_view.code(text, language=language, wrap_lines=True)
                else:
                    prose = re.sub(r"(?m)^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", r"**\1**", text)
                    source_view.markdown(prose, unsafe_allow_html=False)
            if snippet.get("complete") is False:
                source_view.caption("关键代码节选；完整入口与上下文见下方源码。")
    else:
        for source, (_, code, language) in code_blocks:
            st.code(code, language=language, wrap_lines=True)
            if source.get("complete") is False:
                st.caption("关键代码节选；完整入口与上下文见下方源码。")
        if not code_blocks and snippets:
            st.info("此用法目前只有说明；完整内容见下方源码与验证记录。")
        if steps:
            _list(st, "接下来怎么接", steps)
    if outputs:
        _list(st, "预期得到什么", outputs)
    else:
        st.caption("结果检查说明待补充：此片段可用于核对接入位置，尚未提供可照做的结果检查步骤。")
    if fields.get("运行入口"):
        _list(st, "运行入口", fields["运行入口"])
    variations = tuple((snippet, variation) for snippet in snippets
                       for variation in _documentation_variations((snippet,)))
    if variations:
        st.markdown("**还能怎样改**", unsafe_allow_html=False)
        for source, variation in variations:
            source_view = _SourceMarkdown(target, str(source["path"]))
            with source_view.expander(variation["title"], expanded=False):
                for kind, text, language in variation["parts"]:
                    if kind == "code":
                        source_view.code(text, language=language, wrap_lines=True)
                    elif text.strip():
                        source_view.markdown(text, unsafe_allow_html=False)

    # These are explicit source fields, not a guess about whether arbitrary
    # prose is a warning. A missing automatic consumer must remain visible.
    boundaries = _display_items(tuple(dict.fromkeys((*fields.get("边界", ()), *fields.get("依赖与边界", ())))))
    if boundaries:
        st.markdown("**使用边界** · " + "\n\n".join(boundaries), unsafe_allow_html=False)

    command = str(example.get("run_command", "") or "").strip()
    if command:
        st.markdown("**如何运行**", unsafe_allow_html=False)
        directory = str(example.get("working_directory", "") or "").strip()
        if directory:
            st.caption(f"在 {directory} 仓库根目录执行；此网页只展示命令。")
        st.code(command, language="bash", wrap_lines=True)

    detail_steps = steps or _display_items(_strings(example.get("steps")))
    dependencies = _display_items(_strings(example.get("dependencies")))
    parameters = tuple(parameter for parameter in example.get("parameters", ())
                       if _display_items((parameter.get("name", ""),)))
    if inputs or detail_steps or dependencies or parameters or outputs:
        with st.expander("装配说明与参数", expanded=False):
            st.markdown(f"**{example.get('title', example['id'])}**", unsafe_allow_html=False)
            summary = str(example.get("summary", "") or "")
            if summary:
                st.markdown(summary, unsafe_allow_html=False)
            _list(st, "输入与准备", inputs)
            _list(st, "使用步骤", detail_steps, numbered=True)
            _list(st, "运行依赖", dependencies)
            if parameters:
                st.markdown("**可以修改什么**", unsafe_allow_html=False)
                for parameter in parameters:
                    value = parameter.get("value", "")
                    st.markdown(f"- {parameter['name']}：{parameter.get('meaning', '')}（示例值：{value}）",
                                unsafe_allow_html=False)
            _list(st, "预期得到什么", outputs)

    if not snippets and status != "executed" and not _strings(example.get("_index_issues")):
        return

    with st.expander("源码与验证记录", expanded=False):
        kind = {"project": "完整 Project", "case": "独立 Case", "documentation": "说明文档", "reference": "入口引用"}
        st.caption("示例形式：" + kind.get(str(example.get("kind", "")), "入口引用"))
        _verification_note(st, example, detailed=True)
        if status == "executed":
            st.markdown("**实际运行结果**", unsafe_allow_html=False)
            observed = _strings(verification.get("observed_outputs"))
            if observed:
                st.code("\n".join(observed), language="text", wrap_lines=True)
            stamp = _recorded_time(verification.get("executed_at"))
            if stamp:
                st.caption("运行时间：" + stamp)
            st.caption(f"退出码：{verification.get('exit_code', '')} · 源码摘要：{example['source_digest'][:12]}")
        elif outputs:
            st.caption("实际运行结果待补充。")
        for snippet in snippets:
            _snippet(st, snippet)
        if _strings(example.get("_index_issues")):
            st.markdown("**仍需补充或核对**", unsafe_allow_html=False)
            st.caption("该入口未通过发布时的源码检查，需维护者修复后重新建立索引。")


def _render_declared_usage(st: Any, entry: Mapping[str, Any], *, include_reference=True) -> None:
    wiring = _strings(entry.get("minimal_wiring"), preserve_whitespace=True)
    command = str(entry.get("example_entry", "") or "").strip()
    if wiring:
        code = "\n".join(wiring)
        try:
            ast.parse(code)
            language = "python"
        except SyntaxError:
            language = "text"
        from .usage_learning import assembly_location, external_preparation
        location = assembly_location(entry)
        if location:
            st.markdown("**放在哪** · " + location, unsafe_allow_html=False)
        if language == "python":
            _list(st, "片段里的对象从哪里来", external_preparation(code))
        st.markdown("**最小装配片段**" if language == "python" else "**组件接入关系**", unsafe_allow_html=False)
        st.code(code, language=language, wrap_lines=True)
        st.caption("片段展示当前组件的接入位置；外部对象与依赖需由标准 Case 提供，不能视为独立可运行程序。")
    if command and include_reference:
        st.markdown("**已声明的示例入口**", unsafe_allow_html=False)
        st.code(command, language=None, wrap_lines=True)
        st.caption("入口尚未在当前示例索引中核对，没有实际运行记录。")
    if not wiring and not command:
        st.info("此组件尚缺使用示例；可先切换到“接口”查看组件声明。")


def render_examples(st: Any, entry: Mapping[str, Any], *, profile: str = "default") -> None:
    """Show the selected component's focused recipe and verified result."""
    state = examples_snapshot()
    examples = _examples(entry, state)
    learning = _select_documentation_guide(examples)
    with st.expander("第一次装配？先创建一个标准 Project", expanded=False):
        ml = (entry.get("metadata") or {}).get("catalog_framework") == "mlblack"
        framework, case_type = ("mlblack", "trainer") if ml else ("nsgablack", "solver")
        st.markdown("在已安装框架的终端执行以下命令。生成的 Case 会提供 Problem、候选管线和求解器工厂；"
                    "再按本组件的“放在哪”替换对应部分。", unsafe_allow_html=False)
        st.code("python -m nsgablack project new first_project\ncd first_project\n"
                f"python -m nsgablack project add-case search --type {case_type} --framework {framework}\n"
                "python run_project.py --check --build-check", language="bash", wrap_lines=True)
        st.markdown("`cases/search/problem/` 定义问题；`pipeline/` 准备候选或数据；"
                    "`build_solver.py` 连接组件。目录只显示这些命令，具体组件仍须满足下方输入条件。",
                    unsafe_allow_html=False)
    if state.get("configured") and not state.get("available"):
        st.caption(f"示例索引暂不可用（{state.get('error_type', 'ExampleIndexError')}），以下仅展示组件声明。")
    from .curation_ui import render_tutorial
    detailed = render_tutorial(st, entry_key=str(entry.get("key", "")), profile=profile,
                               include_baseline=learning is None) if learning is None else False
    if not examples:
        if detailed:
            with st.expander("原始装配声明", expanded=False):
                _render_declared_usage(st, entry)
        else:
            _render_declared_usage(st, entry)
        return
    has_wiring = bool(_strings(entry.get("minimal_wiring")))
    if not any(example.get("binding") == "focused" for example in examples) and has_wiring:
        # A generic navigation/reference must not hide this component's actual
        # wiring. Focused recipes already carry their own concrete usage.
        _render_declared_usage(st, entry, include_reference=False)
        additional = examples
    else:
        primary = learning or examples[0]
        if detailed:
            with st.expander("原始装配片段与来源", expanded=False):
                _render_one(st, primary, entry=entry)
        else:
            _render_one(st, primary, entry=entry)
        if learning is not None and learning.get("usage_status") != "migration_reference":
            render_tutorial(st, entry_key=str(entry.get("key", "")), profile=profile, include_baseline=False)
        additional = tuple(example for example in examples if example is not primary)
    covered = _covered_documentation_sources(entry, examples)
    for example in additional:
        if _redundant_declared_book(example, covered):
            continue
        if (not example.get("snippets") and not str(example.get("run_command", "") or "").strip()
                and not any(_display_items(_strings(example.get(field)))
                            for field in ("inputs", "steps", "dependencies", "expected_outputs", "_index_issues"))
                and not any(_display_items((parameter.get("name", ""),)) for parameter in example.get("parameters", ()))
                and example.get("verification", {}).get("status") != "executed"):
            continue
        label = ("历史来源（不表示当前可用）" if learning is not None and learning.get("usage_status") == "migration_reference"
                 else "完整 Project 与运行记录" if example.get("verification", {}).get("status") == "executed" else "更多用法")
        with st.expander(f"{label} · {example.get('title', example['id'])}", expanded=False):
            _render_one(st, example, entry=entry)


__all__ = ["example_status", "examples_snapshot", "render_examples"]
