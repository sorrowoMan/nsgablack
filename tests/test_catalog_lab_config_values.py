from pathlib import Path
import pytest

from nsgablack.catalog.lab_config_values import calculate_config_values


def test_real_budget_uses_ga_steps_and_mode_not_population_capacity():
    source = (Path(__file__).parents[1] / "examples/cases/assembled_ga_vns/cases/hybrid_search/config.py").read_text(encoding="utf-8-sig")
    out = calculate_config_values(source, "DemoConfig", values={"ga_steps": 7, "population_size": 50,
        "elite_count": 3, "local_steps": 2, "refinement_source": "elite", "schedule": "plan", "rounds": 4},
        properties=["refinement_count", "max_steps"])
    assert out["properties"] == {"refinement_count": 3, "max_steps": 57}
    assert out["status"] == "computed"
    population = calculate_config_values(source, "DemoConfig", values={"ga_steps": 7, "population_size": 50,
        "local_steps": 2, "refinement_source": "population", "schedule": "phases"}, properties=["max_steps"])
    assert population["properties"]["max_steps"] == 108


def test_reading_config_does_not_run_imports_or_validators(tmp_path):
    sentinel = tmp_path / "must-not-exist"
    source = f'''open({str(sentinel)!r}, "w").write("bad")
class Config:
    count: int = 3
    def __post_init__(self): raise RuntimeError("not called")
    @property
    def budget(self): return self.count * 2
'''
    assert calculate_config_values(source, "Config", properties=["budget"])["properties"] == {"budget": 6}
    assert not sentinel.exists()


@pytest.mark.parametrize("expression", ["__import__('os').getcwd()", "self.__dict__", "2**10000000", "'x'*10000000", "self.budget"])
def test_unsupported_or_unbounded_expressions_are_incomplete_not_success(expression):
    source = f"class C:\n    @property\n    def budget(self): return {expression}\n"
    result = calculate_config_values(source, "C", properties=["budget"])
    assert result["status"] == "incomplete" and result["unsupported"] == ["budget"]


@pytest.mark.parametrize("values", [{"nr": 2}, {"count": True}, {"count": 10**30}])
def test_unknown_fields_or_invalid_types_do_not_silently_fall_back(values):
    with pytest.raises(ValueError):
        calculate_config_values("class C:\n    count: int = 3", "C", values=values)
