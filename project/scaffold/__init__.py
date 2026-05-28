"""Scaffold package — re-exports from project.scaffold_legacy.

Canonical home for scaffold templates.  ``project.scaffold_legacy`` holds the
current monolith implementation; individual sub-modules are targets for
gradual extraction.
"""
from ..scaffold_legacy import (  # noqa: F401
    init_project,
    _FOLDERS, _NON_PACKAGE_FOLDERS, _FOLDER_DESCRIPTIONS,
    _write_file, _readme_for_folder,
    _root_readme, _start_here, _component_registration_guide,
    _build_solver_registration_guide_template,
    _problem_config_template, _problem_template, _problem_class_template,
    _pipeline_config_template, _pipeline_template, _pipeline_class_template,
    _bias_config_template, _bias_template, _bias_class_template,
    _adapter_config_template, _adapter_class_template, _adapter_example_template,
    _adapter_readme, _plugin_template, _plugin_class_template, _plugin_readme,
    _assembly_template, _project_config_template, _run_solver_template,
    _build_solver_template, _solver_config_template,
    _plugins_config_template, _evaluation_config_template,
    _runtime_config_template, _runtime_graph_template,
    _runtime_exporters_template, _runtime_init_template,
    _catalog_project_registry_template, _project_registry_template,
    _project_catalog_entries_template,
    _component_contract_template, _component_test_matrix_readme,
    _smoke_test_template, _contract_test_template,
    _checkpoint_roundtrip_test_template, _strict_fault_test_template,
    _vscode_snippets_template,
)
