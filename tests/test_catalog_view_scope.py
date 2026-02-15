from nsgablack.utils.viz.ui.catalog_view import scope_from_key


def test_scope_from_key_project_prefix():
    assert scope_from_key("project.bias.example") == "project"


def test_scope_from_key_framework_default():
    assert scope_from_key("plugin.module_report") == "framework"

