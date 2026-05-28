from __future__ import annotations

import pytest

from nsgablack.core.resources import (
    DataRef,
    FilesystemArtifactBackend,
    InMemoryL0RuntimeBackend,
    InMemoryResourceScheduler,
    ArtifactDataTransportBackend,
    ResourceBudgetError,
    ResourceRequirement,
    TaskEnvelope,
    TaskResult,
    WorkerDescriptor,
    build_local_worker_descriptor,
)


def test_task_envelope_and_result_roundtrip_are_json_compatible():
    task = TaskEnvelope(
        task_id="task_1",
        task_type="nested_candidate_eval",
        payload={"candidate": [1.0, 2.0]},
        requirement=ResourceRequirement(
            threads=2,
            memory_mb=512,
            capabilities=("nested_eval",),
            timeout_seconds=30,
        ),
        executor_backend="thread",
        input_refs=(DataRef(uri="runs/input.parquet", kind="dataset"),),
        namespace="case.a",
    )

    restored = TaskEnvelope.from_dict(task.as_dict())
    assert restored.task_id == "task_1"
    assert restored.requirement.threads == 2
    assert restored.requirement.memory_mb == 512
    assert restored.requirement.capabilities == ("nested_eval",)
    assert restored.input_refs[0].uri == "runs/input.parquet"

    result = TaskResult.success(
        task_id=task.task_id,
        objectives=(-10.0, 2.0),
        violations=(0.0,),
        worker_id="worker-a",
        lease_id="lease-a",
        artifact_refs=(DataRef(uri="runs/out.xlsx", kind="report"),),
    )
    restored_result = TaskResult.from_dict(result.as_dict())
    assert restored_result.ok
    assert restored_result.objectives == (-10.0, 2.0)
    assert restored_result.artifact_refs[0].kind == "report"


def test_worker_descriptor_matches_capabilities_and_resource_limits():
    worker = WorkerDescriptor(
        worker_id="worker-a",
        executor_backend="thread",
        capabilities=("nested_eval", "numpy"),
        offer={"threads": 4, "device_tokens": ("cuda:0",), "memory_mb": 2048},
    )

    assert worker.can_run(
        ResourceRequirement(threads=2, capabilities=("nested_eval",), memory_mb=1024),
        executor_backend="thread",
    )
    assert not worker.can_run(
        ResourceRequirement(threads=5, capabilities=("nested_eval",)),
        executor_backend="thread",
    )
    assert not worker.can_run(
        ResourceRequirement(threads=1, capabilities=("torch",)),
        executor_backend="thread",
    )
    assert not worker.can_run(
        ResourceRequirement(threads=1, capabilities=("nested_eval",), memory_mb=4096),
        executor_backend="thread",
    )


def test_worker_descriptor_matches_gpu_memory_requirements():
    worker = WorkerDescriptor(
        worker_id="gpu-worker",
        executor_backend="thread",
        capabilities=("nested_eval", "gpu", "cuda"),
        offer={
            "threads": 8,
            "device_tokens": ("cuda:0", "cuda:1"),
            "gpu_memory_mb_by_device": {"cuda:0": 8192, "cuda:1": 4096},
        },
    )

    assert worker.can_run(
        ResourceRequirement(gpus=1, device_tokens=("cuda:0",), gpu_memory_mb=4096, capabilities=("gpu",)),
        executor_backend="thread",
    )
    assert not worker.can_run(
        ResourceRequirement(gpus=1, device_tokens=("cuda:1",), gpu_memory_mb=8192, capabilities=("gpu",)),
        executor_backend="thread",
    )
    assert worker.can_run(
        ResourceRequirement(gpus=1, gpu_memory_mb=4096, capabilities=("gpu",)),
        executor_backend="thread",
    )
    assert not worker.can_run(
        ResourceRequirement(gpu_memory_mb=512, capabilities=("gpu",)),
        executor_backend="thread",
    )


def test_build_local_worker_descriptor_reports_cpu_resource_without_cuda_probe():
    worker = build_local_worker_descriptor(
        worker_id="local-test",
        threads=2,
        include_cuda=False,
        max_inflight=3,
    )

    assert worker.worker_id == "local-test"
    assert worker.offer.threads == 2
    assert worker.offer.gpus == 0
    assert "cpu" in set(worker.capabilities)
    assert worker.max_inflight == 3


def test_in_memory_scheduler_acquires_lease_and_releases_worker_slot():
    scheduler = InMemoryResourceScheduler(
        workers=(
            WorkerDescriptor(
                worker_id="worker-a",
                executor_backend="thread",
                capabilities=("nested_eval",),
                offer={"threads": 4, "device_tokens": ("cuda:0",), "memory_mb": 2048},
                max_inflight=1,
            ),
        )
    )
    task = TaskEnvelope(
        task_id="task-lease",
        task_type="nested_candidate_eval",
        requirement=ResourceRequirement(threads=2, capabilities=("nested_eval",), gpus=1),
        executor_backend="thread",
        namespace="case.scheduler",
    )

    scheduled = scheduler.acquire(task)
    assert scheduled.worker.worker_id == "worker-a"
    assert scheduled.lease.threads == 2
    assert tuple(scheduled.lease.device_tokens) == ("cuda:0",)
    assert scheduled.resource_context["metadata"]["task_id"] == "task-lease"
    assert len(scheduler.active_leases()) == 1

    with pytest.raises(ResourceBudgetError):
        scheduler.acquire(task)

    scheduler.release(scheduled)
    assert scheduler.active_leases() == tuple()
    again = scheduler.acquire(task)
    assert again.worker.worker_id == "worker-a"
    scheduler.release(again)


def test_in_memory_l0_runtime_backend_roundtrips_task_result_and_state():
    backend = InMemoryL0RuntimeBackend(namespace="test:l0")
    task = TaskEnvelope(
        task_id="task-l0",
        task_type="nested_candidate_eval",
        payload={"run_id": "run-a", "index": 0, "candidate": [1.0]},
        requirement=ResourceRequirement(capabilities=("nested_eval",)),
        namespace="run-a",
    )

    backend.submit(task)
    claimed = backend.claim(timeout_seconds=1)
    assert claimed is not None
    assert claimed.task_id == "task-l0"
    assert backend.state_backend is not None
    assert backend.state_backend.get_task_state("task-l0")["status"] == "claimed"

    backend.complete(
        TaskResult.success(
            task_id="task-l0",
            objectives=(3.0,),
            violations=(0.0,),
            worker_id="worker-a",
            metrics={"m": 1},
            resource_context={"run_id": "run-a"},
        )
    )
    restored = backend.get_result("run-a", "task-l0")
    assert restored is not None
    assert restored.ok
    assert restored.objectives == (3.0,)
    assert backend.state_backend.get_task_state("task-l0")["status"] == "ok"
    backend.heartbeat("worker-a", {"active": 1})
    assert backend.worker_registry is not None
    assert backend.worker_registry.get_heartbeat("worker-a")["payload"]["active"] == 1


def test_filesystem_artifact_and_transport_backend_roundtrip_json(tmp_path):
    artifact_backend = FilesystemArtifactBackend(base_dir=tmp_path)
    transport = ArtifactDataTransportBackend(artifact_backend)

    ref = artifact_backend.put_json("reports/summary.json", {"ok": True}, kind="report")
    assert ref.backend == "filesystem"
    assert artifact_backend.get_json(ref) == {"ok": True}

    payload_ref = transport.send({"x": [1, 2, 3]}, kind="payload")
    assert isinstance(payload_ref, DataRef)
    assert transport.receive(payload_ref) == {"x": [1, 2, 3]}
