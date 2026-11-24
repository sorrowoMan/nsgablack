"""Detailed database teaching remains version-bound and display-only."""
import hashlib

from nsgablack.catalog import curation_ui, examples_ui
from nsgablack.catalog.usage_learning import documentation_fields, documentation_variations, documentation_baseline_code


class View:
    def __init__(self):
        self.text, self.codes, self.panels = [], [], []
        self.depth = 0
    def markdown(self, value, **kwargs):
        assert kwargs.get("unsafe_allow_html") is False
        self.text.append(value)
    def caption(self, value):
        self.text.append(value)
    def code(self, value, **kwargs):
        self.codes.append((value, kwargs.get("language"), self.depth))
    def expander(self, label, **kwargs):
        self.panels.append(label)
        return self
    def __enter__(self):
        self.depth += 1
        return self
    def __exit__(self, *_args):
        self.depth -= 1
        return False


def snapshot():
    source = "def change(candidate):\n    return candidate.copy()\n"
    guide = {
        "scenario": "为数值候选保留一个独立草稿，再交给原算法处理。",
        "preparation": ["candidate由当前变化回调提供，输入是一维数值数组。"],
        "placement": "放在当前Case的adapter变化函数中，由所属Adapter调用。",
        "code": source, "language": "python",
        "execution_flow": ["算法传入当前候选，函数返回独立副本，仍由原送评流程处理。"],
        "result_checks": ["返回数值形状应与输入相同，修改返回值不会改写输入。"],
        "extensions": [{"title": "缩小一次变化的幅度", "purpose": "希望当前变化靠近已有候选时使用。",
                        "placement": "替换同一个变化函数，调用方和问题评估保持原入口。",
                        "code": "def change(candidate):\n    return candidate.copy() * 0.5\n",
                        "language": "python", "effect": "返回数值缩小为一半，之后仍需问题修复与正式求值。",
                        "limits": ["只用于允许该数值变化的问题；不能据此改变候选身份。"], "evidence_ids": ["e1"]}],
        "evidence_ids": ["e1"],
    }
    record = {"entry_key": "tool.demo", "source_digest": "a" * 64,
              "prompt_version": "catalog-tutorial-zh-v4", "model": "fixture-model",
              "note": {"summary": "候选草稿示例。", "inputs_outputs": "输入数值候选，返回数值草稿。",
                       "use_when": [], "assembly_steps": [], "pitfalls": [], "related_keys": [],
                       "missing_information": [], "evidence_ids": ["e1"], "tutorial": guide},
              "evidence": [{"id": "e1", "path": "demo/change.py", "start_line": 1, "end_line": 2,
                            "text": source, "sha256": hashlib.sha256(source.encode()).hexdigest()}]}
    return {"enabled": True, "available": True,
            "index": {"entries": {"tool.demo": "a" * 64}, "profiles": {"default": ["tool.demo"], "empty": []},
                      "prompt_version": "catalog-tutorial-zh-v4"}, "records": {"tool.demo": record}}


def test_database_tutorial_shows_copyable_baseline_and_actual_variation(monkeypatch):
    state = snapshot()
    monkeypatch.setattr(curation_ui, "knowledge_snapshot", lambda: state)
    view = View()
    assert curation_ui.render_tutorial(view, entry_key="tool.demo")
    text = "\n".join(view.text)
    assert "代码放在哪" in text and "接上后怎样运行" in text and "怎样检查结果" in text
    assert "还能怎样改" in text and "缩小一次变化" in text and "尚未执行" in text
    guide = state["records"]["tool.demo"]["note"]["tutorial"]
    assert (guide["code"].strip("\r\n"), "python", 0) in view.codes
    assert (guide["extensions"][0]["code"].strip("\r\n"), "python", 1) in view.codes


def test_stale_invalid_or_out_of_profile_guide_never_replaces_usage(monkeypatch):
    for mode in ("stale", "invalid", "profile"):
        state = snapshot()
        if mode == "stale":
            state["records"]["tool.demo"]["source_digest"] = "b" * 64
        elif mode == "invalid":
            state["records"]["tool.demo"]["note"]["tutorial"]["extensions"][0]["evidence_ids"] = ["invented"]
        monkeypatch.setattr(curation_ui, "knowledge_snapshot", lambda: state)
        view = View()
        assert not curation_ui.render_tutorial(view, entry_key="tool.demo", profile="empty" if mode == "profile" else "default")
        assert not view.codes


def test_reviewed_generation_requires_a_positive_independent_review(monkeypatch):
    state=snapshot()
    from nsgablack.catalog.curation_provider import PROMPT_VERSION
    from nsgablack.catalog.tutorial_review import REVIEW_VERSION
    version=PROMPT_VERSION
    state["index"]["prompt_version"]=version
    record=state["records"]["tool.demo"]
    record["prompt_version"]=version
    monkeypatch.setattr(curation_ui,"knowledge_snapshot",lambda:state)
    assert curation_ui.entry_knowledge("tool.demo")["status"]=="invalid"
    record["note"]["tutorial_review"]={
        "version":REVIEW_VERSION,"decision":"publish","issues":[],
        "checks":["输入来自显式参数。","调用方保留原送评。","变化输出仍有同样形状。"],"evidence_ids":["e1"]}
    assert curation_ui.entry_knowledge("tool.demo")["status"]=="current"
    record["note"]["tutorial_review"]["decision"]="revise"
    assert curation_ui.entry_knowledge("tool.demo")["status"]=="invalid"


def test_manual_baseline_keeps_its_place_while_database_adds_variations(monkeypatch):
    state = snapshot()
    monkeypatch.setattr(curation_ui, "knowledge_snapshot", lambda: state)
    view = View()
    assert curation_ui.render_tutorial(view, entry_key="tool.demo", include_baseline=False)
    guide = state["records"]["tool.demo"]["note"]["tutorial"]
    assert not any(code.strip("\r\n") == guide["code"].strip("\r\n") and depth == 0
                   for code, _language, depth in view.codes)
    assert (guide["extensions"][0]["code"].strip("\r\n"), "python", 1) in view.codes


def test_variation_sections_keep_code_and_do_not_pollute_baseline_fields():
    snippet = {"path": "guide.md", "text": '''## tool.demo

先准备什么：基础输入。

放在哪：基础工厂。

```python
# ### 变体一：代码里的标题不应被解释成章节
def base(candidate):
    return candidate.copy()
```

### 变体一：从另一个参考区域取输入
改在哪里：替换调用方传入的参考区域。

```python
def changed(candidate):
    return candidate.copy() * 0.5
```

先准备什么：这属于变体条件，不能覆盖基础输入。
'''}
    assert documentation_fields((snippet,))["先准备什么"] == ("基础输入。",)
    variations = documentation_variations((snippet,))
    assert len(variations) == 1
    assert "参考区域" in variations[0]["title"]
    assert any(kind == "code" and "def changed" in text for kind, text, _ in variations[0]["parts"])
    baseline = documentation_baseline_code(snippet)
    assert len(baseline) == 1 and "def base" in baseline[0][0]


def test_every_baseline_step_has_visible_code_before_optional_variations():
    record = {"id": "multi-part", "title": "完整装配", "kind": "documentation", "binding": "focused",
              "verification": {"status": "source_checked"}, "inputs": ["数值Problem。"],
              "steps": ["先定义，再挂载。"], "dependencies": [], "expected_outputs": ["组件已连接。"],
              "snippets": [{"path": "guide.md", "text": '''## tool.demo

先准备什么：正式Case提供solver。

放在哪：adapter工厂。

```python
def make_value():
    return 1
```

接入步骤：定义函数后，在原工厂挂载。

```python
def attach(solver):
    solver.value = make_value()
```

### 变体一：使用不同数值
```python
def make_value():
    return 2
```
''', "start_line": 1, "end_line": 24, "complete": True}]}
    view = View()
    examples_ui._render_one(view, record)
    assert any("return 1" in code and depth == 0 for code, _, depth in view.codes)
    assert any("solver.value" in code and depth == 0 for code, _, depth in view.codes)
    assert not any("return 2" in code and depth == 0 for code, _, depth in view.codes)
