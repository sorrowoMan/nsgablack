"""
测试代理模型系统（Surrogate System）

测试代理模型的训练、预测和管理。
"""
import pytest
import numpy as np
import sys
from pathlib import Path
from typing import Tuple, List

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSurrogateTrainer:
    """测试代理模型训练器。"""

    @pytest.fixture
    def sample_data(self):
        """创建样本训练数据。"""
        np.random.seed(42)
        X = np.random.rand(50, 5)  # 50个样本，5维
        y = np.sum(X**2, axis=1)   # Sphere函数
        return X, y

    def test_trainer_initialization(self, sample_data):
        """测试训练器初始化。"""
        from surrogate.trainer import SurrogateTrainer

        X, y = sample_data
        trainer = SurrogateTrainer(model_type="knn")

        assert trainer is not None
        assert trainer.model_type == "knn"

    @pytest.mark.slow
    def test_train_and_predict(self, sample_data):
        """测试训练和预测。"""
        from surrogate.trainer import SurrogateTrainer

        X, y = sample_data
        trainer = SurrogateTrainer(model_type="knn")

        # 训练
        trainer.train(X, y)

        # 预测
        X_test = np.random.rand(10, 5)
        y_pred = trainer.predict(X_test)

        assert y_pred is not None
        assert len(y_pred) == 10


class TestSurrogateManager:
    """测试代理模型管理器。"""

    def test_manager_initialization(self):
        """测试管理器初始化。"""
        from surrogate.manager import SurrogateManager

        manager = SurrogateManager()

        assert manager is not None
        assert hasattr(manager, 'models')

    def test_add_surrogate_model(self):
        """测试添加代理模型。"""
        from surrogate.manager import SurrogateManager

        manager = SurrogateManager()
        manager.add_model("model1", model_type="knn")

        assert "model1" in manager.models

    @pytest.mark.slow
    def test_manager_training_and_prediction(self):
        """测试管理器的训练和预测。"""
        from surrogate.manager import SurrogateManager

        # 创建训练数据
        np.random.seed(42)
        X = np.random.rand(100, 3)
        y = np.sum(X**2, axis=1)

        manager = SurrogateManager()
        manager.add_model("main", model_type="knn")
        manager.train_model("main", X, y)

        # 预测
        X_test = np.random.rand(20, 3)
        y_pred = manager.predict_model("main", X_test)

        assert y_pred is not None
        assert len(y_pred) == 20


class TestSurrogateStrategies:
    """测试代理策略。"""

    def test uncertainty_sampling(self):
        """测试不确定性采样策略。"""
        from surrogate.strategies import UncertaintySampling

        strategy = UncertaintySampling()

        # 模拟预测不确定性
        uncertainties = np.array([0.1, 0.5, 0.3, 0.8, 0.2])

        # 选择最不确定的样本
        selected = strategy.select(uncertainties, n_samples=2)

        assert len(selected) == 2
        # 应该选择不确定性最大的
        assert 1 in selected or 3 in selected

    def test_exploitation_exploration_tradeoff(self):
        """测试开发-探索权衡。"""
        from surrogate.strategies import AdaptiveStrategy

        strategy = AdaptiveStrategy(exploration_rate=0.3)

        # 根据代数调整策略
        strategy.update_strategy(generation=10, max_generations=100)

        # 早期应该偏向探索
        assert strategy.current_exploration_rate > 0


@pytest.mark.surrogate
class TestSurrogateIntegration:
    """测试代理模型集成场景。"""

    @pytest.mark.slow
    def test_surrogate_assisted_optimization(self):
        """测试代理辅助优化。"""
        from surrogate.manager import SurrogateManager
        from core.base import BlackBoxProblem

        # 定义昂贵评估问题
        class ExpensiveProblem(BlackBoxProblem):
            def __init__(self):
                super().__init__(
                    dimension=5,
                    objectives=["minimize"],
                    bounds=[(0, 1)] * 5
                )

            def evaluate(self, x):
                # 模拟昂贵评估
                import time
                time.sleep(0.001)  # 模拟延迟
                return np.sum(x**2)

        problem = ExpensiveProblem()
        manager = SurrogateManager()
        manager.add_model("surrogate", model_type="knn")

        # 初始采样
        np.random.seed(42)
        X_init = np.random.rand(20, 5)
        y_init = np.array([problem.evaluate(x) for x in X_init])

        # 训练代理
        manager.train_model("surrogate", X_init, y_init)

        # 使用代理筛选候选解
        X_candidates = np.random.rand(100, 5)
        y_surrogate = manager.predict_model("surrogate", X_candidates)

        # 选择最好的候选解进行真实评估
        top_indices = np.argsort(y_surrogate)[:5]
        for idx in top_indices:
            problem.evaluate(X_candidates[idx])

        # 应该减少了真实评估次数
        assert problem.evaluation_count < len(X_candidates)


@pytest.mark.parametrize("model_type", ["knn", "rf"])
def test_different_surrogate_models(model_type):
    """参数化测试：不同的代理模型。"""
    from surrogate.trainer import SurrogateTrainer

    # 创建数据
    np.random.seed(42)
    X = np.random.rand(50, 3)
    y = np.sum(X**2, axis=1)

    # 训练
    trainer = SurrogateTrainer(model_type=model_type)
    trainer.train(X, y)

    # 预测
    X_test = np.random.rand(10, 3)
    y_pred = trainer.predict(X_test)

    assert y_pred is not None
    assert len(y_pred) == 10
