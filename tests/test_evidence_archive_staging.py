"""Archive staging keeps refs; retention release reloads sealed verified bodies."""
from __future__ import annotations

import gc
import json
from pathlib import Path
import weakref

import pytest

from blackbase.evaluation import (
    EvaluationEvidenceArchiveManifest, EvaluationEvidenceArchiveBundle,
    EvaluationEvidenceArchiveError, iter_evaluation_evidence_archives,
)
from blackbase.resources import ArtifactBinding, ArtifactPublicationError
from nsgablack.core import ComposableSolver

from tests.test_evaluation_evidence_recovery import _Adapter, _ArchiveCaseRuntime, _Problem


def _stage(tmp_path, *, count=1):
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    event_ids = []
    for _ in range(count):
        outcome = solver.step()
        event_ids.append(outcome.metadata["evaluation_disposition"]["event_id"])
    runtime = _ArchiveCaseRuntime(tmp_path)
    solver.set_case_runtime(runtime)
    staged = solver.stage_evaluation_evidence_archives()
    assert set(staged) == set(event_ids)
    return solver, runtime, event_ids


def _assert_pinned(solver, event_id):
    record = solver.evaluation_evidence_journal.get(event_id)
    assert record.archive_binding is None and record.retention_released is False
    assert solver.snapshot_store.read(record.event_ref["key"]).pinned
    assert solver.snapshot_store.read(record.decision_carrier_ref["key"]).pinned


def test_staging_does_not_retain_manifests_and_repeated_calls_are_idempotent(tmp_path, monkeypatch):
    original = EvaluationEvidenceArchiveBundle.__post_init__
    manifests = []

    def observe(manifest):
        original(manifest)
        manifests.append(weakref.ref(manifest))

    monkeypatch.setattr(EvaluationEvidenceArchiveBundle, "__post_init__", observe)
    solver, runtime, event_ids = _stage(tmp_path, count=3)
    gc.collect()
    assert len(manifests) == 1 and all(ref() is None for ref in manifests)
    entries = solver._evaluation_evidence_archive_staging["entries"]
    assert all(set(entry) == {"event_ids", "ref"} for entry in entries.values())
    assert len(runtime.observers) == 1
    initial_refs = dict(runtime.refs)
    assert solver.stage_evaluation_evidence_archives() == {
        event_id: entry["ref"] for entry in entries.values() for event_id in entry["event_ids"]
    }
    assert runtime.refs == initial_refs and len(runtime.observers) == 1
    assert len(manifests) == 1
    for event_id in event_ids:
        _assert_pinned(solver, event_id)

    reader = runtime.artifact_publisher.read_verified
    reads = []

    def verify_seal_before_read(binding):
        assert runtime.artifact_publisher.verify_publication(binding.publication)
        reads.append(binding.ref)
        return reader(binding)

    monkeypatch.setattr(runtime.artifact_publisher, "read_verified", verify_seal_before_read)
    runtime.seal()
    for event_id in event_ids:
        assert solver.evaluation_evidence_journal.get(event_id).retention_released
    assert len(reads) == 1
    assert all(set(entry) == {"event_ids", "ref"} for entry in entries.values())
    assert solver.stage_evaluation_evidence_archives() == {}
    runtime.seal()  # duplicate notification must not create/release another graph
    assert len(reads) == 2 and runtime.refs == initial_refs


def test_archive_read_failure_keeps_pins_and_can_be_retried_after_seal(tmp_path, monkeypatch):
    solver, runtime, event_ids = _stage(tmp_path)
    reader = runtime.artifact_publisher.read_verified

    def unavailable(binding):
        raise OSError("archive temporarily unreadable")

    monkeypatch.setattr(runtime.artifact_publisher, "read_verified", unavailable)
    with pytest.raises(OSError, match="temporarily unreadable"):
        runtime.seal()
    _assert_pinned(solver, event_ids[0])
    monkeypatch.setattr(runtime.artifact_publisher, "read_verified", reader)
    runtime.seal()
    assert solver.evaluation_evidence_journal.get(event_ids[0]).retention_released


def test_adjacent_commits_share_exact_roots_in_one_self_contained_sealed_body(tmp_path):
    solver, runtime, event_ids = _stage(tmp_path, count=3)
    assert len(runtime.refs) == 1
    ref = next(iter(runtime.refs.values()))
    bundle = EvaluationEvidenceArchiveBundle.from_dict(json.loads(Path(ref.uri).read_bytes()))
    records = [solver.evaluation_evidence_journal.get(event_id) for event_id in event_ids]
    legacy = [EvaluationEvidenceArchiveManifest.from_record(record, snapshots=solver.snapshot_store) for record in records]
    assert len(bundle.snapshot_contents_b64) < sum(len(item.snapshot_contents_b64) for item in legacy)
    assert len(bundle.canonical_bytes()) < sum(len(item.canonical_bytes()) for item in legacy)
    (tmp_path / "bundle_stats.json").write_text(json.dumps({
        "events": len(records), "artifact_count_before": len(legacy), "artifact_count_after": 1,
        "root_content_copies_before": sum(len(item.snapshot_contents_b64) for item in legacy),
        "root_content_copies_after": len(bundle.snapshot_contents_b64),
        "legacy_json_bytes": sum(len(item.canonical_bytes()) for item in legacy),
        "bundle_json_bytes": len(bundle.canonical_bytes()),
    }, indent=2), encoding="utf-8")
    for record, manifest in zip(records, legacy):
        resolved = bundle.manifest_for(record.event_id)
        assert resolved == manifest
        resolved.validate_record(record)
        resolved.validate_snapshot_contents()
        _assert_pinned(solver, record.event_id)
    runtime.seal()
    bindings = [solver.evaluation_evidence_journal.get(event_id).archive_binding for event_id in event_ids]
    assert all(binding == bindings[0] for binding in bindings)
    assert all(solver.evaluation_evidence_journal.get(event_id).retention_released for event_id in event_ids)


def test_sealed_eight_event_bundle_uses_one_bulk_release_operation(tmp_path, monkeypatch):
    import blackbase.resources.artifacts as artifacts

    solver, runtime, event_ids = _stage(tmp_path, count=8)
    coordinator = solver.evaluation_evidence_coordinator
    release = coordinator.archive_bundle_and_release
    sha256 = artifacts._sha256
    refs = {Path(ref.uri) for ref in runtime.refs.values()}
    hash_reads, operations = [], []

    def count_hash(path):
        if Path(path) in refs:
            hash_reads.append(path)
        return sha256(path)

    def bulk_release(**kwargs):
        operations.append(tuple(kwargs["event_order"]))
        return release(**kwargs)

    def unexpected_single_release(*args, **kwargs):
        raise AssertionError("sealed bundles must use the bundle operation")

    monkeypatch.setattr(artifacts, "_sha256", count_hash)
    monkeypatch.setattr(coordinator, "archive_bundle_and_release", bulk_release)
    monkeypatch.setattr(coordinator, "archive_and_release", unexpected_single_release)
    runtime.seal()
    assert operations == [tuple(event_ids)]
    # One seal hash, one Publisher ledger check, two operation ledger checks.
    # The Store's verified payload read separately checks hashlib.sha256 bytes.
    assert len(hash_reads) == 4
    assert all(solver.evaluation_evidence_journal.get(event_id).retention_released for event_id in event_ids)


def test_bundle_release_recovers_remaining_events_after_ack_failure_without_staging(tmp_path, monkeypatch):
    solver, runtime, event_ids = _stage(tmp_path, count=3)
    journal = solver.evaluation_evidence_journal
    mark = journal.mark_retention_released
    failed = []
    def lose_second_ack(event_id, **kwargs):
        if event_id == event_ids[1] and not failed:
            failed.append(event_id)
            raise OSError("second release acknowledgement lost")
        return mark(event_id, **kwargs)
    monkeypatch.setattr(journal, "mark_retention_released", lose_second_ack)
    with pytest.raises(OSError, match="acknowledgement lost"):
        runtime.seal()
    assert all(journal.get(event_id).archive_binding is not None for event_id in event_ids)
    assert journal.get(event_ids[0]).retention_released
    assert not journal.get(event_ids[2]).retention_released
    monkeypatch.setattr(journal, "mark_retention_released", mark)
    solver._evaluation_evidence_archive_staging = {}
    resumed = solver.stage_evaluation_evidence_archives()
    assert set(resumed) == set(event_ids[1:])
    assert all(journal.get(event_id).retention_released for event_id in event_ids)
    assert len(runtime.refs) == 1  # recovery did not invent a second archive.


def test_partial_bundle_binding_recovers_before_any_pin_is_released(tmp_path, monkeypatch):
    solver, runtime, event_ids = _stage(tmp_path, count=3)
    journal = solver.evaluation_evidence_journal
    bind = journal.bind_archive
    attempted = []
    def fail_second_binding(event_id, *args, **kwargs):
        attempted.append(event_id)
        if len(attempted) == 2:
            raise OSError("second binding interrupted")
        return bind(event_id, *args, **kwargs)
    monkeypatch.setattr(journal, "bind_archive", fail_second_binding)
    with pytest.raises(OSError, match="binding interrupted"):
        runtime.seal()
    assert sum(journal.get(event_id).archive_binding is not None for event_id in event_ids) == 1
    for event_id in event_ids:
        record = journal.get(event_id)
        assert not record.retention_released
        assert solver.snapshot_store.read(record.event_ref["key"]).pinned
    monkeypatch.setattr(journal, "bind_archive", bind)
    solver._evaluation_evidence_archive_staging = {}
    assert set(solver.stage_evaluation_evidence_archives()) == set(event_ids)
    assert all(journal.get(event_id).retention_released for event_id in event_ids)
    assert len(runtime.refs) == 1


@pytest.mark.parametrize("change", ["missing_root", "tampered_root", "wrong_event", "extra_root"])
def test_invalid_bundle_cannot_release_any_member_pins(tmp_path, monkeypatch, change):
    solver, runtime, event_ids = _stage(tmp_path, count=3)
    read = runtime.artifact_publisher.read_verified
    def corrupt(binding):
        payload = json.loads(read(binding))
        contents = payload["snapshot_contents_b64"]
        if change == "missing_root":
            contents.pop(next(iter(contents)))
        elif change == "tampered_root":
            contents[next(iter(contents))] = "e30="
        elif change == "extra_root":
            contents["unbound-root"] = "e30="
        else:
            first = next(iter(payload["manifests"]))
            payload["manifests"][first]["event_id"] = "a-different-event"
        return json.dumps(payload).encode("utf-8")
    monkeypatch.setattr(runtime.artifact_publisher, "read_verified", corrupt)
    with pytest.raises((ValueError, EvaluationEvidenceArchiveError)):
        runtime.seal()
    for event_id in event_ids:
        _assert_pinned(solver, event_id)


def test_bundle_count_and_byte_thresholds_bound_groups_and_singletons_keep_v2(tmp_path):
    solver, runtime, event_ids = _stage(tmp_path, count=3)
    records = [solver.evaluation_evidence_journal.get(event_id) for event_id in event_ids]
    grouped = list(iter_evaluation_evidence_archives(records, snapshots=solver.snapshot_store, max_events=2))
    assert len(grouped) == 2 and isinstance(grouped[0], EvaluationEvidenceArchiveBundle)
    assert isinstance(grouped[1], EvaluationEvidenceArchiveManifest)
    singles = list(iter_evaluation_evidence_archives(records, snapshots=solver.snapshot_store, max_content_bytes=1))
    assert len(singles) == 3 and all(isinstance(item, EvaluationEvidenceArchiveManifest) for item in singles)


def test_archive_tampered_after_authority_seal_cannot_release_evidence(tmp_path):
    solver, runtime, event_ids = _stage(tmp_path)
    receipts = runtime.artifact_publisher.commit_publications(
        runtime.transaction_id, runtime.refs, metadata={"case_finalization_sealed": True},
    )
    ref = next(iter(runtime.refs.values()))
    path = Path(ref.uri)
    original = path.read_bytes()
    path.write_bytes(b"x" * len(original))
    observer = runtime.observers[0][1]
    with pytest.raises(ArtifactPublicationError):
        observer(receipts)
    _assert_pinned(solver, event_ids[0])
    path.write_bytes(original)
    observer(receipts)
    assert solver.evaluation_evidence_journal.get(event_ids[0]).retention_released


@pytest.mark.parametrize("invalid", ["wrong_type", "not_object", "not_json", "old_schema", "snapshot_digest"])
def test_invalid_reloaded_body_fails_closed_before_retention_release(tmp_path, monkeypatch, invalid):
    solver, runtime, event_ids = _stage(tmp_path)
    reader = runtime.artifact_publisher.read_verified

    def bad_body(binding):
        raw = reader(binding)
        if invalid == "wrong_type":
            return {"not": "bytes"}
        if invalid == "not_object":
            return b"[]"
        if invalid == "not_json":
            return b"not-json"
        manifest = json.loads(raw)
        if invalid == "old_schema":
            manifest["schema"] = "blackbase.evaluation_evidence_archive/v1"
        else:
            key = next(iter(manifest["snapshot_contents_b64"]))
            manifest["snapshot_contents_b64"][key] = "e30="
        return json.dumps(manifest).encode("utf-8")

    monkeypatch.setattr(runtime.artifact_publisher, "read_verified", bad_body)
    with pytest.raises((TypeError, ValueError, EvaluationEvidenceArchiveError)):
        runtime.seal()
    _assert_pinned(solver, event_ids[0])


def test_standard_project_case_reloads_sealed_archives_then_releases_pins(tmp_path, monkeypatch):
    from blackbase.project import add_case, create_project, execute_project
    import blackbase.project.invocation as invocation

    project = create_project(tmp_path / "archive_case", framework="blackbase")
    case = add_case("search", "solver", project_root=project)
    (case / "build_solver.py").write_text('''
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.adapters import AlgorithmAdapter

class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-1., 1.)])
    def evaluate(self, x):
        return float(x[0] ** 2)

class Adapter(AlgorithmAdapter):
    def __init__(self):
        super().__init__(name="archive-test")
    def propose(self, solver, context):
        return [[0.5]]
    def update(self, solver, candidates, feedback, context):
        pass

class ThreeSteps(ComposableSolver):
    def run(self):
        return super().run(max_steps=3)

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    return ThreeSteps(Problem(), adapter=Adapter(), resource_context=resource_context)
'''.lstrip(), encoding="utf-8")
    (project / "project_config.py").write_text('''
PROJECT_NAME = "archive_case"
STAGES = [{"name": "run", "cases": ["search"]}]
GROUPS = {"default": {"stages": ["run"]}}
'''.lstrip(), encoding="utf-8")
    built = []
    original_build = invocation.build_case

    def capture(*args, **kwargs):
        solver = original_build(*args, **kwargs)
        built.append(solver)
        original_runtime = solver.set_case_runtime

        def bind_runtime(runtime):
            original_runtime(runtime)
            original_reader = runtime.artifact_publisher.read_verified

            def read(binding):
                assert runtime.artifact_publisher.verify_publication(binding.publication)
                raw = original_reader(binding)
                payload = json.loads(raw)
                event_ids = tuple(payload["manifests"]) if "manifests" in payload else (payload["event_id"],)
                for event_id in event_ids:
                    record = solver.evaluation_evidence_journal.get(event_id)
                    assert record.retention_released is False
                    assert solver.snapshot_store.read(record.event_ref["key"]).pinned
                return raw

            runtime.artifact_publisher.read_verified = read
            return solver

        solver.set_case_runtime = bind_runtime
        return solver

    monkeypatch.setattr(invocation, "build_case", capture)
    result = execute_project(project, record=False)
    assert result.ok, [case.error for case in result.case_results]
    solver = built[0]
    entries = solver._evaluation_evidence_archive_staging["entries"]
    assert len(entries) == 1 and all(set(entry) == {"event_ids", "ref"} for entry in entries.values())
    for name, entry in entries.items():
        assert len(entry["event_ids"]) == 3
        for event_id in entry["event_ids"]:
            record = solver.evaluation_evidence_journal.get(event_id)
            assert record.retention_released and record.archive_binding
            assert not solver.snapshot_store.read(record.event_ref["key"]).pinned
            output = result.case_results[0]
            assert ArtifactBinding.from_dict(record.archive_binding) == ArtifactBinding(
                ref=output.artifact_refs[name], publication=output.artifact_publications[name],
            )
    assert not solver.case_runtime.audit()["finalization_observers"]["failures"]
