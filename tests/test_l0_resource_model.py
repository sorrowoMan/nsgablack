from __future__ import annotations

import pytest

from blackbase.resources import (
    ArtifactAuthority,
    ArtifactPublisher,
    DataRef,
    InMemoryTaskRuntimeBackend,
    InMemoryResourceScheduler,
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


def test_in_memory_task_runtime_roundtrips_claim_and_result():
    backend = InMemoryTaskRuntimeBackend()
    task = TaskEnvelope(
        task_id="task-l0",
        task_type="nested_candidate_eval",
        payload={"run_id": "run-a", "index": 0, "candidate": [1.0]},
        requirement=ResourceRequirement(capabilities=("nested_eval",)),
        namespace="run-a",
    )

    worker = WorkerDescriptor(
        worker_id="worker-a",
        executor_backend="thread",
        capabilities=("nested_eval",),
        offer={"threads": 1, "gpus": 0, "backend": "local"},
    )
    backend.submit(task)
    claimed = backend.claim_task(worker, run_id="run-a", timeout_seconds=1)
    assert claimed is not None
    assert claimed.task.task_id == "task-l0"

    backend.complete_claim(
        claimed,
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
    assert backend.task_transport.get("task-l0").status == "succeeded"
    backend.heartbeat(worker)
    assert backend.task_transport.list_workers()[0].worker_id == "worker-a"


def test_project_artifact_publisher_roundtrips_json(tmp_path):
    publisher = ArtifactPublisher(
        ArtifactAuthority(root=str(tmp_path), namespace="test"),
        project_run_id="project-run",
        case_run_id="case-run",
    )
    ref = publisher.publish("summary", {"ok": True}, kind="report")
    assert ref.backend == "filesystem"
    assert isinstance(ref, DataRef)
    assert ref.kind == "report"
    assert ref.media_type == "application/json"
    assert __import__("json").loads(__import__("pathlib").Path(ref.uri).read_text("utf-8")) == {"ok": True}
