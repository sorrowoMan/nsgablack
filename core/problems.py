import time
import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.datasets import make_classification
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

from .base import BlackBoxProblem
from .solver import BlackBoxSolverNSGAII


class SphereBlackBox(BlackBoxProblem):
    def __init__(self, dimension=2):
        super().__init__(f"Sphere函数 (d={dimension})", dimension)

    def evaluate(self, x):
        if hasattr(x, 'shape') and len(x.shape) > 1:
            return np.sum(x**2, axis=1)
        return np.sum(x**2)


class ZDT1BlackBox(BlackBoxProblem):
    def __init__(self, dimension=30):
        super().__init__(f"ZDT1函数 (d={dimension})", dimension)
        self.bounds = {var: [0, 1] for var in self.variables}

    def evaluate(self, x):
        if hasattr(x, 'shape') and len(x.shape) > 1:
            f1 = x[:, 0]
            g = 1 + 9 * np.sum(x[:, 1:], axis=1) / (self.dimension - 1)
            h = 1 - np.sqrt(f1 / g)
            f2 = g * h
            return np.column_stack([f1, f2])
        f1 = x[0]
        g = 1 + 9 * np.sum(x[1:]) / (self.dimension - 1)
        h = 1 - np.sqrt(f1 / g)
        f2 = g * h
        return np.array([f1, f2])

    def get_num_objectives(self):
        return 2


class ZDT3BlackBox(BlackBoxProblem):
    """ZDT3问题 - 具有断开的Pareto前沿"""
    def __init__(self, dimension=30):
        super().__init__(f"ZDT3函数 (d={dimension})", dimension)
        self.bounds = {var: [0, 1] for var in self.variables}

    def evaluate(self, x):
        if hasattr(x, 'shape') and len(x.shape) > 1:
            f1 = x[:, 0]
            g = 1 + 9 * np.sum(x[:, 1:], axis=1) / (self.dimension - 1)
            h = 1 - np.sqrt(f1 / g) - (f1 / g) * np.sin(10 * np.pi * f1)
            f2 = g * h
            return np.column_stack([f1, f2])
        f1 = x[0]
        g = 1 + 9 * np.sum(x[1:]) / (self.dimension - 1)
        h = 1 - np.sqrt(f1 / g) - (f1 / g) * np.sin(10 * np.pi * f1)
        f2 = g * h
        return np.array([f1, f2])

    def get_num_objectives(self):
        return 2


class DTLZ2BlackBox(BlackBoxProblem):
    """DTLZ2问题 - 可扩展的多目标测试问题"""
    def __init__(self, dimension=12, n_objectives=3):
        super().__init__(f"DTLZ2函数 (d={dimension}, objectives={n_objectives})", dimension)
        self.n_objectives = n_objectives
        self.bounds = {var: [0, 1] for var in self.variables}

    def evaluate(self, x):
        if hasattr(x, 'shape') and len(x.shape) > 1:
            # 批量处理
            k = self.dimension - self.n_objectives + 1
            g = np.sum((x[:, self.n_objectives-1:] - 0.5) ** 2, axis=1)

            objectives = []
            for i in range(self.n_objectives):
                if i == self.n_objectives - 1:
                    # 最后一个目标
                    prod = np.ones(x.shape[0])
                    for j in range(self.n_objectives - 1):
                        prod *= np.cos(x[:, j] * np.pi / 2)
                    obj = (1 + g) * (1 - prod)
                else:
                    prod = np.ones(x.shape[0])
                    for j in range(self.n_objectives - 1 - i):
                        prod *= np.cos(x[:, j] * np.pi / 2)
                    if i > 0:
                        prod *= np.sin(x[:, self.n_objectives - 2 - i] * np.pi / 2)
                    obj = (1 + g) * prod
                objectives.append(obj)
            return np.column_stack(objectives)
        else:
            # 单个解
            k = self.dimension - self.n_objectives + 1
            g = np.sum((x[self.n_objectives-1:] - 0.5) ** 2)

            objectives = []
            for i in range(self.n_objectives):
                if i == self.n_objectives - 1:
                    # 最后一个目标
                    prod = 1.0
                    for j in range(self.n_objectives - 1):
                        prod *= np.cos(x[j] * np.pi / 2)
                    obj = (1 + g) * (1 - prod)
                else:
                    prod = 1.0
                    for j in range(self.n_objectives - 1 - i):
                        prod *= np.cos(x[j] * np.pi / 2)
                    if i > 0:
                        prod *= np.sin(x[self.n_objectives - 2 - i] * np.pi / 2)
                    obj = (1 + g) * prod
                objectives.append(obj)
            return np.array(objectives)

    def get_num_objectives(self):
        return self.n_objectives


class ExpensiveSimulationBlackBox(BlackBoxProblem):
    def __init__(self, dimension=5):
        super().__init__(f"昂贵仿真 (d={dimension})", dimension)

    def evaluate(self, x):
        time.sleep(0.01)
        if hasattr(x, 'shape') and len(x.shape) > 1:
            result = np.zeros((x.shape[0], 2))
            for i in range(x.shape[0]):
                result[i, 0] = np.sum(x[i]**2)
                result[i, 1] = np.sum((x[i] - 1)**2)
            return result
        f1 = np.sum(x**2)
        f2 = np.sum((x - 1)**2)
        return np.array([f1, f2])

    def get_num_objectives(self):
        return 2


class NeuralNetworkHyperparameterOptimization(BlackBoxProblem):
    def __init__(self, dimension=4):
        super().__init__("神经网络超参数优化", dimension)
        self.bounds = {
            'x0': [10, 200],
            'x1': [10, 200],
            'x2': [0.0001, 0.1],
            'x3': [0.0001, 0.01]
        }
        self.X, self.y = make_classification(
            n_samples=1000, n_features=20, n_informative=15,
            n_redundant=5, n_classes=3, random_state=42
        )
        self.scaler = StandardScaler()
        self.X_scaled = self.scaler.fit_transform(self.X)
        print(f"创建神经网络超参数优化问题，数据集形状: {self.X.shape}")

    def evaluate(self, x):
        if hasattr(x, 'shape') and len(x.shape) > 1:
            results = np.zeros((x.shape[0], 2))
            for i in range(x.shape[0]):
                results[i] = self._evaluate_single(x[i])
            return results
        return self._evaluate_single(x)

    def _evaluate_single(self, params):
        try:
            hidden1 = max(10, int(params[0]))
            hidden2 = max(10, int(params[1]))
            learning_rate = max(0.0001, min(0.1, params[2]))
            alpha = max(0.0001, min(0.01, params[3]))
            model = MLPClassifier(
                hidden_layer_sizes=(hidden1, hidden2),
                learning_rate_init=learning_rate,
                alpha=alpha,
                max_iter=100,
                random_state=42,
                early_stopping=True,
                n_iter_no_change=10
            )
            scores = cross_val_score(model, self.X_scaled, self.y, cv=3, scoring='accuracy', n_jobs=1)
            accuracy = np.mean(scores)
            input_size = self.X.shape[1]
            output_size = len(np.unique(self.y))
            complexity = (input_size * hidden1 + hidden1 * hidden2 +
                          hidden2 * output_size + hidden1 + hidden2 + output_size)
            return np.array([1 - accuracy, complexity / 10000])
        except Exception as e:
            print(f"模型训练失败: {e}")
            return np.array([1.0, 100.0])

    def get_num_objectives(self):
        return 2


class EngineeringDesignOptimization(BlackBoxProblem):
    def __init__(self, dimension=3):
        super().__init__("工程梁设计优化", dimension)
        self.bounds = {
            'x0': [0.1, 1.0],
            'x1': [0.1, 1.0],
            'x2': [2.0, 10.0]
        }

    def evaluate(self, x):
        if hasattr(x, 'shape') and len(x.shape) > 1:
            results = np.zeros((x.shape[0], 2))
            for i in range(x.shape[0]):
                results[i] = self._evaluate_single(x[i])
            return results
        return self._evaluate_single(x)

    def _evaluate_single(self, params):
        width, height, length = params
        if width <= 0 or height <= 0 or length <= 0:
            return np.array([1000.0, 1000.0])
        density = 7850
        elastic_modulus = 2e11
        load = 10000
        volume = width * height * length
        weight = density * volume
        moment_of_inertia = (width * height**3) / 12
        if moment_of_inertia <= 0:
            deformation = 1e10
        else:
            deformation = (load * length**3) / (3 * elastic_modulus * moment_of_inertia)
        return np.array([weight, deformation])

    def get_num_objectives(self):
        return 2


class BusinessPortfolioOptimization(BlackBoxProblem):
    def __init__(self, dimension=5):
        super().__init__("投资组合优化", dimension)
        self.bounds = {f'x{i}': [0.0, 1.0] for i in range(dimension)}
        np.random.seed(42)
        self.expected_returns = np.random.uniform(0.05, 0.15, dimension)
        self.covariance_matrix = self._generate_covariance_matrix(dimension)

    def _generate_covariance_matrix(self, n_assets):
        A = np.random.rand(n_assets, n_assets)
        return np.dot(A, A.T) * 0.1

    def evaluate(self, x):
        if hasattr(x, 'shape') and len(x.shape) > 1:
            results = np.zeros((x.shape[0], 2))
            for i in range(x.shape[0]):
                results[i] = self._evaluate_single(x[i])
            return results
        return self._evaluate_single(x)

    def _evaluate_single(self, weights):
        weights = np.abs(weights)
        weights = weights / np.sum(weights) if np.sum(weights) > 0 else weights
        expected_return = np.dot(weights, self.expected_returns)
        portfolio_variance = np.dot(weights.T, np.dot(self.covariance_matrix, weights))
        return np.array([-expected_return, portfolio_variance])

    def get_num_objectives(self):
        return 2


def demo_sphere_blackbox():
    problem = SphereBlackBox(dimension=2)
    solver = BlackBoxSolverNSGAII(problem)
    return solver


def demo_zdt1_blackbox():
    problem = ZDT1BlackBox(dimension=10)
    solver = BlackBoxSolverNSGAII(problem)
    return solver


def demo_expensive_simulation():
    problem = ExpensiveSimulationBlackBox(dimension=5)
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 40
    solver.max_generations = 50
    solver.diversity_params['candidate_size'] = 200
    return solver


def optimize_neural_network():
    problem = NeuralNetworkHyperparameterOptimization(dimension=4)
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 50
    solver.max_generations = 100
    solver.mutation_rate = 0.1
    solver.crossover_rate = 0.9
    solver.enable_diversity_init = True
    solver.use_history = True
    solver.enable_elite_retention = True
    solver.diversity_params['candidate_size'] = 200
    solver.diversity_params['similarity_threshold'] = 0.1
    solver.diversity_params['rejection_prob'] = 0.7
    solver.elite_retention_prob = 0.85
    return solver


def optimize_engineering_design():
    problem = EngineeringDesignOptimization(dimension=3)
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 40
    solver.max_generations = 80
    solver.enable_diversity_init = True
    solver.enable_elite_retention = True
    return solver


def optimize_business_portfolio():
    problem = BusinessPortfolioOptimization(dimension=5)
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 60
    solver.max_generations = 120
    solver.enable_diversity_init = True
    solver.enable_elite_retention = True
    return solver


def analyze_results(solver, problem_name):
    if solver.pareto_solutions is None or len(solver.pareto_solutions['individuals']) == 0:
        print("没有找到Pareto最优解")
        return
    pareto_front = solver.pareto_solutions
    print(f"\n=== {problem_name} 优化结果 ===")
    print(f"找到 {len(pareto_front['individuals'])} 个Pareto最优解")
    print(f"总函数评估次数: {solver.evaluation_count}")
    for i, (ind, obj) in enumerate(zip(pareto_front['individuals'][:5], pareto_front['objectives'][:5])):
        print(f"\n解 {i+1}:")
        for var_idx, var_name in enumerate(solver.variables):
            print(f"  {var_name}: {ind[var_idx]:.4f}")
        if problem_name == "神经网络超参数优化":
            hidden1 = int(ind[0])
            hidden2 = int(ind[1])
            lr = ind[2]
            alpha = ind[3]
            accuracy = 1 - obj[0]
            complexity = obj[1] * 10000
            print(f"  隐藏层1: {hidden1} 神经元")
            print(f"  隐藏层2: {hidden2} 神经元")
            print(f"  学习率: {lr:.6f}")
            print(f"  正则化: {alpha:.6f}")
            print(f"  准确率: {accuracy:.4f}")
            print(f"  参数数量: {complexity:.0f}")
        elif problem_name == "工程梁设计优化":
            width, height, length = ind
            weight = obj[0]
            deformation = obj[1]
            print(f"  宽度: {width:.3f} m")
            print(f"  高度: {height:.3f} m")
            print(f"  长度: {length:.3f} m")
            print(f"  重量: {weight:.2f} kg")
            print(f"  变形: {deformation:.6f} m")
        elif problem_name == "投资组合优化":
            weights = ind
            expected_return = -obj[0]
            risk = obj[1]
            print(f"  预期收益: {expected_return:.4f}")
            print(f"  风险: {risk:.6f}")
            print(f"  资产配置: {[f'{w:.3f}' for w in weights]}\n")

__all__ = [
    'SphereBlackBox', 'ZDT1BlackBox', 'ExpensiveSimulationBlackBox',
    'NeuralNetworkHyperparameterOptimization', 'EngineeringDesignOptimization',
    'BusinessPortfolioOptimization', 'demo_sphere_blackbox', 'demo_zdt1_blackbox',
    'demo_expensive_simulation', 'optimize_neural_network', 'optimize_engineering_design',
    'optimize_business_portfolio', 'analyze_results'
]
import time
import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.datasets import make_classification
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

from .base import BlackBoxProblem


class SphereBlackBox(BlackBoxProblem):
    """Sphere函数黑箱问题（单目标）"""

    def __init__(self, dimension=2):
        super().__init__(f"Sphere函数 (d={dimension})", dimension)

    def evaluate(self, x):
        if hasattr(x, 'shape') and len(x.shape) > 1:
            return np.sum(x**2, axis=1)
        else:
            return np.sum(x**2)


class ZDT1BlackBox(BlackBoxProblem):
    """ZDT1测试函数黑箱问题（多目标）"""

    def __init__(self, dimension=30):
        super().__init__(f"ZDT1函数 (d={dimension})", dimension)
        self.bounds = {var: [0, 1] for var in self.variables}

    def evaluate(self, x):
        if hasattr(x, 'shape') and len(x.shape) > 1:
            f1 = x[:, 0]
            g = 1 + 9 * np.sum(x[:, 1:], axis=1) / (self.dimension - 1)
            h = 1 - np.sqrt(f1 / g)
            f2 = g * h
            return np.column_stack([f1, f2])
        else:
            f1 = x[0]
            g = 1 + 9 * np.sum(x[1:]) / (self.dimension - 1)
            h = 1 - np.sqrt(f1 / g)
            f2 = g * h
            return np.array([f1, f2])

    def get_num_objectives(self):
        return 2


class ExpensiveSimulationBlackBox(BlackBoxProblem):
    """昂贵仿真黑箱问题示例"""

    def __init__(self, dimension=5):
        super().__init__(f"昂贵仿真 (d={dimension})", dimension)

    def evaluate(self, x):
        time.sleep(0.01)
        if hasattr(x, 'shape') and len(x.shape) > 1:
            result = np.zeros((x.shape[0], 2))
            for i in range(x.shape[0]):
                result[i, 0] = np.sum(x[i]**2)
                result[i, 1] = np.sum((x[i] - 1)**2)
            return result
        else:
            f1 = np.sum(x**2)
            f2 = np.sum((x - 1)**2)
            return np.array([f1, f2])

    def get_num_objectives(self):
        return 2


class NeuralNetworkHyperparameterOptimization(BlackBoxProblem):
    """神经网络超参数优化黑箱问题（多目标）"""

    def __init__(self, dimension=4):
        super().__init__("神经网络超参数优化", dimension)
        self.bounds = {
            'x0': [10, 200],
            'x1': [10, 200],
            'x2': [0.0001, 0.1],
            'x3': [0.0001, 0.01]
        }
        self.X, self.y = make_classification(
            n_samples=1000, n_features=20, n_informative=15,
            n_redundant=5, n_classes=3, random_state=42
        )
        self.scaler = StandardScaler()
        self.X_scaled = self.scaler.fit_transform(self.X)

    def evaluate(self, x):
        if hasattr(x, 'shape') and len(x.shape) > 1:
            results = np.zeros((x.shape[0], 2))
            for i in range(x.shape[0]):
                results[i] = self._evaluate_single(x[i])
            return results
        else:
            return self._evaluate_single(x)

    def _evaluate_single(self, params):
        try:
            hidden1 = max(10, int(params[0]))
            hidden2 = max(10, int(params[1]))
            learning_rate = max(0.0001, min(0.1, float(params[2])))
            alpha = max(0.0001, min(0.01, float(params[3])))
            model = MLPClassifier(
                hidden_layer_sizes=(hidden1, hidden2),
                learning_rate_init=learning_rate,
                alpha=alpha,
                max_iter=100,
                random_state=42,
                early_stopping=True,
                n_iter_no_change=10
            )
            scores = cross_val_score(model, self.X_scaled, self.y, cv=3, scoring='accuracy', n_jobs=1)
            accuracy = float(np.mean(scores))
            input_size = self.X.shape[1]
            output_size = len(np.unique(self.y))
            complexity = (input_size * hidden1 + hidden1 * hidden2 + hidden2 * output_size + hidden1 + hidden2 + output_size)
            return np.array([1 - accuracy, complexity / 10000])
        except Exception as e:
            print(f"模型训练失败: {e}")
            return np.array([1.0, 100.0])

    def get_num_objectives(self):
        return 2


class EngineeringDesignOptimization(BlackBoxProblem):
    """工程设计优化问题示例（多目标）"""

    def __init__(self, dimension=3):
        super().__init__("工程梁设计优化", dimension)
        self.bounds = {
            'x0': [0.1, 1.0],
            'x1': [0.1, 1.0],
            'x2': [2.0, 10.0]
        }

    def evaluate(self, x):
        if hasattr(x, 'shape') and len(x.shape) > 1:
            results = np.zeros((x.shape[0], 2))
            for i in range(x.shape[0]):
                results[i] = self._evaluate_single(x[i])
            return results
        else:
            return self._evaluate_single(x)

    def _evaluate_single(self, params):
        width, height, length = params
        if width <= 0 or height <= 0 or length <= 0:
            return np.array([1000.0, 1000.0])
        density = 7850
        elastic_modulus = 2e11
        load = 10000
        volume = float(width) * float(height) * float(length)
        weight = density * volume
        moment_of_inertia = (float(width) * float(height)**3) / 12.0
        if moment_of_inertia <= 0:
            deformation = 1e10
        else:
            deformation = (load * float(length)**3) / (3 * elastic_modulus * moment_of_inertia)
        return np.array([weight, deformation])


class BusinessPortfolioOptimization(BlackBoxProblem):
    """投资组合优化问题（多目标）"""

    def __init__(self, dimension=5):
        super().__init__("投资组合优化", dimension)
        self.bounds = {f'x{i}': [0.0, 1.0] for i in range(dimension)}
        np.random.seed(42)
        self.expected_returns = np.random.uniform(0.05, 0.15, dimension)
        A = np.random.rand(dimension, dimension)
        self.covariance_matrix = np.dot(A, A.T) * 0.1

    def evaluate(self, x):
        if hasattr(x, 'shape') and len(x.shape) > 1:
            results = np.zeros((x.shape[0], 2))
            for i in range(x.shape[0]):
                results[i] = self._evaluate_single(x[i])
            return results
        else:
            return self._evaluate_single(x)

    def _evaluate_single(self, weights):
        weights = np.abs(weights)
        weights = weights / np.sum(weights) if np.sum(weights) > 0 else weights
        expected_return = float(np.dot(weights, self.expected_returns))
        portfolio_variance = float(np.dot(weights.T, np.dot(self.covariance_matrix, weights)))
        return np.array([-expected_return, portfolio_variance])
    
    def get_num_objectives(self):
        return 2
