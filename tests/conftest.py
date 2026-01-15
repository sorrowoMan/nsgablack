"""
pytest配置文件

提供测试fixture和通用工具。
"""
import pytest
import numpy as np
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def sample_problem():
    """创建一个简单的测试问题。

    Returns:
        BlackBoxProblem: 简单的二维Sphere问题
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from core.base import BlackBoxProblem

    class SimpleSphere(BlackBoxProblem):
        def __init__(self):
            super().__init__(
                dimension=2,
                objectives=["minimize"],
                bounds=[(-10, 10)] * 2
            )

        def evaluate(self, x):
            return np.sum(x**2)

    return SimpleSphere()


@pytest.fixture
def temp_dir():
    """创建临时目录。

    Yields:
        Path: 临时目录路径
    """
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # 清理
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_solutions():
    """创建样本解集。

    Returns:
        tuple: (决策变量, 目标值)
    """
    np.random.seed(42)
    x = np.random.randn(10, 2)  # 10个解，2维
    f = np.sum(x**2, axis=1)
    return x, f


@pytest.fixture
def sample_bias():
    """创建样本偏置模块。

    Returns:
        BiasModule: 配置好的偏置模块
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from bias.bias import BiasModule

    bias = BiasModule()

    # 添加一个简单的约束偏置
    def constraint_penalty(x, constraints, context):
        violation = np.sum(np.maximum(x, 5))  # x > 5时惩罚
        return {"penalty": violation}

    bias.add_penalty(constraint_penalty, weight=1.0, name="bounds_penalty")

    return bias
