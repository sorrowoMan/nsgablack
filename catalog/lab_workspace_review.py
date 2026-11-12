"""Pure draft review and one conservative, explicitly applied syntax repair.

Nothing in this module imports or evaluates the reviewed source. Syntax and
call locations are observations of text, never proof of an assembled runtime.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
import difflib
import hashlib
import io
import re
import tokenize
from typing import Any

from .lab_workspace_project import source_outline


_SCOPE_NOTE = (
    "仅检查当前草稿的 Python 语法和静态装配调用位置；不导入组件、不构建 Unit、"
    "不运行源码，不证明参数兼容、实际执行路径或算法正确性。"
)


def _digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _missing_colon_fix(source: str, line: int) -> dict[str, Any] | None:
    normalized = source.removeprefix("\ufeff")
    # Python accepts LF, CRLF and CR. Tokenizer row/column coordinates must
    # match the parser without changing the suggested source's line endings.
    physical_lines = re.split(r"\r\n|\r|\n", normalized)
    if not 1 <= line <= len(physical_lines):
        return None
    content = physical_lines[line - 1]
    boundary = len(content)
    reader = io.StringIO(normalized.replace("\r\n", "\n").replace("\r", "\n")).readline
    try:
        for token in tokenize.generate_tokens(reader):
            if token.start[0] > line:
                break
            if token.type == tokenize.COMMENT and token.start[0] == line:
                boundary = token.start[1]
                break
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return None
    position = len(content[:boundary].rstrip())
    if not position or content[:position].endswith(":"):
        return None
    # Locate only physical newlines; str.splitlines() also splits characters
    # such as form-feed that Python does not count as a new source line.
    endings = list(re.finditer(r"\r\n|\r|\n", normalized))
    start = endings[line - 2].end() if line > 1 else 0
    offset = start + position + (1 if source.startswith("\ufeff") else 0)
    after = source[:offset] + ":" + source[offset:]
    try:
        ast.parse(after.removeprefix("\ufeff"))
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    return {
        "kind": "missing-colon",
        "title": "在此行代码末尾补上冒号",
        "line": line,
        "before_digest": _digest(source),
        "after_text": after,
        "diff": "".join(difflib.unified_diff(
            source.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile="草稿（修复前）", tofile="草稿（补冒号后）")),
    }


def review_source(path: str, source: str) -> dict[str, Any]:
    """Reuse the source outline; offer a fix only for exact ``expected ':'``.

    A proposal changes one character and is returned only when the complete
    candidate parses. It is not saved, imported, built, evaluated or executed.
    """
    result = source_outline(path, source)
    result.update(before_digest=_digest(source), fixes=[], scope_note=_SCOPE_NOTE)
    diagnostics = result["diagnostics"]
    if (result["kind"] == "python" and result["syntax_ok"] is False
            and len(diagnostics) == 1
            and diagnostics[0].get("code") == "python-syntax-error"
            and diagnostics[0].get("message") == "expected ':'"
            and type(diagnostics[0].get("line")) is int):
        fix = _missing_colon_fix(source, diagnostics[0]["line"])
        if fix is not None:
            result["fixes"].append(fix)
    return result


def apply_source_fix(current_text: str, suggestion: Mapping[str, Any]) -> str:
    """Return the reviewed text only if the current draft and fix still match.

    Re-derive the sole supported edit so a changed proposal cannot turn this
    helper into an arbitrary replacement. The caller owns explicit adoption.
    """
    if not isinstance(current_text, str) or not isinstance(suggestion, Mapping):
        raise ValueError("修复需要当前草稿与有效建议。")
    if suggestion.get("before_digest") != _digest(current_text):
        raise ValueError("草稿已改变，请重新审查后预览修复。")
    for expected in review_source("draft.py", current_text)["fixes"]:
        if dict(suggestion) == expected:
            return expected["after_text"]
    raise ValueError("修复建议与当前草稿的确定性修复不一致，请重新审查。")
