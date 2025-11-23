"""ML + 历史评估联合初始化示例模块

目标：将机器学习模型作为候选进入 GA 之前的过滤器，并与历史评估模块（避免局部最优）共同作用，
以减少评估资源被劣质解占用的情况。

本模块提供：
- `train_bad_solution_classifier`：从采样数据训练一个二分类模型（示例使用 RandomForest）。
- `ClassifierHistoryAwareInitializer`：继承自 `DiversityAwareInitializerBlackBox`，在多样性选择时
  同时使用分类器预测和历史相似性判据来拒绝候选。
- `main()`：演示流水线（采样→训练→注入初始化器→短跑优化），并可保存与加载模型。

使用：
    python -m nsgablack.ml_guided_ga_example
"""

from __future__ import annotations

import os
import joblib
import argparse
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from typing import Tuple, Optional, Any, Dict

from .problems import SphereBlackBox
from .diversity import DiversityAwareInitializerBlackBox
from .solver import BlackBoxSolverNSGAII
from .exmaple import prepare_pca_reduced_problem
from .ml_models import ModelManager


def sample_candidates(problem, n_candidates: int = 200, method: str = 'random', bounds=None) -> Tuple[np.ndarray, np.ndarray]:
    """在问题的原边界内采样候选解并返回 (X, y)；y 为用于划分好/坏的标量评分。"""
    dim = problem.dimension
    if bounds is None:
        bounds = [problem.bounds[f'x{i}'] for i in range(dim)]
    if method == 'lhs':
        from scipy.stats import qmc
        sampler = qmc.LatinHypercube(d=dim)
        U = sampler.random(n_candidates)
        lows = np.array([b[0] for b in bounds])
        highs = np.array([b[1] for b in bounds])
        X = (lows + U * (highs - lows))
    else:
        X = np.zeros((n_candidates, dim))
        for i, b in enumerate(bounds):
            X[:, i] = np.random.uniform(b[0], b[1], n_candidates)
    # 评估目标（若多目标，取第一个目标作为评分）
    y = []
    for xi in X:
        val = problem.evaluate(xi)
        if hasattr(val, '__len__'):
            y.append(float(np.asarray(val).flatten()[0]))
        else:
            y.append(float(val))
    return X, np.array(y, dtype=float)


def train_bad_solution_classifier(X: np.ndarray, y: np.ndarray, bad_frac: float = 0.3,
                                  random_state: int = 42) -> Tuple[Any, StandardScaler]:
    """训练一个二分类器来识别劣解（标签 1），返回 (clf_pipeline, scaler)

    标注策略：将评分最差的 `bad_frac` 百分比样本标注为劣解。
    返回的 clf 期望能够被包装为拥有 `predict` 与 `predict_proba` 的对象；
    示例中我们返回一个包含 scaler 的包装器。
    """
    n = len(X)
    k = max(1, int(n * bad_frac))
    order = np.argsort(y)[::-1]
    bad_idx = order[:k]
    labels = np.zeros(n, dtype=int)
    labels[bad_idx] = 1

    X_train, X_val, y_train, y_val = train_test_split(X, labels, test_size=0.2, random_state=random_state)
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s = scaler.transform(X_val)

    clf = RandomForestClassifier(n_estimators=200, random_state=random_state)
    clf.fit(X_train_s, y_train)

    train_acc = clf.score(X_train_s, y_train)
    val_acc = clf.score(X_val_s, y_val)
    print(f"Classifier train acc: {train_acc:.3f}, val acc: {val_acc:.3f}")

    class PipelineWrapper:
        def __init__(self, clf, scaler):
            self.clf = clf
            self.scaler = scaler
            self.classes_ = clf.classes_

        def predict(self, X_in):
            return self.clf.predict(self.scaler.transform(X_in))

        def predict_proba(self, X_in):
            return self.clf.predict_proba(self.scaler.transform(X_in))

    return PipelineWrapper(clf, scaler), scaler


class ClassifierHistoryAwareInitializer(DiversityAwareInitializerBlackBox):
    """结合分类器与历史评估的初始化器。

    行为：在多样性候选中，同步应用分类器（预测为“劣解”则跳过）与历史相似性判据（与历史过于相似以一定概率跳过），
    最终补足人工填充保证达到 `pop_size`。

    参数：
    - clf: 已训练并包含 `predict`/`predict_proba` 的对象（可为包装器，负责 scaler）。
    - bad_label: 表示劣解的标签（int）。
    - bad_prob_thresh: 若预测劣解概率 >= 阈值，则拒绝候选。
    """

    def __init__(self, problem, clf: Optional[Any] = None, bad_label: int = 1, bad_prob_thresh: float = 0.6, **kwargs):
        super().__init__(problem, **kwargs)
        self.clf = clf
        self.bad_label = bad_label
        self.bad_prob_thresh = float(bad_prob_thresh)

    def is_predicted_bad(self, candidate: np.ndarray) -> bool:
        if self.clf is None:
            return False
        try:
            X = np.atleast_2d(np.asarray(candidate, dtype=float))
            if hasattr(self.clf, 'predict_proba'):
                proba = self.clf.predict_proba(X)
                classes = list(self.clf.classes_)
                if self.bad_label in classes:
                    bad_idx = classes.index(self.bad_label)
                    p_bad = float(proba[0, bad_idx])
                else:
                    p_bad = float(proba[0, -1])
            else:
                pred = int(self.clf.predict(X)[0])
                p_bad = 1.0 if pred == self.bad_label else 0.0
            return p_bad >= self.bad_prob_thresh
        except Exception:
            return False

    def initialize_diverse_population(self, pop_size: int = 100, candidate_size: int = 1000, sampling_method: str = 'lhs'):
        # 复用父类的采样与评估流程，但在选择阶段加入 classifier 筛选
        bounds = self.problem.bounds
        n_dim = self.problem.dimension
        bounds_array = np.array(list(bounds.values()))
        if sampling_method == 'lhs':
            from scipy.stats import qmc
            sampler = qmc.LatinHypercube(d=n_dim)
            U = sampler.random(n=candidate_size)
            candidates = qmc.scale(U, bounds_array[:, 0], bounds_array[:, 1])
        else:
            candidates = np.zeros((candidate_size, n_dim))
            for i, var in enumerate(self.problem.variables):
                low, high = bounds[var]
                candidates[:, i] = np.random.uniform(low, high, candidate_size)

        fitness_values = []
        for i, cand in enumerate(candidates):
            fitness_values.append(self.problem.evaluate(cand))
        fitness_values = np.array(fitness_values)

        if self.problem.is_multiobjective():
            sorted_indices = self.sort_candidates_multiobjective(candidates, fitness_values)
        else:
            sorted_indices = np.argsort(fitness_values)

        selected_population = []
        selected_fitness = []
        for idx in sorted_indices:
            if len(selected_population) >= pop_size:
                break
            cand = candidates[idx]
            fit = fitness_values[idx]
            # classifier 过滤
            if self.is_predicted_bad(cand):
                continue
            # 历史相似性判定
            if self.is_similar_to_history(cand):
                if np.random.random() < self.rejection_prob:
                    continue
            selected_population.append(cand)
            selected_fitness.append(fit)

        # 若不足，则回退补足（保证可用）
        if len(selected_population) < pop_size:
            needed = pop_size - len(selected_population)
            for idx in sorted_indices:
                if needed <= 0:
                    break
                cand = candidates[idx]
                if any((cand == s).all() for s in selected_population):
                    continue
                selected_population.append(cand)
                selected_fitness.append(fitness_values[idx])
                needed -= 1

        # 写入历史
        for s, f in zip(selected_population, selected_fitness):
            self.add_to_history(s, f)
        return np.array(selected_population), np.array(selected_fitness)


class ClassifierHistoryAwareReducedInitializer(DiversityAwareInitializerBlackBox):
    """适配器：在降维（reduced）空间使用基于原空间的 classifier + history 判断。

    - base_initializer: 针对原始问题构建的 ClassifierHistoryAwareInitializer（负责历史存储和 classifier）
    - expand_fn: 将降维向量映射回原始空间的函数（reduced -> full）

    适配器在 reduced 空间采样，但所有的 classifier 与历史相似性判断均基于映射回的原空间向量。
    最终返回的 population 与 fitness 保持为 reduced 空间的表示（以供 solver 使用）。
    """

    def __init__(self, reduced_problem, base_initializer: ClassifierHistoryAwareInitializer, expand_fn, **kwargs):
        # reduced_problem 用于采样 reduced-space 的边界
        super().__init__(reduced_problem, **kwargs)
        self.base_initializer = base_initializer
        self.expand_fn = expand_fn

    def is_predicted_bad_in_full(self, reduced_candidate: np.ndarray) -> bool:
        full = self.expand_fn(reduced_candidate)
        return self.base_initializer.is_predicted_bad(full)

    def is_similar_to_history_in_full(self, reduced_candidate: np.ndarray) -> bool:
        full = self.expand_fn(reduced_candidate)
        return self.base_initializer.is_similar_to_history(full)

    def add_to_history_full(self, reduced_candidate: np.ndarray, fitness):
        full = self.expand_fn(reduced_candidate)
        # 将 full 及其 fitness 写入 base_initializer 的历史
        self.base_initializer.add_to_history(full, fitness)

    def initialize_diverse_population(self, pop_size: int = 100, candidate_size: int = 1000, sampling_method: str = 'lhs'):
        # 在 reduced 空间采样并评估，再用 base_initializer 在 full 空间进行 classifier/history 判断
        bounds = self.problem.bounds
        n_dim = self.problem.dimension
        bounds_array = np.array(list(bounds.values()))
        if sampling_method == 'lhs':
            from scipy.stats import qmc
            sampler = qmc.LatinHypercube(d=n_dim)
            U = sampler.random(n=candidate_size)
            candidates = qmc.scale(U, bounds_array[:, 0], bounds_array[:, 1])
        else:
            candidates = np.zeros((candidate_size, n_dim))
            for i, var in enumerate(self.problem.variables):
                low, high = bounds[var]
                candidates[:, i] = np.random.uniform(low, high, candidate_size)

        # 评估每个 reduced 候选：映射回 full 并评估目标
        fitness_values = []
        for cand in candidates:
            full = self.expand_fn(cand)
            fitness_values.append(self.base_initializer.problem.evaluate(full))
        fitness_values = np.array(fitness_values)

        if self.problem.is_multiobjective():
            sorted_indices = self.sort_candidates_multiobjective(candidates, fitness_values)
        else:
            sorted_indices = np.argsort(fitness_values)

        selected_population = []
        selected_fitness = []
        for idx in sorted_indices:
            if len(selected_population) >= pop_size:
                break
            cand = candidates[idx]
            fit = fitness_values[idx]
            # classifier 判断基于 full
            if self.is_predicted_bad_in_full(cand):
                continue
            if self.is_similar_to_history_in_full(cand):
                if np.random.random() < self.rejection_prob:
                    continue
            selected_population.append(cand)
            selected_fitness.append(fit)

        if len(selected_population) < pop_size:
            needed = pop_size - len(selected_population)
            for idx in sorted_indices:
                if needed <= 0:
                    break
                cand = candidates[idx]
                if any((cand == s).all() for s in selected_population):
                    continue
                selected_population.append(cand)
                selected_fitness.append(fitness_values[idx])
                needed -= 1

        # 将 full 解加入 base_initializer 的历史（供未来判断使用）
        for cand, fit in zip(selected_population, selected_fitness):
            self.add_to_history_full(cand, fit)

        return np.array(selected_population), np.array(selected_fitness)


def main(argv: Optional[list] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description='ML-guided GA example (Classifier + History)')
    parser.add_argument('--pop-size', type=int, default=40)
    parser.add_argument('--gens', type=int, default=30)
    parser.add_argument('--samples', type=int, default=600)
    parser.add_argument('--bad-frac', type=float, default=0.25)
    parser.add_argument('--model-out', type=str, default=None)
    args = parser.parse_args(argv)

    problem = SphereBlackBox(dimension=8)
    print("采样候选并评估...")
    X, y = sample_candidates(problem, n_candidates=args.samples, method='lhs')

    print(f"训练/更新劣解分类器（标注最差 {args.bad_frac*100:.0f}% 为劣解）...")
    # 使用 ModelManager 管理模型持久化与续训
    mm = ModelManager()
    problem_id = getattr(problem, 'name', 'problem')
    clf_pipe, scaler, model_path = mm.train_or_update(problem_id, problem.dimension, X, y, bad_frac=args.bad_frac)
    if args.model_out:
        # 额外导出一份到用户指定路径
        joblib.dump({'clf': clf_pipe, 'scaler': scaler}, args.model_out)
        print(f"模型已保存到 {args.model_out}")
    print(f"模型持久化路径: {model_path}")

    init = ClassifierHistoryAwareInitializer(problem, clf=clf_pipe, bad_label=1, bad_prob_thresh=0.6,
                                             history_size=2000, similarity_threshold=0.05, rejection_prob=0.6)

    print("准备 PCA 降维问题并运行短轮优化示例...")
    reduced = prepare_pca_reduced_problem(lambda x: problem.evaluate(x),
                                          bounds=[problem.bounds[f'x{i}'] for i in range(problem.dimension)],
                                          n_components=3, initial_samples=400, sampling_method='lhs')

    from .headless import CallableSingleObjectiveProblem
    prob_red = CallableSingleObjectiveProblem(reduced['reduced_objective'], reduced['reduced_bounds'], name='PCA_reduced_demo')
    solver = BlackBoxSolverNSGAII(prob_red)
    solver.pop_size = args.pop_size
    solver.max_generations = args.gens
    solver.enable_diversity_init = True
    # 为降维空间创建适配器初始化器：在 reduced 空间采样，但 classifier/history 在 full 空间判断
    reduced_init = ClassifierHistoryAwareReducedInitializer(prob_red, base_initializer=init,
                                                            expand_fn=reduced['expand_to_full'],
                                                            history_size=init.history_size,
                                                            similarity_threshold=init.similarity_threshold,
                                                            rejection_prob=init.rejection_prob)
    solver.diversity_initializer = reduced_init
    solver.use_history = True
    solver.enable_elite_retention = True

    print("开始优化（短轮，仅演示）...")
    solver.running = True
    solver.initialize_population()
    while solver.running and solver.generation < min(10, solver.max_generations):
        solver.animate(None)

    out: Dict[str, Any] = {}
    if solver.objectives is not None and solver.objectives.ndim == 2:
        best_idx = int(np.argmin(solver.objectives[:, 0]))
        best_x_red = solver.population[best_idx]
        best_f = float(solver.objectives[best_idx, 0])
        full_x = reduced['expand_to_full'](best_x_red)
        print("降维空间最优值:", best_f)
        print("映射回原空间示例最优解:", full_x)
        out['best_f'] = best_f
        out['best_x_full'] = full_x
    else:
        print("未产生有效目标结果")

    return out


if __name__ == '__main__':
    main()
