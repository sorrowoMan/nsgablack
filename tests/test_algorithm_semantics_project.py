"""All three algorithms execute through the same standard Project/L0 surface."""
from pathlib import Path
import shutil

import pytest

from nsgablack.project.project_runner import execute_project


CASES = {"synchronous_bo", "cmaes_distribution", "map_elites_archive"}


@pytest.fixture(scope="module")
def semantic_project(tmp_path_factory):
    source = Path(__file__).resolve().parents[1] / "examples/cases/algorithm_semantics"
    target = tmp_path_factory.mktemp("algorithm_semantics") / "project"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(
        "results", ".blackbase", "__pycache__", "*.pyc"))
    return target


def test_formal_build_check_describes_real_algorithms(semantic_project):
    result = execute_project(semantic_project, check=True, build_check=True)
    assert result.ok, result.as_dict()
    assert {row.request.case_name for row in result.case_results} == CASES
    names = {row.request.case_name: row.metadata["runtime_state"]["adapter"]
             for row in result.case_results}
    assert len(set(names.values())) == 3
    assert all("Bias" not in value for value in names.values())


@pytest.mark.parametrize("group", ["default", "parallel"])
def test_actual_three_case_run_has_effective_resources_and_real_evaluations(semantic_project, group):
    result = execute_project(semantic_project, group=group)
    assert result.ok, result.as_dict()
    assert {row.request.case_name for row in result.case_results} == CASES
    namespaces = set()
    for row in result.case_results:
        binding = row.resource_usage["binding"]
        assert binding["current"] is True
        effective = row.resource_usage["effective_context"]
        namespaces.add(effective["namespace"])
        assert effective["threads"] == effective["grant"]["workers"] == 1
        report = row.output["report"]
        assert report["steps"] > 0
        assert report["evaluation_count"] > 0
        publication = row.artifact_publications["summary"]
        assert publication.metadata["case_finalization_sealed"] is True
        binding = result.artifact_bindings[f"{row.request.case_name}.summary"]
        assert binding.publication == publication
        assert binding.ref == publication.ref
    assert len(namespaces) == 3
