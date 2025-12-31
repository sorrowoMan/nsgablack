"""
抽象图论结构框架

提供优雅的抽象类来表示各种图论问题结构，便于复用和扩展。
与数学逻辑偏置完美结合：抽象提供结构，数学提供逻辑。

Abstract Graph Theory Framework

Provides elegant abstract classes to represent various graph problem structures,
facilitating reuse and extension. Perfectly combined with mathematical logic biases:
abstraction provides structure, mathematics provides logic.

设计理念:
1. 抽象类提供标准的接口和数据结构
2. 具体实现专注于数学逻辑和约束定义
3. 便于复用常见的图论模式
4. 支持组合和扩展
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Set, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import numpy as np


class GraphType(Enum):
    """图的类型枚举"""
    UNDIRECTED = "undirected"
    DIRECTED = "directed"
    WEIGHTED = "weighted"
    UNWEIGHTED = "unweighted"
    BIPARTITE = "bipartite"
    TREE = "tree"
    COMPLETE = "complete"
    SPARSE = "sparse"
    DENSE = "dense"


class SolutionEncoding(Enum):
    """解的编码方式枚举"""
    PERMUTATION = "permutation"          # 排列编码（如TSP）
    BINARY_EDGES = "binary_edges"        # 二进制边选择
    ADJACENCY_MATRIX = "adjacency_matrix" # 邻接矩阵
    SEQUENCE = "sequence"                # 序列编码（如路径）
    PARTITION = "partition"              # 划分编码（如着色、社区检测）
    MATCHING = "matching"                # 匹配编码


@dataclass
class GraphMetadata:
    """图的元数据"""
    num_nodes: int
    num_edges: Optional[int] = None
    graph_type: List[GraphType] = field(default_factory=list)
    encoding: Optional[SolutionEncoding] = None
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """验证结果（保持与约束偏置的一致性）"""
    is_valid: bool
    violation_type: Optional[str] = None
    violation_details: Optional[Dict[str, Any]] = None
    penalty_value: float = 0.0

    def __post_init__(self):
        if not self.is_valid and self.penalty_value == 0.0:
            self.penalty_value = float('inf')


class AbstractGraphProblem(ABC):
    """
    抽象图论问题基类

    提供标准的接口和数据结构，具体问题专注于实现数学逻辑。
    """

    def __init__(self, num_nodes: int, **kwargs):
        self.num_nodes = num_nodes
        self.metadata = GraphMetadata(
            num_nodes=num_nodes,
            graph_type=kwargs.get('graph_type', []),
            encoding=kwargs.get('encoding'),
            properties=kwargs.get('properties', {})
        )

    @abstractmethod
    def get_name(self) -> str:
        """返回问题名称"""
        pass

    @abstractmethod
    def get_encoding(self) -> SolutionEncoding:
        """返回解的编码方式"""
        pass

    @abstractmethod
    def validate_solution(self, solution: np.ndarray) -> ValidationResult:
        """验证解的合法性"""
        pass

    @abstractmethod
    def decode_solution(self, solution: np.ndarray) -> Any:
        """将编码的解解码为具体的问题表示"""
        pass

    @abstractmethod
    def evaluate_solution(self, solution: np.ndarray) -> float:
        """评估解的质量（目标函数值）"""
        pass


class PermutationGraphProblem(AbstractGraphProblem):
    """
    排列编码的图论问题抽象类

    适用于：TSP、哈密顿路径、排列调度等问题
    """

    def __init__(self, num_nodes: int, **kwargs):
        super().__init__(num_nodes, encoding=SolutionEncoding.PERMUTATION, **kwargs)
        self.must_be_hamiltonian = kwargs.get('must_be_hamiltonian', True)
        self.must_be_cycle = kwargs.get('must_be_cycle', False)

    def get_encoding(self) -> SolutionEncoding:
        return SolutionEncoding.PERMUTATION

    def validate_permutation_constraints(self, perm: List[int]) -> ValidationResult:
        """验证排列约束的通用逻辑"""
        # 检查长度
        if len(perm) != self.num_nodes:
            return ValidationResult(
                is_valid=False,
                violation_type="wrong_length",
                violation_details={
                    "expected": self.num_nodes,
                    "actual": len(perm)
                }
            )

        # 检查元素范围
        if any(p < 0 or p >= self.num_nodes for p in perm):
            invalid_elements = [p for p in perm if p < 0 or p >= self.num_nodes]
            return ValidationResult(
                is_valid=False,
                violation_type="out_of_range",
                violation_details={"invalid_elements": invalid_elements}
            )

        # 检查重复元素
        if len(set(perm)) != len(perm):
            duplicates = [p for p in perm if perm.count(p) > 1]
            return ValidationResult(
                is_valid=False,
                violation_type="duplicates",
                violation_details={"duplicates": duplicates}
            )

        # 检查是否需要哈密顿路径
        if self.must_be_hamiltonian and len(set(perm)) != self.num_nodes:
            return ValidationResult(
                is_valid=False,
                violation_type="not_hamiltonian",
                violation_details={}
            )

        return ValidationResult(is_valid=True)

    def decode_solution(self, solution: np.ndarray) -> List[int]:
        """解码排列"""
        # 四舍五入并转为整数
        perm = np.round(solution).astype(int)
        # 确保在有效范围内
        perm = np.clip(perm, 0, self.num_nodes - 1)
        return perm.tolist()


class TSPProblem(PermutationGraphProblem):
    """
    旅行商问题抽象类

    继承排列编码的问题框架，专注于TSP的数学逻辑
    """

    def __init__(self, distance_matrix: np.ndarray, **kwargs):
        num_nodes = distance_matrix.shape[0]
        super().__init__(num_nodes, must_be_cycle=True, **kwargs)
        self.distance_matrix = distance_matrix
        self.metadata.graph_type = [GraphType.COMPLETE, GraphType.WEIGHTED]

    def get_name(self) -> str:
        return "Traveling Salesman Problem (TSP)"

    def validate_solution(self, solution: np.ndarray) -> ValidationResult:
        """验证TSP解"""
        perm = self.decode_solution(solution)
        result = self.validate_permutation_constraints(perm)

        if not result.is_valid:
            return result

        # TSP特定的验证：如果需要环路，检查首尾是否相连
        # （实际上在完全图中总是相连的，这里作为示例）
        if self.must_be_cycle:
            # 在实际实现中，可以检查是否存在从最后一个节点到第一个节点的边
            pass

        return ValidationResult(is_valid=True)

    def evaluate_solution(self, solution: np.ndarray) -> float:
        """计算TSP路径长度"""
        perm = self.decode_solution(solution)

        # 验证解是否合法
        if not self.validate_solution(solution).is_valid:
            return float('inf')

        # 计算总距离
        total_distance = 0.0
        for i in range(len(perm)):
            j = (i + 1) % len(perm)  # 回到起点
            total_distance += self.distance_matrix[perm[i], perm[j]]

        return total_distance


class HamiltonianPathProblem(PermutationGraphProblem):
    """
    哈密顿路径问题抽象类
    """

    def __init__(self, adjacency_matrix: np.ndarray, is_cycle: bool = False, **kwargs):
        num_nodes = adjacency_matrix.shape[0]
        super().__init__(num_nodes, must_be_hamiltonian=True, must_be_cycle=is_cycle, **kwargs)
        self.adjacency_matrix = adjacency_matrix
        self.metadata.graph_type = [GraphType.UNWEIGHTED]

    def get_name(self) -> str:
        return "Hamiltonian Path Problem"

    def validate_solution(self, solution: np.ndarray) -> ValidationResult:
        """验证哈密顿路径"""
        perm = self.decode_solution(solution)
        result = self.validate_permutation_constraints(perm)

        if not result.is_valid:
            return result

        # 验证路径连续性
        for i in range(len(perm) - 1):
            if self.adjacency_matrix[perm[i], perm[i + 1]] == 0:
                return ValidationResult(
                    is_valid=False,
                    violation_type="discontinuous_path",
                    violation_details={"break_point": i, "from": perm[i], "to": perm[i + 1]}
                )

        # 如果是环路，检查首尾相连
        if self.must_be_cycle and self.adjacency_matrix[perm[-1], perm[0]] == 0:
            return ValidationResult(
                is_valid=False,
                violation_type="not_a_cycle",
                violation_details={"start": perm[0], "end": perm[-1]}
            )

        return ValidationResult(is_valid=True)

    def evaluate_solution(self, solution: np.ndarray) -> float:
        """评估哈密顿路径（这里简单地返回0或inf）"""
        if self.validate_solution(solution).is_valid:
            return 0.0  # 找到有效路径
        else:
            return float('inf')


class BinaryEdgesGraphProblem(AbstractGraphProblem):
    """
    二进制边选择编码的图论问题抽象类

    适用于：树、生成树、匹配、子图选择等问题
    """

    def __init__(self, num_nodes: int, **kwargs):
        super().__init__(num_nodes, encoding=SolutionEncoding.BINARY_EDGES, **kwargs)
        self.expected_edges = kwargs.get('expected_edges')
        self.must_be_connected = kwargs.get('must_be_connected', False)
        self.must_be_acyclic = kwargs.get('must_be_acyclic', False)

    def get_encoding(self) -> SolutionEncoding:
        return SolutionEncoding.BINARY_EDGES

    def decode_edges(self, solution: np.ndarray) -> List[Tuple[int, int]]:
        """将二进制向量解码为边列表"""
        edges = []
        edge_idx = 0

        for i in range(self.num_nodes):
            for j in range(i + 1, self.num_nodes):
                if edge_idx < len(solution) and solution[edge_idx] > 0.5:
                    edges.append((i, j))
                edge_idx += 1

        return edges

    def decode_solution(self, solution: np.ndarray) -> List[Tuple[int, int]]:
        return self.decode_edges(solution)


class SpanningTreeProblem(BinaryEdgesGraphProblem):
    """
    生成树问题抽象类
    """

    def __init__(self, num_nodes: int, edge_weights: Optional[Dict[Tuple[int, int], float]] = None, **kwargs):
        super().__init__(
            num_nodes,
            expected_edges=num_nodes - 1,
            must_be_connected=True,
            must_be_acyclic=True,
            **kwargs
        )
        self.edge_weights = edge_weights or {}
        self.metadata.graph_type = [GraphType.TREE, GraphType.CONNECTED]

    def get_name(self) -> str:
        return "Spanning Tree Problem"

    def validate_solution(self, solution: np.ndarray) -> ValidationResult:
        """验证生成树"""
        edges = self.decode_edges(solution)

        # 检查边数
        if len(edges) != self.num_nodes - 1:
            return ValidationResult(
                is_valid=False,
                violation_type="wrong_edge_count",
                violation_details={
                    "expected": self.num_nodes - 1,
                    "actual": len(edges)
                }
            )

        # 检查连通性
        if not self._is_connected(edges):
            return ValidationResult(
                is_valid=False,
                violation_type="disconnected",
                violation_details={}
            )

        # 检查无环
        if self._has_cycle(edges):
            return ValidationResult(
                is_valid=False,
                violation_type="has_cycle",
                violation_details={}
            )

        return ValidationResult(is_valid=True)

    def _is_connected(self, edges: List[Tuple[int, int]]) -> bool:
        """检查图是否连通"""
        if self.num_nodes == 0:
            return True

        # DFS检查连通性
        visited = set()
        stack = [0]

        adjacency = {i: [] for i in range(self.num_nodes)}
        for u, v in edges:
            adjacency[u].append(v)
            adjacency[v].append(u)

        while stack:
            node = stack.pop()
            if node not in visited:
                visited.add(node)
                stack.extend(adjacency[node])

        return len(visited) == self.num_nodes

    def _has_cycle(self, edges: List[Tuple[int, int]]) -> bool:
        """检查是否有环"""
        parent = list(range(self.num_nodes))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            px, py = find(x), find(y)
            if px == py:
                return False
            parent[px] = py
            return True

        for u, v in edges:
            if not union(u, v):
                return True

        return False

    def evaluate_solution(self, solution: np.ndarray) -> float:
        """计算生成树的总权重"""
        edges = self.decode_edges(solution)

        if not self.validate_solution(solution).is_valid:
            return float('inf')

        total_weight = sum(self.edge_weights.get((u, v), 1.0) for u, v in edges)
        return total_weight


class PartitionGraphProblem(AbstractGraphProblem):
    """
    划分编码的图论问题抽象类

    适用于：图着色、社区检测、聚类等问题
    """

    def __init__(self, num_nodes: int, num_groups: int, **kwargs):
        super().__init__(num_nodes, encoding=SolutionEncoding.PARTITION, **kwargs)
        self.num_groups = num_groups
        self.metadata.properties['num_groups'] = num_groups

    def get_encoding(self) -> SolutionEncoding:
        return SolutionEncoding.PARTITION

    def decode_partition(self, solution: np.ndarray) -> List[int]:
        """将解向量解码为分组标签"""
        groups = np.round(solution).astype(int)
        groups = np.clip(groups, 0, self.num_groups - 1)
        return groups.tolist()

    def decode_solution(self, solution: np.ndarray) -> List[int]:
        return self.decode_partition(solution)


class GraphColoringProblem(PartitionGraphProblem):
    """
    图着色问题抽象类
    """

    def __init__(self, adjacency_matrix: np.ndarray, max_colors: int, **kwargs):
        num_nodes = adjacency_matrix.shape[0]
        super().__init__(num_nodes, max_colors, **kwargs)
        self.adjacency_matrix = adjacency_matrix
        self.max_colors = max_colors
        self.metadata.graph_type = [GraphType.UNWEIGHTED]
        self.metadata.properties['max_colors'] = max_colors

    def get_name(self) -> str:
        return f"Graph Coloring Problem ({self.max_colors} colors)"

    def validate_solution(self, solution: np.ndarray) -> ValidationResult:
        """验证图着色"""
        colors = self.decode_partition(solution)

        # 检查使用的颜色数
        unique_colors = set(colors)
        if len(unique_colors) > self.max_colors:
            return ValidationResult(
                is_valid=False,
                violation_type="too_many_colors",
                violation_details={
                    "max_allowed": self.max_colors,
                    "actual": len(unique_colors)
                }
            )

        # 检查相邻节点颜色冲突
        conflicts = []
        for i in range(self.num_nodes):
            for j in range(i + 1, self.num_nodes):
                if self.adjacency_matrix[i, j] > 0 and colors[i] == colors[j]:
                    conflicts.append((i, j, colors[i]))

        if conflicts:
            return ValidationResult(
                is_valid=False,
                violation_type="color_conflict",
                violation_details={"conflicts": conflicts}
            )

        return ValidationResult(is_valid=True)

    def evaluate_solution(self, solution: np.ndarray) -> float:
        """评估着色方案（最小化使用的颜色数）"""
        colors = self.decode_partition(solution)

        if not self.validate_solution(solution).is_valid:
            return float('inf')

        # 返回使用的颜色数
        return len(set(colors))


class GraphProblemFactory:
    """
    图论问题工厂类

    提供统一的问题创建接口
    """

    @staticmethod
    def create_tsp(distance_matrix: np.ndarray, **kwargs) -> TSPProblem:
        """创建TSP问题"""
        return TSPProblem(distance_matrix, **kwargs)

    @staticmethod
    def create_spanning_tree(num_nodes: int, edge_weights: Optional[Dict] = None, **kwargs) -> SpanningTreeProblem:
        """创建生成树问题"""
        return SpanningTreeProblem(num_nodes, edge_weights, **kwargs)

    @staticmethod
    def create_graph_coloring(adjacency_matrix: np.ndarray, max_colors: int, **kwargs) -> GraphColoringProblem:
        """创建图着色问题"""
        return GraphColoringProblem(adjacency_matrix, max_colors, **kwargs)

    @staticmethod
    def create_hamiltonian_path(adjacency_matrix: np.ndarray, is_cycle: bool = False, **kwargs) -> HamiltonianPathProblem:
        """创建哈密顿路径问题"""
        return HamiltonianPathProblem(adjacency_matrix, is_cycle, **kwargs)

    @staticmethod
    def get_available_problems() -> List[str]:
        """获取所有可用的问题类型"""
        return [
            'tsp',
            'spanning_tree',
            'graph_coloring',
            'hamiltonian_path'
        ]


# 组合问题类 - 支持多个目标的组合
class CompositeGraphProblem(AbstractGraphProblem):
    """
    组合图论问题

    将多个图论问题组合在一起，适用于复杂的多约束场景
    """

    def __init__(self, subproblems: List[AbstractGraphProblem], **kwargs):
        # 所有子问题的节点数必须相同
        num_nodes = subproblems[0].num_nodes
        for problem in subproblems:
            if problem.num_nodes != num_nodes:
                raise ValueError("All subproblems must have the same number of nodes")

        super().__init__(num_nodes, **kwargs)
        self.subproblems = subproblems

    def get_name(self) -> str:
        return f"Composite Problem ({', '.join(p.get_name() for p in self.subproblems)})"

    def get_encoding(self) -> SolutionEncoding:
        # 使用第一个子问题的编码方式
        return self.subproblems[0].get_encoding()

    def validate_solution(self, solution: np.ndarray) -> ValidationResult:
        """验证所有子问题的约束"""
        for i, problem in enumerate(self.subproblems):
            result = problem.validate_solution(solution)
            if not result.is_valid:
                result.violation_details = {
                    **result.violation_details,
                    "subproblem": i,
                    "subproblem_name": problem.get_name()
                }
                return result
        return ValidationResult(is_valid=True)

    def decode_solution(self, solution: np.ndarray) -> Any:
        """使用第一个子问题的解码方式"""
        return self.subproblems[0].decode_solution(solution)

    def evaluate_solution(self, solution: np.ndarray) -> float:
        """组合评估所有子问题"""
        if not self.validate_solution(solution).is_valid:
            return float('inf')

        # 简单求和，可以根据需要使用加权组合
        total = 0.0
        for problem in self.subproblems:
            total += problem.evaluate_solution(solution)

        return total

    def add_subproblem(self, problem: AbstractGraphProblem):
        """添加子问题"""
        if problem.num_nodes != self.num_nodes:
            raise ValueError("Subproblem must have the same number of nodes")
        self.subproblems.append(problem)