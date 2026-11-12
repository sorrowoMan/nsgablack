"""Host automation boundaries: reservations, fairness, grants and cleanup."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

import pytest


@pytest.fixture
def scheduler():
    path = Path(__file__).resolve().parents[1] / "deployment/catalog/auto_curate.py"
    spec = importlib.util.spec_from_file_location("catalog_auto_curate_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def private_model_config(tmp_path):
    directory = tmp_path / "secrets"
    directory.mkdir(exist_ok=True)
    (directory / "deepseek.json").write_text(json.dumps({"model": "deepseek-flash", "api_key": "never-print-this-key"}))


def packet(n=45):
    value = {"model": "deepseek-flash", "prompt": "catalog-explainer-zh-v3", "entries": [
        {"key": f"adapter.example_{i:03}", "digest": f"{i:064x}", "cached": False, "evidence": True}
        for i in range(n)]}
    value["source_index_sha256"] = hashlib.sha256(json.dumps(
        {e["key"]: e["digest"] for e in value["entries"]}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return value


def new_state(scheduler):
    return scheduler.read_state(Path("does-not-exist-auto-curate-test.json"))


@pytest.mark.parametrize("mode", ["once", "drain"])
def test_unapproved_automation_stops_before_state_or_docker(scheduler, tmp_path, monkeypatch, mode):
    def forbidden(*args, **kwargs):
        raise AssertionError("Unapproved execution must not read grants, probe or reserve")
    monkeypatch.setattr(scheduler, "Docker", forbidden)
    monkeypatch.setattr(scheduler, "read_state", forbidden)
    with pytest.raises(scheduler.SchedulerError, match="^ai_paid_execution_required$"):
        if mode == "once":
            scheduler.once(tmp_path)
        else:
            scheduler.drain(tmp_path, max_items=20)
    assert list(tmp_path.iterdir()) == [tmp_path / "secrets"]


def test_old_timer_command_cannot_implicitly_authorize_payment(scheduler, tmp_path):
    with pytest.raises(SystemExit) as exc:
        scheduler.main(["--root", str(tmp_path), "--once"])
    assert exc.value.code == 2
    assert not (tmp_path / "automation").exists()


def test_writer_docker_requires_explicit_execution_before_cleanup(scheduler, tmp_path, monkeypatch):
    docker = scheduler.Docker(tmp_path)
    monkeypatch.setattr(docker, "cleanup", lambda: pytest.fail("No Docker activity is authorized"))
    with pytest.raises(scheduler.SchedulerError, match="^ai_paid_execution_required$"):
        docker.run("sha256:" + "a" * 64, probe=False, keys=["adapter.example"])


def test_cached_and_evidenceless_entries_never_request_model(scheduler):
    probe = packet(3)
    probe["entries"][0]["cached"] = True
    probe["entries"][1]["evidence"] = False
    assert [e["key"] for e in scheduler.select_batch(new_state(scheduler), probe, 100000)] == [probe["entries"][2]["key"]]


def test_failed_first_batch_cannot_starve_later_components(scheduler):
    state, probe = new_state(scheduler), packet()
    first = scheduler.select_batch(state, probe, 100000)
    scheduler.reserve(state, probe, first, 100000)
    report = {"results": [{"entry_key": e["key"], "error": "note_evidence_validation_failed"} for e in first]}
    assert scheduler.settle(state, probe, first, report, 100000) == {"generated": 0, "failed": 20}
    second = scheduler.select_batch(state, probe, 100901)
    assert len(second) == 20
    assert not {e["key"] for e in first} & {e["key"] for e in second}
    scheduler.reserve(state, probe, second, 100901)
    third = scheduler.select_batch(state, probe, 101802)
    assert third[0]["key"] == probe["entries"][40]["key"]


def test_daily_reservation_counts_failures_and_resets_only_forward_day(scheduler):
    state, probe = new_state(scheduler), packet(101)
    for t in range(5):
        chosen = scheduler.select_batch(state, probe, 100000 + t * 901)
        scheduler.reserve(state, probe, chosen, 100000 + t * 901)
    assert state["reserved"] == 100
    assert scheduler.select_batch(state, probe, 105000) == []
    assert scheduler.select_batch(state, probe, 1) == []  # A clock rollback cannot mint a new budget.
    assert len(scheduler.select_batch(state, probe, 200000)) == 20
    assert state["reserved"] == 0


def test_backoff_identity_includes_source_model_and_prompt(scheduler):
    state, probe = new_state(scheduler), packet(1)
    chosen = scheduler.select_batch(state, probe, 100000)
    scheduler.reserve(state, probe, chosen, 100000)
    assert scheduler.select_batch(state, probe, 100001) == []
    probe["entries"][0]["digest"] = "f" * 64
    assert len(scheduler.select_batch(state, probe, 100001)) == 1
    scheduler.reserve(state, probe, chosen, 100001)
    probe["model"] = "another-model"
    assert len(scheduler.select_batch(state, probe, 100002)) == 1
    scheduler.reserve(state, probe, chosen, 100002)
    probe["prompt"] = "catalog-explainer-zh-v4"
    assert len(scheduler.select_batch(state, probe, 100003)) == 1


def test_auth_or_balance_failure_opens_circuit(scheduler):
    state, probe = new_state(scheduler), packet(3)
    chosen = scheduler.select_batch(state, probe, 100000)
    scheduler.reserve(state, probe, chosen, 100000)
    result = scheduler.settle(state, probe, chosen, {"results": [{"entry_key": chosen[0]["key"], "error": "ai_http_402"}]}, 100000)
    assert result == {"generated": 0, "failed": 3}
    assert state["circuit_until"] == 186400
    assert scheduler.select_batch(state, probe, 150000) == []


def test_ambiguous_exit_preserves_reservations_before_model(scheduler, tmp_path):
    state_dir = tmp_path / "automation/state"
    state_dir.mkdir(parents=True)

    class BrokenDocker:
        def image(self):
            return "sha256:" + "a" * 64, "release"

        def run(self, image, *, probe, keys=None, execute=False):
            if probe:
                return packet(25)
            saved = json.loads((state_dir / "state.json").read_text())
            assert saved["reserved"] == 20 and len(saved["failures"]) == 20
            raise scheduler.SchedulerError("docker_timeout")

    with pytest.raises(scheduler.SchedulerError, match="docker_timeout"):
        scheduler.once(tmp_path, execute=True, now=100000, docker=BrokenDocker())
    saved = scheduler.read_state(state_dir / "state.json")
    assert saved["reserved"] == 20
    assert scheduler.select_batch(saved, packet(25), 100001)[0]["key"] == "adapter.example_020"


def test_success_removes_failure_and_status_records_progress(scheduler, tmp_path):
    (tmp_path / "automation/state").mkdir(parents=True)

    class GoodDocker:
        cached = set()

        def image(self):
            return "sha256:" + "a" * 64, "release"

        def run(self, image, *, probe, keys=None, execute=False):
            if probe:
                value = packet(3)
                for entry in value["entries"]:
                    entry["cached"] = entry["key"] in self.cached
                return value
            self.cached.update(keys)
            return {"results": [{"entry_key": key} for key in keys]}

    result = scheduler.once(tmp_path, execute=True, now=100000, docker=GoodDocker())
    assert result["current"] == result["generated"] == result["reserved_today"] == 3
    assert result["status"] == "complete" and result["remaining"] == 0
    assert scheduler.read_state(tmp_path / "automation/state/state.json")["failures"] == {}


@pytest.mark.parametrize("exception", ["timeout", "signal"])
def test_timeout_and_stop_remove_only_captured_owned_id(scheduler, tmp_path, exception):
    (tmp_path / "automation/state").mkdir(parents=True)
    docker = scheduler.Docker(tmp_path)
    calls, cid = [], "b" * 64

    def call(args, **kwargs):
        calls.append(args)
        if args[0] == "create":
            return subprocess.CompletedProcess(args, 0, cid, "")
        if args[0] == "start":
            raise scheduler.SchedulerError("docker_timeout") if exception == "timeout" else scheduler.Interrupted("interrupted")
        if args[0] == "inspect":
            nonce = json.loads(docker.ownerfile.read_text())["nonce"]
            return subprocess.CompletedProcess(args, 0, cid + " /" + scheduler.CONTAINER + " managed " + nonce, "")
        return subprocess.CompletedProcess(args, 0, "", "")

    docker.call = call
    with pytest.raises(scheduler.SchedulerError):
        docker.run("sha256:" + "a" * 64, probe=False, keys=["adapter.nsga2"], execute=True)
    assert [a for a in calls if a[0] == "rm"] == [["rm", "--force", cid]]
    assert not any(scheduler.CONTAINER in a for a in calls if a[0] == "rm")


def test_cleanup_refuses_another_container_identity(scheduler, tmp_path):
    docker = scheduler.Docker(tmp_path)
    docker.cid = "c" * 64
    docker.ownerfile.parent.mkdir(parents=True)
    scheduler.atomic_json(docker.ownerfile, {"nonce": "a" * 32})
    calls = []

    def call(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "/unrelated managed", "")

    docker.call = call
    with pytest.raises(scheduler.SchedulerError, match="worker_identity_conflict"):
        docker.cleanup()
    assert not any(args[0] == "rm" for args in calls)


@pytest.mark.parametrize("probe", [True, False])
def test_probe_has_read_only_grant_and_generation_alone_gets_writer(scheduler, tmp_path, probe):
    (tmp_path / "automation/state").mkdir(parents=True)
    docker = scheduler.Docker(tmp_path)
    calls = []

    def call(args, **kwargs):
        calls.append(args)
        if args[0] == "create":
            return subprocess.CompletedProcess(args, 0, "d" * 64, "")
        if args[0] == "start":
            return subprocess.CompletedProcess(args, 0, "{}", "")
        if args[0] == "inspect":
            nonce = json.loads(docker.ownerfile.read_text())["nonce"]
            return subprocess.CompletedProcess(args, 0, "d" * 64 + " /" + scheduler.CONTAINER + " managed " + nonce, "")
        return subprocess.CompletedProcess(args, 0, "", "")

    docker.call = call
    docker.run("sha256:" + "a" * 64, probe=probe, keys=["adapter.nsga2"], execute=not probe)
    create = next(args for args in calls if args[0] == "create")
    mounts = [create[i + 1] for i, value in enumerate(create) if value == "--mount"]
    assert len(mounts) == (1 if probe else 2) and all(m.endswith(",readonly") for m in mounts)
    assert any("catalog-reader.json" in m for m in mounts) == probe
    assert any("catalog-writer.json" in m for m in mounts) != probe
    assert any("deepseek.json" in m for m in mounts) != probe
    assert create[create.index("--user") + 1] == ("10001:10001" if probe else "0:0")
    assert "--read-only" in create and "--log-driver" in create
    assert not any("socket" in m for m in mounts)
    assert not any("never-print-this-key" in value for value in create)


def test_private_driver_errors_are_never_reported(scheduler, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(scheduler.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setitem(sys.modules, "fcntl", types.SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda *args: None))
    monkeypatch.setattr(scheduler, "once", lambda root, **kw: (_ for _ in ()).throw(ValueError("sensitive provider payload")))
    assert scheduler.main(["--root", str(tmp_path), "--once", "--execute"]) == 1
    output = capsys.readouterr().out
    assert "sensitive" not in output and '"error": "ValueError"' in output
    state = scheduler.read_state(tmp_path / "automation/state/state.json")
    assert state["last_status"]["error"] == "ValueError"


def test_corrupt_budget_fails_closed(scheduler, tmp_path):
    state = new_state(scheduler)
    state["reserved"] = -1
    file = tmp_path / "state.json"
    file.write_text(json.dumps(state))
    with pytest.raises(scheduler.SchedulerError, match="state_invalid"):
        scheduler.read_state(file)


def test_release_path_outside_releases_is_rejected(scheduler, tmp_path):
    release = tmp_path / "releases/one"
    release.mkdir(parents=True)
    # image() resolves a directory too; this avoids requiring Windows symlink privileges.
    (tmp_path / "current").mkdir()
    docker = scheduler.Docker(tmp_path)
    with pytest.raises(scheduler.SchedulerError, match="release_path_invalid"):
        docker.image()


def test_release_image_mismatch_blocks_even_discovery(scheduler, tmp_path, monkeypatch):
    release = tmp_path / "releases/one"
    release.mkdir(parents=True)
    (release / "service.json").write_text(json.dumps({"image_id": "sha256:" + "a" * 64}))
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        return release if path == tmp_path / "current" else original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    docker = scheduler.Docker(tmp_path)
    docker.call = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, "sha256:" + "b" * 64, "")
    with pytest.raises(scheduler.SchedulerError, match="release_not_active"):
        docker.image()


@pytest.mark.parametrize("matches", [True, False])
def test_reader_only_release_is_bound_to_exact_active_source(scheduler, tmp_path, monkeypatch, matches):
    release = tmp_path / "releases/reader-only"
    release.mkdir(parents=True)
    digest = "a" * 64
    (release / "release-manifest.json").write_text(json.dumps({"content_sha256": digest}))
    original = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda path, *args, **kwargs:
                        release if path == tmp_path / "current" else original(path, *args, **kwargs))
    docker = scheduler.Docker(tmp_path)
    calls = []
    def call(args, **kwargs):
        calls.append(args)
        text = "sha256:" + "b" * 64 if args[0] == "inspect" else digest if matches else "c" * 64
        return subprocess.CompletedProcess(args, 0, text, "")
    docker.call = call
    if matches:
        assert docker.image() == ("sha256:" + "b" * 64, "reader-only")
    else:
        with pytest.raises(scheduler.SchedulerError, match="release_not_active"):
            docker.image()
    assert calls[1][:4] == ["exec", "nsgablack-catalog", "python", "-c"]
    assert all("create" not in args for args in calls)


@pytest.mark.parametrize("matching_nonce", [True, False])
def test_create_timeout_before_cidfile_uses_nonce_to_recover_exact_id(scheduler, tmp_path, matching_nonce):
    (tmp_path / "automation/state").mkdir(parents=True)
    docker = scheduler.Docker(tmp_path)
    calls, cid = [], "f" * 64

    def call(args, **kwargs):
        calls.append(args)
        if args[0] == "create":
            assert docker.ownerfile.exists() and not docker.cidfile.exists()
            raise scheduler.SchedulerError("docker_timeout")
        if args[0] == "inspect":
            assert args[-1] == scheduler.CONTAINER
            nonce = json.loads(docker.ownerfile.read_text())["nonce"] if matching_nonce else "0" * 32
            return subprocess.CompletedProcess(args, 0, cid + " /" + scheduler.CONTAINER + " managed " + nonce, "")
        return subprocess.CompletedProcess(args, 0, "", "")

    docker.call = call
    with pytest.raises(scheduler.SchedulerError, match="docker_timeout" if matching_nonce else "worker_identity_conflict"):
        docker.run("sha256:" + "a" * 64, probe=True)
    assert [a for a in calls if a[0] == "rm"] == ([["rm", "--force", cid]] if matching_nonce else [])


@pytest.mark.parametrize("confirmed_absent", [True, False])
def test_daemon_failure_preserves_intent_until_absence_confirmed(scheduler, tmp_path, confirmed_absent):
    docker = scheduler.Docker(tmp_path)
    docker.ownerfile.parent.mkdir(parents=True)
    scheduler.atomic_json(docker.ownerfile, {"nonce": "a" * 32})
    docker.cidfile.write_text("b" * 64)
    calls = []

    def call(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0 if args[0] == "ps" and confirmed_absent else 1, "", "private daemon diagnostic")

    docker.call = call
    if confirmed_absent:
        docker.cleanup()
        assert not docker.ownerfile.exists() and not docker.cidfile.exists()
    else:
        with pytest.raises(scheduler.SchedulerError, match="worker_inspect_failed"):
            docker.cleanup()
        assert docker.ownerfile.exists() and docker.cidfile.exists()
    assert not any(args[0] == "rm" for args in calls)


class MemoryDocker:
    """No Docker daemon or paid provider is used by scheduler behavior tests."""

    def __init__(self, count=45, *, failures=(), visible=True):
        self.value = packet(count)
        self.failures, self.visible = set(failures), visible
        self.batches, self.probes = [], 0

    def image(self):
        return "sha256:" + "a" * 64, "verified-release"

    def run(self, image, *, probe, keys=None, execute=False):
        if probe:
            self.probes += 1
            return json.loads(json.dumps(self.value))
        self.batches.append(tuple(keys))
        for entry in self.value["entries"]:
            if self.visible and entry["key"] in keys and entry["key"] not in self.failures:
                entry["cached"] = True
        return {"results": [{"entry_key": key, **({"error": "note_evidence_validation_failed"}
                            if key in self.failures else {})} for key in keys]}


def prepare_state(scheduler, tmp_path, *, reserved=0):
    directory = tmp_path / "automation/state"
    directory.mkdir(parents=True)
    state = new_state(scheduler)
    state.update(budget_day="1970-01-02", reserved=reserved)
    scheduler.atomic_json(directory / "state.json", state)
    return state


def test_explicit_drain_freezes_bounded_plan_and_preserves_daily_usage(scheduler, tmp_path):
    prepare_state(scheduler, tmp_path, reserved=80)
    docker = MemoryDocker(45)
    result = scheduler.drain(tmp_path, execute=True, max_items=25, now=100000, docker=docker)
    assert list(map(len, docker.batches)) == [20, 5]
    assert result["generated"] == result["current"] == result["selected"] == 25
    assert result["remaining"] == 20 and result["status"] == "daily_limit"
    assert result["next_eligible_at"] == 172800
    state = scheduler.read_state(tmp_path / "automation/state/state.json")
    assert state["reserved"] == 105 and state["catchup_reserved"] == 25
    assert state["last_drain"]["reserved"] == state["last_drain"]["plan_count"] == 25
    assert scheduler.select_batch(state, docker.value, 100001) == []  # No negative slicing/refilled allowance.
    assert docker.probes == 3


def test_drain_completes_only_after_exact_store_visibility(scheduler, tmp_path):
    prepare_state(scheduler, tmp_path, reserved=100)
    docker = MemoryDocker(23)
    result = scheduler.drain(tmp_path, execute=True, max_items=557, now=100000, docker=docker)
    assert result["current"] == 23 and result["status"] == "complete"
    assert result["next_eligible_at"] is None and result["reserved_today"] == 123
    assert sum(len(batch) for batch in docker.batches) == len(set(key for batch in docker.batches for key in batch))


@pytest.mark.parametrize("draining", [False, True])
def test_success_report_is_not_substituted_for_store_probe(scheduler, tmp_path, draining):
    prepare_state(scheduler, tmp_path)
    docker = MemoryDocker(3, visible=False)
    result = (scheduler.drain(tmp_path, execute=True, max_items=3, now=100000, docker=docker) if draining else
              scheduler.once(tmp_path, execute=True, now=100000, docker=docker))
    assert result["generated"] == 3 and result["current"] == 0
    assert result["status"] != "complete" and len(docker.batches) == 1


def test_drain_does_not_retry_failed_identity_or_starve_following_batch(scheduler, tmp_path):
    prepare_state(scheduler, tmp_path)
    docker = MemoryDocker(45, failures=("adapter.example_000", "adapter.example_021"))
    result = scheduler.drain(tmp_path, execute=True, max_items=45, now=100000, docker=docker)
    assert list(map(len, docker.batches)) == [20, 20, 5]
    assert result["failed"] == 2 and result["current"] == 43 and result["status"] == "backoff"
    assert sum(key == "adapter.example_000" for batch in docker.batches for key in batch) == 1
    state = scheduler.read_state(tmp_path / "automation/state/state.json")
    assert len(state["failures"]) == 2 and state["reserved"] == 45


def test_drain_respects_existing_circuit_and_publishes_reason(scheduler, tmp_path):
    state = prepare_state(scheduler, tmp_path)
    state["circuit_until"] = 186400
    scheduler.atomic_json(tmp_path / "automation/state/state.json", state)
    docker = MemoryDocker(3)
    result = scheduler.drain(tmp_path, execute=True, max_items=3, now=100000, docker=docker)
    assert not docker.batches and result["reserved_today"] == 0
    assert result["status"] == "circuit_open" and result["next_eligible_at"] == 186400


def test_drain_daily_extra_allowance_has_hard_bound(scheduler, tmp_path):
    state = prepare_state(scheduler, tmp_path, reserved=650)
    state["catchup_reserved"] = 550
    scheduler.atomic_json(tmp_path / "automation/state/state.json", state)
    docker = MemoryDocker(20)
    result = scheduler.drain(tmp_path, execute=True, max_items=20, now=100000, docker=docker)
    assert list(map(len, docker.batches)) == [7]
    assert result["reserved_today"] == scheduler.DAILY_LIMIT + scheduler.MAX_DRAIN_ITEMS
    state = scheduler.read_state(tmp_path / "automation/state/state.json")
    assert state["catchup_reserved"] == scheduler.MAX_DRAIN_ITEMS
    assert scheduler.select_batch(state, docker.value, 100001, drain=True) == []


def test_drain_refuses_source_changes_between_batches(scheduler, tmp_path):
    prepare_state(scheduler, tmp_path)

    class ChangingDocker(MemoryDocker):
        def run(self, image, *, probe, keys=None, execute=False):
            value = super().run(image, probe=probe, keys=keys, execute=execute)
            if probe and self.probes > 1:
                value = packet(46)
            return value

    docker = ChangingDocker()
    with pytest.raises(scheduler.SchedulerError, match="release_changed"):
        scheduler.drain(tmp_path, execute=True, max_items=45, now=100000, docker=docker)
    assert len(docker.batches) == 1
    state = scheduler.read_state(tmp_path / "automation/state/state.json")
    assert state["reserved"] == state["catchup_reserved"] == 20


def test_public_progress_is_fixed_allowlist_with_atomic_readable_file(scheduler, tmp_path):
    prepare_state(scheduler, tmp_path)
    scheduler.once(tmp_path, execute=True, now=100000, docker=MemoryDocker(3))
    path = tmp_path / "automation/progress/progress.json"
    value = json.loads(path.read_text())
    assert set(value) == {"schema", "release", "image_id", "checked_at", "source_index_sha256", "prompt_version", "total", "current",
                          "selected", "generated", "failed", "daily_limit", "reserved_today", "status",
                          "next_eligible_at", "circuit_until", "remaining"}
    assert value["schema"] == scheduler.PROGRESS_SCHEMA and value["status"] == "complete"
    safe = scheduler.public_progress({**value, "error": "never-print-this-key", "model": "secret-model",
                                      "failures": {"entry_key": "secret"}, "api_key": "private"})
    assert safe == value
    assert "never-print-this-key" not in path.read_text()
    assert list(path.parent.iterdir()) == [path]
    if sys.platform != "win32":
        assert path.stat().st_mode & 0o777 == 0o644
        assert path.parent.stat().st_mode & 0o777 == 0o755


def test_source_index_digest_is_independent_of_cache_and_checked(scheduler):
    probe = packet(3)
    assert scheduler.validate_probe(probe) is probe
    probe["entries"][0]["cached"] = True
    assert scheduler.validate_probe(probe) is probe
    probe["entries"][0]["digest"] = "f" * 64
    with pytest.raises(scheduler.SchedulerError, match="probe_source_index_invalid"):
        scheduler.validate_probe(probe)


@pytest.mark.parametrize("argv", [["--drain"], ["--drain", "--max-items", "0"],
                                 ["--drain", "--max-items", "558"], ["--once", "--max-items", "20"]])
def test_drain_requires_explicit_bounded_cli_allowance(scheduler, argv):
    with pytest.raises(SystemExit) as exc:
        scheduler.main(argv)
    assert exc.value.code == 2
