"""Concrete source proposals must use the receiver actually passed at runtime."""
import hashlib

import pytest

from nsgablack.catalog.lab_edit_check import check_python_edit


POOL = "nsgablack.core.state.solution_pool.SolutionPool"
UNIT = "nsgablack.units.collections.DecompositionUnit"
CONFIG = "nsgablack.adapters.moead.adapter.MOEADConfig"


def codes(report, severity=None):
    return {row["code"] for row in report["diagnostics"] if severity is None or row["severity"] == severity}


def test_raw_pool_rejects_the_previous_models_convenience_pool_call():
    proposal = "def select(request, *, pool, rng):\n    return pool.subpool('ga_elite').random(request.count, rng=rng)\n"
    checked = check_python_edit(proposal, bindings={"pool": POOL})
    assert checked["status"] == "rejected"
    assert any(row.get("symbol") == POOL + ".subpool" for row in checked["diagnostics"])
    assert checked["execution_status"] == "not_run"
    assert checked["binding_assumptions"] == {"pool": POOL}


def test_current_raw_pool_method_is_checked_without_manufacturing_a_runtime_pass():
    proposal = "def select(request, *, pool, rng):\n    return pool.subpool_refs('ga_elite')\n"
    checked = check_python_edit(proposal, bindings={"pool": POOL})
    assert checked["status"] == "needs_runtime_validation"
    assert checked["checked_calls"][0]["symbol"] == POOL + ".subpool_refs"
    assert not codes(checked, "error")
    assert checked["code_sha256"] == hashlib.sha256(proposal.encode()).hexdigest()


def test_algorithm_parameter_is_a_config_field_not_a_unit_field():
    wrong = check_python_edit("return_limit = unit.nr\n", bindings={"unit": UNIT})
    right = check_python_edit("return_limit = cfg.nr\n", bindings={"cfg": CONFIG})
    assert "api_member_undeclared" in codes(wrong)
    assert wrong["checked_fields"] == [] and wrong["unresolved"]
    assert right["status"] == "needs_runtime_validation"
    assert right["checked_fields"][0]["symbol"] == CONFIG + ".nr"


@pytest.mark.parametrize("call", ["pool.subpool_refs()", "pool.subpool_refs('elite', True)",
                                  "pool.subpool_refs('elite', invented=True)",
                                  "pool.subpool_refs('elite', name='other')"])
def test_real_keyword_only_and_required_arguments_are_enforced(call):
    checked = check_python_edit(call, bindings={"pool": POOL})
    assert "api_call_signature_invalid" in codes(checked, "error")


def test_keyword_only_parameter_can_be_passed_by_name():
    checked = check_python_edit("pool.subpool_refs(name='ga_elite', allow_pending=False)", bindings={"pool": POOL})
    assert not codes(checked, "error")
    assert len(checked["checked_calls"]) == 1


def test_import_alias_and_parameter_annotations_infer_real_receiver():
    checked = check_python_edit("""from nsgablack.core.state.solution_pool import SolutionPool as SP
def selected(pool: SP):
    return pool.subpool_refs('ga_elite')
""")
    assert not codes(checked, "error")
    assert checked["checked_calls"][0]["symbol"] == POOL + ".subpool_refs"


def test_imported_module_alias_and_constructor_assignment_preserve_type():
    checked = check_python_edit("""import nsgablack.adapters.moead.adapter as md
cfg = md.MOEADConfig()
limit = cfg.nr
""")
    assert not codes(checked, "error")
    assert any(row["symbol"] == CONFIG + ".nr" for row in checked["checked_fields"])
    assert "constructor_signature_unresolved" in codes(checked)


def test_unaliased_dotted_module_import_preserves_the_class_boundary():
    checked = check_python_edit("""import nsgablack.adapters.moead.adapter
cfg = nsgablack.adapters.moead.adapter.MOEADConfig()
limit = cfg.nr
""")
    assert not codes(checked, "error")
    assert any(row["symbol"] == CONFIG + ".nr" for row in checked["checked_fields"])


def test_import_alias_shadow_does_not_certify_the_old_api():
    checked = check_python_edit("""from nsgablack.core.state.solution_pool import SolutionPool as SP
def use(SP):
    return SP.subpool_refs('ga_elite')
""")
    assert checked["checked_calls"] == []
    assert "attribute_receiver_unresolved" in codes(checked)


def test_local_reassignment_kills_a_previously_inferred_receiver():
    checked = check_python_edit("""def use(pool):
    pool = foreign_object
    return pool.subpool_refs('ga_elite')
""", bindings={"pool": POOL})
    assert checked["checked_calls"] == []
    assert "call_target_unresolved" in codes(checked)


def test_branch_with_different_receiver_does_not_guess_a_joined_type():
    checked = check_python_edit("""def use(pool, condition):
    if condition:
        pool = foreign_object
    return pool.subpool_refs('ga_elite')
""", bindings={"pool": POOL})
    assert checked["checked_calls"] == []
    assert checked["unresolved"]


def test_inherited_unit_field_is_resolved_without_a_builder():
    checked = check_python_edit("values = unit.population", bindings={"unit": UNIT})
    assert not codes(checked, "error")
    assert checked["checked_fields"][0]["symbol"] == UNIT + ".population"


def test_explicit_binding_cannot_silently_override_a_source_annotation():
    checked = check_python_edit("""from nsgablack.units.collections import DecompositionUnit
def wrong(pool: DecompositionUnit):
    return pool.weights
""", bindings={"pool": POOL})
    assert "binding_annotation_conflict" in codes(checked, "error")


def test_unknown_calls_and_dynamic_lookup_are_explicitly_unchecked():
    checked = check_python_edit("""def choose(pool, name):
    method = getattr(pool, name)
    return method()
""", bindings={"pool": POOL})
    assert checked["status"] == "needs_runtime_validation"
    assert "dynamic_operation_unchecked" in codes(checked)
    assert "call_target_unresolved" in codes(checked)


def test_starred_call_is_not_recorded_as_signature_checked():
    checked = check_python_edit("pool.subpool_refs(*args, **kwargs)", bindings={"pool": POOL})
    assert "call_unpacking_unchecked" in codes(checked)
    assert checked["checked_calls"] == []


def test_syntax_errors_and_complex_inputs_are_not_run():
    checked = check_python_edit("def broken(: pass")
    assert checked["status"] == "rejected" and not checked["syntax_ok"]
    assert checked["execution_status"] == "not_run"
    with pytest.raises(ValueError, match="edit_source_invalid"):
        check_python_edit("a" * 48001)
    with pytest.raises(ValueError, match="edit_source_too_complex"):
        check_python_edit("x=1\n" * 1600)


def test_source_drift_fails_closed_without_executing_proposed_code(monkeypatch):
    from nsgablack.catalog import lab_api
    def stale(_):
        raise ValueError("api_source_changed")
    monkeypatch.setattr(lab_api, "verify_api_sources", stale)
    checked = check_python_edit("pool.subpool_refs('ga_elite')", bindings={"pool": POOL})
    assert "api_source_changed" in codes(checked, "error")


def test_class_method_is_bound_and_ordinary_class_method_is_unbound():
    checked = check_python_edit("""from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.core.state.solution_pool import SolutionPool
projection = ObjectiveProjection.from_dict(value)
refs = SolutionPool.subpool_refs(pool, 'ga_elite')
""", bindings={"pool": POOL})
    assert not codes(checked, "error")
    assert len(checked["checked_calls"]) == 2


def test_module_function_uses_real_keyword_only_signature():
    checked = check_python_edit("""from nsgablack.representation.structure_builders import simplex_points
directions = simplex_points(2, 10, positive=True)
""")
    assert not codes(checked, "error")
    assert len(checked["checked_calls"]) == 1
    wrong = check_python_edit("""from nsgablack.representation.structure_builders import simplex_points
directions = simplex_points(2, 10, True)
""")
    assert "api_call_signature_invalid" in codes(wrong, "error")


def test_local_assignment_shadows_outer_receiver_for_the_entire_function():
    checked = check_python_edit("""def use():
    result = pool.subpool_refs('ga_elite')
    pool = foreign_object
    return result
""", bindings={"pool": POOL})
    assert checked["checked_calls"] == []
    assert checked["unresolved"]


@pytest.mark.parametrize("body", ["pool = unknown", "del pool", "if (pool := unknown):\n    pass"])
def test_rebinding_forms_do_not_reuse_a_previous_receiver(body):
    checked = check_python_edit(body + "\npool.subpool_refs('ga_elite')", bindings={"pool": POOL})
    assert checked["checked_calls"] == []
    assert checked["unresolved"]


def test_duplicate_keywords_and_return_outside_function_are_compile_errors():
    for source in ("pool.subpool_refs(name='a', name='b')", "return 1"):
        checked = check_python_edit(source, bindings={"pool": POOL})
        assert not checked["syntax_ok"]
        assert "edit_syntax_invalid" in codes(checked, "error")


def test_large_report_is_bounded_and_truncation_disclosed():
    import json
    checked = check_python_edit("pool.subpool_refs('ga_elite')\n" * 150, bindings={"pool": POOL})
    assert checked["report_truncated"]
    assert len(json.dumps(checked, ensure_ascii=False).encode()) <= 44000


def test_source_is_parsed_not_executed_and_user_mapping_is_not_mutated(tmp_path):
    bindings = {"pool": POOL}
    marker = tmp_path / "must-not-exist"
    checked = check_python_edit(f"open({str(marker)!r}, 'w').write('executed')\npool.subpool_refs('ga_elite')", bindings=bindings)
    assert not marker.exists()
    assert bindings == {"pool": POOL}
    assert checked["execution_status"] == "not_run"
    assert "call_target_unresolved" in codes(checked)


SELECTION = "nsgablack.adapters.change_pool.ChangeSelection"


def test_source_backed_property_container_is_not_a_method():
    wrong = check_python_edit("def change(view):\n    return view.refs()\n", bindings={"change.view": SELECTION})
    assert "api_noncallable_value_called" in codes(wrong, "error")
    right = check_python_edit("def change(view):\n    return view.refs\n", bindings={"change.view": SELECTION})
    assert not codes(right, "error")
    assert right["checked_fields"][0]["symbol"] == SELECTION + ".refs"


def test_scoped_abi_assumption_does_not_bind_a_sibling_parameter_or_global_name():
    source = "def change(view):\n    return view.refs()\ndef helper(view):\n    return view.refs()\nresult = view.refs()\n"
    checked = check_python_edit(source, bindings={"change.view": SELECTION})
    errors = [d for d in checked["diagnostics"] if d["severity"] == "error"]
    assert [d["line"] for d in errors] == [2]
    assert any(d["line"] == 4 and d["code"] == "attribute_receiver_unresolved" for d in checked["diagnostics"])
    assert any(d["line"] == 5 and d["code"] == "attribute_receiver_unresolved" for d in checked["diagnostics"])
    assert checked["binding_assumptions"] == {"change.view": SELECTION}


def test_nested_class_scoped_binding_is_explicit_and_checked():
    checked = check_python_edit("class Custom:\n    def change(self, view):\n        return view.refs()\n", bindings={"Custom.change.view": SELECTION})
    assert "api_noncallable_value_called" in codes(checked, "error")


@pytest.mark.parametrize("import_line,call", [("import numpy as np", "np.array(view, dtype=float)"),
                                                ("from numpy import asarray as cast", "cast(view, dtype=int)")])
def test_numeric_coercion_of_declared_opaque_framework_object_is_rejected(import_line, call):
    source = import_line + "\ndef change(view):\n    return " + call + "\n"
    checked = check_python_edit(source, bindings={"change.view": SELECTION})
    assert "api_numeric_coercion_invalid" in codes(checked, "error")


@pytest.mark.parametrize("body", ["return np.array(view.values, dtype=float)",
                                  "return np.array(view, dtype=object)",
                                  "np = foreign\n    return np.array(view, dtype=float)",
                                  "float = foreign\n    return np.array(view, dtype=float)"])
def test_numeric_coercion_checks_do_not_invent_value_types_or_ignore_shadowing(body):
    checked = check_python_edit("import numpy as np\ndef change(view):\n    " + body + "\n", bindings={"change.view": SELECTION})
    assert "api_numeric_coercion_invalid" not in codes(checked)


def test_proven_errors_remain_visible_after_many_unknowns():
    checked = check_python_edit("foreign.call()\n" * 45 + "view.refs()\n", bindings={"view": SELECTION})
    assert checked["status"] == "rejected" and checked["report_truncated"]
    assert "api_noncallable_value_called" in codes(checked, "error")


def test_constructor_signature_check_does_not_claim_candidate_shape_validation():
    checked = check_python_edit("from nsgablack.adapters.change import ChangeResult\nresult=ChangeResult(candidate)\n")
    assert not codes(checked, "error")
    assert checked["checked_calls"][0]["checked_scope"] == "signature_only"
    assert checked["execution_status"] == "not_run" and checked["status"] == "needs_runtime_validation"


@pytest.mark.parametrize("body,expected", [
    ("view=request.pool.subpool('source')\n    return view.refs()", "api_noncallable_value_called"),
    ("view=request.pool.read(())\n    return np.array(view, dtype=float)", "api_numeric_coercion_invalid"),
])
def test_explicit_callback_abi_connects_real_pool_return_types_to_misuse(body, expected):
    source = "import numpy as np\ndef change(request):\n    " + body + "\n"
    checked = check_python_edit(source, bindings={"change.request": "nsgablack.adapters.change.ChangeRequest"})
    assert expected in codes(checked, "error")
    unknown = check_python_edit(source)
    assert expected not in codes(unknown, "error")
    assert unknown["status"] == "needs_runtime_validation"


def test_numeric_protocol_declaration_prevents_false_opaque_object_rejection(tmp_path, monkeypatch):
    from nsgablack.catalog import lab_api
    path = tmp_path / "adapters"
    path.mkdir()
    (path / "array.py").write_text("class ArraySource:\n    def __array__(self, dtype=None): return unknown\n", encoding="utf-8")
    monkeypatch.setattr(lab_api, "_ROOT", tmp_path)
    checked = check_python_edit("import numpy as np\nresult=np.asarray(view,dtype=float)\n", bindings={"view": "ArraySource"})
    assert "api_numeric_coercion_invalid" not in codes(checked)
