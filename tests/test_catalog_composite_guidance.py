"""A usable Composite guide stays tied to the actual formal Case assembly."""
import ast
from pathlib import Path

from nsgablack.catalog.usage_learning import documentation_fields, markdown_parts


ROOT = Path(__file__).resolve().parents[1]


def composite_section():
    path = ROOT / "docs/catalog_usage/NSGABLACK_COMPONENT_USAGE_CN.md"
    text = path.read_text(encoding="utf-8-sig")
    section = text.split("## adapter.composite · CompositeAdapter\n", 1)[1].split("\n## ", 1)[0]
    return {"path": str(path), "text": section}


def test_composite_teaching_code_is_the_actual_formal_case_not_a_separate_recipe():
    snippet = composite_section()
    code = [text for kind, text, language in markdown_parts(snippet["text"])
            if kind == "code" and language == "python"]
    assert len(code) == 1
    formal_case = ROOT / "examples/cases/catalog_recipes/cases/composite/build_solver.py"
    source = ast.parse(formal_case.read_text(encoding="utf-8-sig"))
    if isinstance(source.body[0], ast.Expr) and isinstance(source.body[0].value, ast.Constant):
        source.body.pop(0)  # A module description is not part of the assembly.
    assert ast.dump(ast.parse(code[0])) == ast.dump(source)


def test_composite_guide_answers_execution_handoff_and_result_questions():
    snippet = composite_section()
    fields = documentation_fields((snippet,))
    assert all(fields.get(label) for label in (
        "什么时候用", "先准备什么", "放在哪", "接入步骤", "怎样判断接对", "运行入口", "边界"))
    assert "4 + 4 = 8" in "\n".join(fields["接入步骤"])
    assert "child:0:wide/population" in "\n".join(fields["怎样判断接对"])
    assert "child:1:narrow/population" in "\n".join(fields["怎样判断接对"])
    assert "get_population_partitions()" in "\n".join(fields["怎样判断接对"])
    assert "不会因此开启线程或进程并行" in "\n".join(fields["边界"])
    assert "PoolTask" in "\n".join(fields["边界"])
    assert "结果检查说明待补充" not in snippet["text"]
