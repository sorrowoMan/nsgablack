"""Historical supply input import uses two actual ledgers and no optimization."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import numpy as np
import pytest

from blackbase.project import CaseRunIdentity, build_case, case_import_context, execute_project, load_case_builder
from blackbase.resources import ArtifactAuthority, ArtifactBinding, ArtifactPublicationError, ArtifactPublisher, coerce_resource_context

PROJECT = Path(__file__).resolve().parents[1] / 'examples/cases/supply_adjustment_nested'
PRODUCTION = PROJECT.parent / 'production_scheduling/cases/production_scheduling'


def seal_fixture(publisher, name, payload):
    """Unit-fixture seal; this does not claim a production solve occurred."""
    ref = publisher.publish(name, payload, serializer='json')
    tx = 'test-fixture-' + name
    publisher.reserve_publication(name, tx)
    publisher.record_provisional_publication(name, tx, ref)
    receipt = publisher.commit_publications(tx, {name: ref}, metadata={
        'case_finalization_sealed': True, 'unit_test_fixture': True})[name]
    return ArtifactBinding(ref, receipt)


@pytest.fixture(scope='module')
def domain():
    with case_import_context(PROJECT, 'supply_adjustment_nested'):
        runtime = importlib.import_module('runtime')
        data = runtime.load_production_case_data(bom_path=None, supply_path=None,
            machines=22, materials=157, days=31, production_case_dir=PRODUCTION)
        problem = importlib.import_module('problem').SupplyEventShiftProblem(
            base_supply=data.supply_matrix, bom_matrix=data.bom_matrix,
            production_case_dir=PRODUCTION, max_moved_events=100)
        projection = importlib.import_module('evaluation.production_case')
        wrapper = importlib.import_module('solver.joint_case').JointSupplyCase
        initializer = importlib.import_module('pipeline.main').FixedSupplyInitializer
    shifts = np.zeros(problem.dimension, dtype=int)
    movable = [i for i, event in enumerate(problem.events) if event.day > 2]
    shifts[movable[0]], shifts[movable[-1]] = 2, 1
    adjusted = problem.apply_shifts(shifts)
    return SimpleNamespace(problem=problem, data=data, shifts=shifts,
        adjusted=adjusted, source=projection.source_descriptor(data),
        digest=projection.compute_scenario_digest(data.bom_matrix, adjusted),
        wrapper=wrapper, initializer=initializer)


def original_plan(domain):
    identity = CaseRunIdentity(project_run_id='old-run', root_run_id='old-run',
        case_run_id='old-search', invocation_id='old-search', depth=0)
    inner = identity.child(case_run_id='old-child')
    source = deepcopy(domain.source)
    # Producer-only paths are deliberately unreadable on this host. The importer
    # must use current canonical files and compare their content identities.
    for key in source:
        source[key]['path'] = '/unmounted-producer-only/' + key
    return {'schema': 'supply_adjustment_nested.joint_summary/v1',
        'identity': identity.as_dict(), 'inner_case_identity': inner.as_dict(),
        'candidate_token': 'historical-proposal',
        'accepted_solution_ref': {'candidate_token': 'historical-proposal', 'pool_id': 'old-pool', 'record_id': 'old-record', 'row': 0},
        'source': source, 'scenario_digest': domain.digest, 'candidate': domain.shifts.astype(float).tolist(),
        'shifts': domain.shifts.tolist(), 'adjusted_supply': domain.adjusted.tolist(),
        'schedule': np.zeros((22, 31)).tolist(), 'total_output': 0.,
        'raw_objectives': [0., 2., 3.], 'day0_max_abs_delta': 0., 'material_total_max_abs_delta': 0.,
        'raw_constraint_violation': 0.}


@pytest.fixture
def source(tmp_path, domain):
    old = ArtifactAuthority(root=str(tmp_path / 'old-artifacts'), namespace='old-supply')
    old_publisher = ArtifactPublisher(old, project_run_id='old-run', case_run_id='old-search')
    plan = original_plan(domain)
    binding = seal_fixture(old_publisher, 'joint_summary', plan)
    authority = ArtifactAuthority(root=str(tmp_path / 'new-artifacts'), namespace='new-supply')
    publisher = ArtifactPublisher(authority, project_run_id='new-run', case_run_id='import-case')
    builder = load_case_builder(PROJECT, 'supply_plan_import')
    case = build_case(builder, resource_context={'threads': 1}, component_overrides={
        'old_authority': old.as_dict(), 'old_binding': binding.as_dict(),
        'production_case_dir': str(PRODUCTION)})
    class Runtime:
        identity = CaseRunIdentity(project_run_id='new-run', root_run_id='new-run', case_run_id='import-case', invocation_id='import-case')
        artifact_publisher = publisher
        published = {}
        def checkpoint(self): pass
        def publish_artifact(self, name, value, **kwargs):
            self.published[name] = seal_fixture(publisher, name, value)
            return self.published[name].ref
    runtime = Runtime()
    case.set_case_runtime(runtime)
    return SimpleNamespace(old=old, old_publisher=old_publisher, binding=binding,
        authority=authority, publisher=publisher, case=case, runtime=runtime, plan=plan)


def old_file_digests(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in Path(root).rglob('*') if path.is_file()}


def test_import_explicitly_reads_old_ledger_without_switching_new_profile(source, domain, monkeypatch):
    before = old_file_digests(source.old.root)
    profile = '{"endpoint":"http://127.0.0.1:1","authority":{"namespace":"new-only"}}'
    monkeypatch.setenv('BLACKBASE_ARTIFACT_HTTP_PROFILE', profile)
    output = source.case.run()
    exported = source.case.export_case_result(output)
    binding = source.runtime.published['candidate_plan']
    assert output['schema'] == 'supply_adjustment_nested.candidate_plan/v1'
    assert output['identity'] == source.runtime.identity.as_dict()
    assert output['identity'] != source.plan['identity']
    assert set(output) == {'schema', 'identity', 'source', 'candidate', 'shifts', 'adjusted_supply', 'scenario_digest', 'derived_from'}
    assert output['source'] == domain.source
    assert output['shifts'] == domain.shifts.tolist()
    assert output['derived_from']['authority'] == source.old.as_dict()
    assert output['derived_from']['binding'] == source.binding.as_dict()
    assert output['derived_from']['sha256'] == source.binding.ref.checksum
    assert binding.publication.authority_namespace == source.authority.namespace
    assert exported['imported_source']['evaluations'] == 0
    assert old_file_digests(source.old.root) == before
    import os
    assert os.environ['BLACKBASE_ARTIFACT_HTTP_PROFILE'] == profile


def make_receiver(domain, publisher, binding):
    from nsgablack.adapters import FixedCandidateAdapter
    class Solver:
        def __init__(self):
            self.problem, self.adapter = domain.problem, FixedCandidateAdapter()
            self.representation_pipeline = SimpleNamespace(initializer=domain.initializer(np.zeros(domain.problem.dimension)))
            self.plugin_manager = self.evaluation_mediator = None
            self.resource_context = coerce_resource_context({'threads': 1})
            self.supply_source = domain.source
            self.generation = self.evaluation_count = 0
        def set_case_runtime(self, runtime): self.case_runtime = runtime
        def run(self): return self.representation_pipeline.initializer.initialize(self.problem)
    case = domain.wrapper(Solver())
    runtime = SimpleNamespace(request=SimpleNamespace(input_artifact_bindings={'candidate_plan': binding}), artifact_publisher=publisher)
    return case.set_case_runtime(runtime).set_input_artifacts({'candidate_plan': binding.ref})


def test_new_plan_is_an_input_and_is_not_misrepresented_as_an_evaluated_candidate(source, domain):
    output = source.case.run()
    source.case.export_case_result(output)
    binding = source.runtime.published['candidate_plan']
    receiver = make_receiver(domain, source.publisher, binding)
    np.testing.assert_array_equal(receiver.run(), domain.shifts)
    assert receiver._candidate_plan_binding == binding
    assert receiver._candidate_plan_derived_from == output['derived_from']
    assert 'candidate_token' not in output and 'accepted_solution_ref' not in output


def test_legacy_same_authority_joint_summary_input_still_works(source, domain):
    receiver = make_receiver(domain, source.old_publisher, source.binding)
    np.testing.assert_array_equal(receiver.run(), domain.shifts)
    assert receiver._candidate_plan_derived_from is None


@pytest.mark.parametrize('change', ['origin', 'publication_identity', 'candidate_shape'])
def test_new_candidate_input_requires_its_own_publication_and_historical_trace(source, domain, change):
    plan = source.case.run()
    if change == 'origin': plan['derived_from']['sha256'] = 'sha256:' + '0' * 64
    elif change == 'publication_identity': plan['identity']['case_run_id'] = 'copied-historical-identity'
    else: plan['candidate'] = plan['candidate'][:-1]
    binding = seal_fixture(source.publisher, 'bad-input-' + change, plan)
    receiver = make_receiver(domain, source.publisher, binding)
    with pytest.raises(ValueError):
        receiver.run()
    assert receiver._candidate_plan_applied is False


@pytest.mark.parametrize('change', ['bytes', 'source', 'day0', 'shape', 'identity', 'scenario'])
def test_invalid_original_plan_cannot_produce_a_new_successful_input(tmp_path, source, domain, change):
    if change == 'bytes':
        Path(source.binding.ref.uri).write_bytes(b'{"tampered":true}')
    else:
        plan = deepcopy(source.plan)
        if change == 'source': plan['source']['bom']['sha256'] = '0' * 64
        elif change == 'day0': plan['adjusted_supply'][0][0] += 1
        elif change == 'shape': plan['candidate'] = plan['candidate'][:-1]
        elif change == 'identity': plan['identity']['case_run_id'] = 'not-the-producer'
        elif change == 'scenario': plan['scenario_digest'] = 'sha256:' + '0' * 64
        source.case.old_binding = seal_fixture(source.old_publisher, 'changed-' + change, plan)
    with pytest.raises((ValueError, ArtifactPublicationError)):
        source.case.run()
    assert not source.runtime.published


def test_formal_project_import_is_sealed_in_new_authority_without_evaluation(tmp_path, source):
    root = tmp_path / 'import-project'
    (root / 'cases').mkdir(parents=True)
    (root / 'cases/__init__.py').write_text('', encoding='utf-8')
    for name in ('supply_plan_import', 'supply_adjustment_nested', 'production_inner', 'artifact_delivery_check'):
        shutil.copytree(PROJECT / 'cases' / name, root / 'cases' / name,
            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '_artifacts'))
    overrides = {'old_authority': source.old.as_dict(), 'old_binding': source.binding.as_dict(), 'production_case_dir': str(PRODUCTION)}
    (root / 'project_config.py').write_text(f'''
PROJECT_NAME = "import-proof"
L0 = {{"namespace": "new-import-proof", "offer": {{"threads": 1}},
      "policy": {{"mode": "strict", "max_threads": 1}}, "default_request": {{"threads": 1}},
      "lease_backend": "sqlite", "lease_path": ".blackbase/leases.sqlite"}}
STAGES = [{{"name": "import", "cases": ["supply_plan_import"], "mode": "build",
           "component_overrides": {{"supply_plan_import": {overrides!r}}}}}]
GROUPS = {{"default": {{"stages": ["import"]}}}}
''', encoding='utf-8')
    before = old_file_digests(source.old.root)
    result = execute_project(root, run_id='formal-import-proof', record=False)
    assert result.ok, result.as_dict()
    imported = result.case_results[0]
    binding = ArtifactBinding(imported.artifact_refs['candidate_plan'], imported.artifact_publications['candidate_plan'])
    reader = ArtifactPublisher.from_resource_context(imported.request.resource_context,
        project_run_id=imported.identity.project_run_id, case_run_id=imported.identity.case_run_id)
    payload = json.loads(reader.read_verified(binding))
    assert payload['identity'] == imported.identity.as_dict()
    assert payload['derived_from']['binding'] == source.binding.as_dict()
    assert imported.output['imported_source']['evaluations'] == 0
    assert binding.publication.authority_namespace == 'new-import-proof'
    assert old_file_digests(source.old.root) == before
