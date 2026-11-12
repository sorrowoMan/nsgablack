"""普通函数表达变化和选择；没有私有求解循环，也不直接发布候选。"""
from functools import partial

import numpy as np
from nsgablack.adapters import ChangeBatchResult, ChangeResult, Pool


def crossover_then_mutate(request, *, rng, sigma):
    left, right = request.parents
    alpha = rng.uniform(0.2, 0.8, size=left.shape)
    crossed = (alpha * left + (1. - alpha) * right,
               (1. - alpha) * left + alpha * right)
    children = [ChangeResult(child + rng.normal(0., sigma, size=child.shape))
                for child in crossed[:request.max_outputs]]
    return ChangeBatchResult(tuple(children))


def selection_key(pool):
    return np.column_stack((pool.violations > 1e-9, np.maximum(pool.violations, 0.),
                            pool.objectives[:, 0]))


def best(pool, *, count, rng):
    del rng
    return pool.top(min(count, len(pool)), key=selection_key)


def choose_members_and_elite(pool, *, count, elite_count, rng):
    # 主结果决定 GA 成员，副集合只保存其精英引用，两者一次提交。
    members = pool.chosen(partial(best, count=count), rng=rng)
    elite = Pool(parent=members, name="elite")
    elite.inject(members.chosen(partial(best, count=elite_count), rng=rng), replace=True)
    return members


def select_elite(control, context):
    return control.solution_pool.subpool_refs("elite")


def select_refined(control, context):
    return control.adapter.get_pool_task_results(control, "vns")
