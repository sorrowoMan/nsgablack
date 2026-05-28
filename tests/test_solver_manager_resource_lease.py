from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from nsgablack.core import (
    InMemoryLeaseStore,
    InMemoryMessageQueue,
    RegimeSpec,
    ResourceAllocator,
    ResourceBudgetError,
    ResourceLease,
    ResourceOffer,
    ResourcePolicy,
    ResourceRequest,
    SQLiteLeaseStore,
    SQLiteMessageQueue,
    SolverManager,
)


class _DummySolver:
    def __init__(self, name: str, request: ResourceRequest) -> None:
        self.name = str(name)
        self.resource_request = request

    def run(self, *, return_dict: bool = True):
        return {"ok": True, "name": self.name} if return_dict else None


class TestSolverManagerResourceLease(unittest.TestCase):
    def test_allocator_assigns_concrete_gpu_leases_from_abstract_requests(self) -> None:
        allocator = ResourceAllocator(
            offer=ResourceOffer(threads=4, backend="local", device_tokens=("cuda:0", "cuda:1")),
            policy=ResourcePolicy(mode="strict", gpu_sharing="exclusive"),
        )
        request = ResourceRequest(threads=1, backend="local", gpus=1, label="inner")

        first = allocator.acquire(request, owner_id="trial_0", scope="outer_eval")
        second = allocator.acquire(request, owner_id="trial_1", scope="outer_eval")
        context = first.resource_context(compute_backend="torch", device="auto", namespace="trial_0")

        self.assertEqual(tuple(first.device_tokens), ("cuda:0",))
        self.assertEqual(tuple(second.device_tokens), ("cuda:1",))
        self.assertEqual(str(context["device"]), "cuda:0")
        self.assertEqual(str(context["lease"]["owner_id"]), "trial_0")

        with self.assertRaises(ResourceBudgetError):
            allocator.acquire(request, owner_id="trial_2", scope="outer_eval")

    def test_solver_manager_rejects_parallel_concrete_gpu_conflict(self) -> None:
        request = ResourceRequest(threads=1, backend="local", device_tokens=("cuda:0",), label="inner")
        manager = SolverManager(
            regimes=(
                RegimeSpec("a", lambda: _DummySolver("a", request)),
                RegimeSpec("b", lambda: _DummySolver("b", request)),
            ),
            offer=ResourceOffer(threads=4, backend="local", device_tokens=("cuda:0",)),
            policy=ResourcePolicy(mode="strict", gpu_sharing="exclusive"),
            mode="parallel",
        )

        with self.assertRaises(ResourceBudgetError):
            manager.run()

    def test_solver_manager_allows_declared_shared_gpu_policy(self) -> None:
        request = ResourceRequest(threads=1, backend="local", device_tokens=("cuda:0",), label="inner")
        manager = SolverManager(
            regimes=(
                RegimeSpec("a", lambda: _DummySolver("a", request)),
                RegimeSpec("b", lambda: _DummySolver("b", request)),
            ),
            offer=ResourceOffer(threads=4, backend="local", device_tokens=("cuda:0",)),
            policy=ResourcePolicy(mode="strict", gpu_sharing="shared", max_jobs_per_gpu=2),
            mode="parallel",
        )

        result = manager.run()
        self.assertEqual(len(tuple(result["regimes"])), 2)

    def test_sqlite_lease_store_prevents_cross_allocator_gpu_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "leases.sqlite3")
            request = ResourceRequest(threads=1, backend="local", gpus=1, label="inner")
            offer = ResourceOffer(threads=4, backend="local", device_tokens=("cuda:0",))

            first_allocator = ResourceAllocator(
                offer=offer,
                policy=ResourcePolicy(mode="strict", gpu_sharing="exclusive"),
                lease_store=SQLiteLeaseStore(db_path),
            )
            second_allocator = ResourceAllocator(
                offer=offer,
                policy=ResourcePolicy(mode="strict", gpu_sharing="exclusive"),
                lease_store=SQLiteLeaseStore(db_path),
            )

            first = first_allocator.acquire(request, owner_id="trial_a", scope="outer_eval")
            self.assertEqual(tuple(first.device_tokens), ("cuda:0",))
            with self.assertRaises(ResourceBudgetError):
                second_allocator.acquire(request, owner_id="trial_b", scope="outer_eval")

            second_allocator.release(first)
            second = second_allocator.acquire(request, owner_id="trial_b", scope="outer_eval")
            self.assertEqual(tuple(second.device_tokens), ("cuda:0",))

    def test_in_memory_message_queue_tracks_lease_events_without_being_truth_source(self) -> None:
        queue = InMemoryMessageQueue()
        allocator = ResourceAllocator(
            offer=ResourceOffer(threads=4, backend="local", device_tokens=("cuda:0",)),
            policy=ResourcePolicy(mode="strict", gpu_sharing="exclusive"),
            message_queue=queue,
        )
        lease = allocator.acquire(ResourceRequest(threads=1, backend="local", gpus=1), owner_id="trial_a")

        events = queue.peek()
        self.assertEqual([event.topic for event in events], ["resource.lease.acquired"])
        self.assertEqual(events[0].payload["lease"]["lease_id"], lease.lease_id)
        self.assertTrue(queue.ack(events[0].event_id))
        self.assertEqual(queue.peek(), tuple())
        self.assertEqual(len(allocator.active_leases()), 1)

        allocator.release(lease)
        released_events = queue.peek(topic="resource.lease.released")
        self.assertEqual(len(released_events), 1)
        self.assertEqual(released_events[0].payload["lease_id"], lease.lease_id)

    def test_sqlite_message_queue_publishes_cross_process_lease_conflict_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "leases.sqlite3")
            queue = SQLiteMessageQueue(db_path)
            request = ResourceRequest(threads=1, backend="local", gpus=1, label="inner")
            offer = ResourceOffer(threads=4, backend="local", device_tokens=("cuda:0",))

            first_allocator = ResourceAllocator(
                offer=offer,
                policy=ResourcePolicy(mode="strict", gpu_sharing="exclusive"),
                lease_store=SQLiteLeaseStore(db_path, message_queue=queue),
            )
            second_allocator = ResourceAllocator(
                offer=offer,
                policy=ResourcePolicy(mode="strict", gpu_sharing="exclusive"),
                lease_store=SQLiteLeaseStore(db_path, message_queue=queue),
            )

            first = first_allocator.acquire(request, owner_id="trial_a", scope="outer_eval")
            with self.assertRaises(ResourceBudgetError):
                second_allocator.acquire(request, owner_id="trial_b", scope="outer_eval")

            topics = [event.topic for event in queue.peek(limit=10)]
            self.assertEqual(topics, ["resource.lease.acquired", "resource.lease.conflict"])
            for event in queue.peek(limit=10):
                queue.ack(event.event_id)
            self.assertEqual(queue.peek(), tuple())
            self.assertEqual(len(SQLiteLeaseStore(db_path).active_leases()), 1)

            first_allocator.release(first)
            released_events = queue.peek(topic="resource.lease.released")
            self.assertEqual(len(released_events), 1)
            self.assertEqual(released_events[0].payload["lease_id"], first.lease_id)

    def test_allocator_heartbeat_refreshes_active_lease(self) -> None:
        queue = InMemoryMessageQueue()
        allocator = ResourceAllocator(
            offer=ResourceOffer(threads=4, backend="local", device_tokens=("cuda:0",)),
            policy=ResourcePolicy(
                mode="strict",
                gpu_sharing="exclusive",
                lease_ttl_seconds=60.0,
                heartbeat_interval_seconds=10.0,
            ),
            message_queue=queue,
        )

        lease = allocator.acquire(ResourceRequest(threads=1, backend="local", gpus=1), owner_id="trial_a")
        self.assertTrue(allocator.heartbeat(lease))

        active = allocator.active_leases()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].lease_id, lease.lease_id)
        self.assertEqual(active[0].ttl_seconds, 60.0)
        self.assertEqual(active[0].heartbeat_interval_seconds, 10.0)
        self.assertGreaterEqual(active[0].last_heartbeat_at, lease.last_heartbeat_at)
        topics = [event.topic for event in queue.peek(limit=10)]
        self.assertEqual(topics, ["resource.lease.acquired", "resource.lease.heartbeat"])

    def test_in_memory_lease_store_prunes_stale_lease(self) -> None:
        queue = InMemoryMessageQueue()
        store = InMemoryLeaseStore(message_queue=queue)
        stale = ResourceLease(
            lease_id="stale_lease",
            owner_id="dead_process",
            scope="outer_eval",
            threads=1,
            backend="local",
            device_tokens=("cuda:0",),
            ttl_seconds=0.1,
            acquired_at=1.0,
            last_heartbeat_at=1.0,
        )

        store.acquire(stale)
        self.assertEqual(store.active_leases(), tuple())
        topics = [event.topic for event in queue.peek(limit=10)]
        self.assertEqual(topics, ["resource.lease.acquired", "resource.lease.expired"])

    def test_sqlite_lease_store_prunes_stale_lease_and_releases_gpu(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "leases.sqlite3")
            queue = SQLiteMessageQueue(db_path)
            store = SQLiteLeaseStore(db_path, message_queue=queue)
            stale = ResourceLease(
                lease_id="stale_lease",
                owner_id="dead_process",
                scope="outer_eval",
                threads=1,
                backend="local",
                device_tokens=("cuda:0",),
                ttl_seconds=0.1,
                acquired_at=1.0,
                last_heartbeat_at=1.0,
            )

            store.acquire(stale)
            self.assertEqual(store.active_leases(), tuple())

            allocator = ResourceAllocator(
                offer=ResourceOffer(threads=4, backend="local", device_tokens=("cuda:0",)),
                policy=ResourcePolicy(mode="strict", gpu_sharing="exclusive"),
                lease_store=store,
            )
            fresh = allocator.acquire(ResourceRequest(threads=1, backend="local", gpus=1), owner_id="trial_b")

            self.assertEqual(tuple(fresh.device_tokens), ("cuda:0",))
            topics = [event.topic for event in queue.peek(limit=10)]
            self.assertEqual(
                topics,
                ["resource.lease.acquired", "resource.lease.expired", "resource.lease.acquired"],
            )


if __name__ == "__main__":
    unittest.main()
