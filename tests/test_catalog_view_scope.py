from nsgablack.utils.viz.ui.catalog_view import context_role_match, scope_from_key


def test_scope_from_key_project_prefix():
    assert scope_from_key("project.bias.example") == "project"


def test_scope_from_key_framework_default():
    assert scope_from_key("plugin.module_report") == "framework"


def test_context_role_match_requires():
    info = {
        "context_requires": ["population", "generation"],
        "context_provides": ["pareto_solutions"],
        "context_mutates": ["population"],
    }
    assert context_role_match(info, "generation", "requires")
    assert not context_role_match(info, "generation", "providers")


def test_context_role_match_providers_include_mutates():
    info = {
        "context_requires": [],
        "context_provides": ["pareto_solutions"],
        "context_mutates": ["population"],
    }
    assert context_role_match(info, "population", "providers")
    assert context_role_match(info, "pareto_solutions", "providers")
