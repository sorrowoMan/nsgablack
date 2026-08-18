"""Smoke tests for PoolScheduler — L0 shared thread pool."""

from blackbase.resources import PoolScheduler


def test_pool_scheduler_basic():
    pool = PoolScheduler(total_threads=4)
    assert pool.total_threads == 4
    assert pool.available() == 4
    pool.close()


def test_pool_scheduler_submit_and_wait():
    pool = PoolScheduler(total_threads=4)
    results = []

    def worker(n):
        results.append(n)
        return n * 2

    fut = pool.submit(worker, 42, resource_permits=2, task_id="task_a")
    val = fut.result(timeout=5)
    assert val == 84
    assert fut.task_id == "task_a"
    assert 42 in results

    report = pool.report()
    assert report["tasks_completed"] == 1
    pool.close()


def test_pool_scheduler_as_executor():
    pool = PoolScheduler(total_threads=4)
    with pool.as_executor(2) as ex:
        out = list(ex.map(lambda x: x * 3, [1, 2, 3]))
    assert out == [3, 6, 9]
    pool.close()


def test_pool_scheduler_threads_released_after_map():
    pool = PoolScheduler(total_threads=4)
    assert pool.available() == 4
    with pool.as_executor(3) as ex:
        assert pool.available() <= 1  # 3 threads acquired
        list(ex.map(lambda x: x, range(5)))
    assert pool.available() == 4  # all released
    pool.close()


def test_pool_scheduler_import_from_shared_public_api():
    from blackbase.resources import PoolScheduler as SharedPoolScheduler

    assert SharedPoolScheduler is PoolScheduler
