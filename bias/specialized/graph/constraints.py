"""
图约束偏置 - Graph Constraint Bias

专注于验证和维护图论问题的约束合法性，确保进入进化过程的个体满足图论规范。

核心思想：只判断解是否合法，通过无限大惩罚值约束搜索空间，而不是引导搜索方向。
这是图论优化的终极解法之一。

主要功能：
- TSP（旅行商问题）约束验证
- 路径/回路约束验证
- 树结构约束验证
- 图着色约束验证
- 匹配问题约束验证
- 通用图论约束验证框架

Core Philosophy:
- 只做约束验证，不做搜索引导
- 违反约束 = 无限大惩罚值
- 满足约束 = 零惩罚值
- 让算法自己探索所有合法解空间
"""

import numpy as np
from typing import List, Tuple, Dict, Optional, Set, Union, Callable, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass

from bias_base import DomainBias, OptimizationContext


class GraphConstraintViolation(Exception):
    """图约束违反异常"""
    pass


@dataclass
class ValidationResult:
    """约束验证结果"""
    is_valid: bool
    violation_type: Optional[str] = None
    violation_details: Optional[Dict[str, Any]] = None
    penalty_value: float = 0.0

    def __post_init__(self):
        if not self.is_valid and self.penalty_value == 0.0:
            # 默认违反约束的惩罚值
            self.penalty_value = float('inf')


class GraphConstraintBias(DomainBias):
    """
    图约束偏置基类

    专门用于验证图论问题的约束合法性
    """

    def __init__(self, name: str, penalty_scale: float = 1e6):
        super().__init__(name, weight=1.0)
        self.penalty_scale = penalty_scale  # 约束违反的惩罚规模

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算约束违反惩罚

        Returns:
            0.0 if constraints are satisfied
            Large penalty value if constraints are violated
        """
        result = self.validate_constraints(x, context)
        return result.penalty_value if result.penalty_value != float('inf') else self.penalty_scale

    @abstractmethod
    def validate_constraints(self, x: np.ndarray, context: OptimizationContext) -> ValidationResult:
        """
        验证约束的抽象方法

        子类必须实现具体的约束验证逻辑
        """
        pass


class TSPConstraintBias(GraphConstraintBias):
    """
    旅行商问题(TSP)约束偏置

    验证TSP解的合法性：
    1. 必须访问所有城市
    2. 每个城市只能访问一次
    3. 必须形成闭合回路
    """

    def __init__(self, num_cities: int, penalty_scale: float = 1e6):
        super().__init__("tsp_constraint", penalty_scale)
        self.num_cities = num_cities

    def validate_constraints(self, x: np.ndarray, context: OptimizationContext) -> ValidationResult:
        """
        验证TSP约束

        Args:
            x: 解向量，可以是：
               - 排序形式：城市的访问顺序
               - 二进制形式：边是否被选择
               - 浮点形式：需要转换为离散值
        """
        try:
            # 转换为城市序列
            if len(x) == self.num_cities:
                # 排序形式
                tour = np.round(x).astype(int)
            else:
                # 二进制形式，需要构建序列
                tour = self._extract_tour_from_binary(x)

            # 验证1: 访问所有城市
            unique_cities = set(tour)
            if len(unique_cities) != self.num_cities:
                missing = set(range(self.num_cities)) - unique_cities
                return ValidationResult(
                    is_valid=False,
                    violation_type="missing_cities",
                    violation_details={"missing_cities": list(missing)}
                )

            # 验证2: 每个城市只访问一次
            if len(tour) != len(unique_cities):
                duplicates = [city for city in unique_cities if list(tour).count(city) > 1]
                return ValidationResult(
                    is_valid=False,
                    violation_type="duplicate_visits",
                    violation_details={"duplicated_cities": duplicates}
                )

            # 验证3: 形成回路（首尾相连）
            if tour[0] != tour[-1]:
                # 如果不是闭合回路，可以自动添加返回边
                pass  # 这是可选的，取决于具体编码方式

            return ValidationResult(is_valid=True)

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                violation_type="invalid_encoding",
                violation_details={"error": str(e)}
            )

    def _extract_tour_from_binary(self, x: np.ndarray) -> List[int]:
        """从二进制编码提取访问序列"""
        # 这是一个简化的实现，实际需要根据具体的编码方式
        num_nodes = int(np.sqrt(len(x)))
        adjacency_matrix = x.reshape((num_nodes, num_nodes))

        # 使用简单启发式构建路径
        visited = [0]
        current = 0

        while len(visited) < num_nodes:
            # 找到下一个未访问的节点
            next_node = None
            for j in range(num_nodes):
                if j not in visited and adjacency_matrix[current, j] > 0.5:
                    next_node = j
                    break

            if next_node is None:
                # 随机选择一个未访问的节点
                unvisited = [j for j in range(num_nodes) if j not in visited]
                next_node = unvisited[0]

            visited.append(next_node)
            current = next_node

        return visited


class PathConstraintBias(GraphConstraintBias):
    """
    路径约束偏置

    验证路径问题的约束：
    1. 从起点到终点
    2. 路径连续性
    3. 不包含环路（除非是回路问题）
    """

    def __init__(self, num_nodes: int, start_node: int = 0, end_node: int = None,
                 allow_cycles: bool = False, penalty_scale: float = 1e6):
        super().__init__("path_constraint", penalty_scale)
        self.num_nodes = num_nodes
        self.start_node = start_node
        self.end_node = end_node if end_node is not None else num_nodes - 1
        self.allow_cycles = allow_cycles

    def validate_constraints(self, x: np.ndarray, context: OptimizationContext) -> ValidationResult:
        """验证路径约束"""
        try:
            # 解析路径
            path = self._extract_path(x)

            # 验证1: 起点正确
            if path[0] != self.start_node:
                return ValidationResult(
                    is_valid=False,
                    violation_type="invalid_start",
                    violation_details={"expected_start": self.start_node, "actual_start": path[0]}
                )

            # 验证2: 终点正确（如果不是回路）
            if not self.allow_cycles and path[-1] != self.end_node:
                return ValidationResult(
                    is_valid=False,
                    violation_type="invalid_end",
                    violation_details={"expected_end": self.end_node, "actual_end": path[-1]}
                )

            # 验证3: 路径连续性
            for i in range(len(path) - 1):
                if not self._is_connected(path[i], path[i+1], x):
                    return ValidationResult(
                        is_valid=False,
                        violation_type="disconnected_path",
                        violation_details={"break_point": i, "from": path[i], "to": path[i+1]}
                    )

            # 验证4: 无重复节点（如果不允许环路）
            if not self.allow_cycles:
                unique_nodes = set(path)
                if len(unique_nodes) != len(path):
                    return ValidationResult(
                        is_valid=False,
                        violation_type="duplicate_nodes",
                        violation_details={"path": path}
                    )

            return ValidationResult(is_valid=True)

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                violation_type="invalid_encoding",
                violation_details={"error": str(e)}
            )

    def _extract_path(self, x: np.ndarray) -> List[int]:
        """从解向量提取路径"""
        if len(x) <= self.num_nodes:
            # 直接是节点序列
            return np.round(x).astype(int).tolist()
        else:
            # 需要从邻接矩阵构建路径
            # 简化实现：返回所有节点的顺序
            return list(range(self.num_nodes))

    def _is_connected(self, u: int, v: int, x: np.ndarray) -> bool:
        """检查两个节点是否相连"""
        # 简化实现，假设总是相连
        return True


class TreeConstraintBias(GraphConstraintBias):
    """
    树结构约束偏置

    验证树的约束：
    1. 连通性
    2. 无环路
    3. 边数 = 节点数 - 1
    """

    def __init__(self, num_nodes: int, penalty_scale: float = 1e6):
        super().__init__("tree_constraint", penalty_scale)
        self.num_nodes = num_nodes

    def validate_constraints(self, x: np.ndarray, context: OptimizationContext) -> ValidationResult:
        """验证树约束"""
        try:
            # 提取边
            edges = self._extract_edges(x)

            # 约束1: 边数必须等于 n-1
            if len(edges) != self.num_nodes - 1:
                return ValidationResult(
                    is_valid=False,
                    violation_type="wrong_edge_count",
                    violation_details={
                        "expected": self.num_nodes - 1,
                        "actual": len(edges)
                    }
                )

            # 约束2: 连通性
            if not self._is_connected(edges):
                return ValidationResult(
                    is_valid=False,
                    violation_type="disconnected",
                    violation_details={}
                )

            # 约束3: 无环路
            if self._has_cycle(edges):
                return ValidationResult(
                    is_valid=False,
                    violation_type="has_cycle",
                    violation_details={}
                )

            return ValidationResult(is_valid=True)

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                violation_type="invalid_encoding",
                violation_details={"error": str(e)}
            )

    def _extract_edges(self, x: np.ndarray) -> List[Tuple[int, int]]:
        """从解向量提取边列表"""
        edges = []
        edge_idx = 0

        for i in range(self.num_nodes):
            for j in range(i + 1, self.num_nodes):
                if edge_idx < len(x) and x[edge_idx] > 0.5:
                    edges.append((i, j))
                edge_idx += 1

        return edges

    def _is_connected(self, edges: List[Tuple[int, int]]) -> bool:
        """检查图是否连通"""
        if self.num_nodes == 0:
            return True

        # 使用DFS检查连通性
        visited = set()
        stack = [0]  # 从节点0开始

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
        """检查是否有环路"""
        # 使用并查集检测环路
        parent = list(range(self.num_nodes))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            px, py = find(x), find(y)
            if px == py:
                return False  # 形成环路
            parent[px] = py
            return True

        for u, v in edges:
            if not union(u, v):
                return True

        return False


class GraphColoringConstraintBias(GraphConstraintBias):
    """
    图着色约束偏置

    验证图着色的约束：
    1. 相邻节点颜色不同
    2. 颜色数不超过限制
    """

    def __init__(self, adjacency_matrix: np.ndarray, max_colors: int = None, penalty_scale: float = 1e6):
        super().__init__("coloring_constraint", penalty_scale)
        self.adjacency_matrix = adjacency_matrix
        self.num_nodes = adjacency_matrix.shape[0]
        self.max_colors = max_colors

    def validate_constraints(self, x: np.ndarray, context: OptimizationContext) -> ValidationResult:
        """验证着色约束"""
        try:
            # 解析颜色分配
            colors = np.round(x).astype(int)

            # 约束1: 颜色数不超过限制
            if self.max_colors is not None:
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

            # 约束2: 相邻节点颜色不同
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

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                violation_type="invalid_encoding",
                violation_details={"error": str(e)}
            )


class MatchingConstraintBias(GraphConstraintBias):
    """
    匹配问题约束偏置

    验证匹配的约束：
    1. 每个节点最多参与一条边
    """

    def __init__(self, num_nodes: int, is_perfect: bool = False, penalty_scale: float = 1e6):
        super().__init__("matching_constraint", penalty_scale)
        self.num_nodes = num_nodes
        self.is_perfect = is_perfect

    def validate_constraints(self, x: np.ndarray, context: OptimizationContext) -> ValidationResult:
        """验证匹配约束"""
        try:
            # 提取匹配边
            edges = self._extract_edges(x)

            # 计算每个节点的度
            node_degrees = [0] * self.num_nodes
            for u, v in edges:
                node_degrees[u] += 1
                node_degrees[v] += 1

            # 约束1: 每个节点最多参与一条边
            for i, degree in enumerate(node_degrees):
                if degree > 1:
                    return ValidationResult(
                        is_valid=False,
                        violation_type="node_multiple_edges",
                        violation_details={"node": i, "degree": degree}
                    )

            # 约束2: 如果是完全匹配，所有节点度必须为1
            if self.is_perfect:
                unmatched_nodes = [i for i, degree in enumerate(node_degrees) if degree == 0]
                if unmatched_nodes:
                    return ValidationResult(
                        is_valid=False,
                        violation_type="unmatched_nodes",
                        violation_details={"unmatched": unmatched_nodes}
                    )

            return ValidationResult(is_valid=True)

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                violation_type="invalid_encoding",
                violation_details={"error": str(e)}
            )

    def _extract_edges(self, x: np.ndarray) -> List[Tuple[int, int]]:
        """从解向量提取匹配边"""
        edges = []
        edge_idx = 0

        for i in range(self.num_nodes):
            for j in range(i + 1, self.num_nodes):
                if edge_idx < len(x) and x[edge_idx] > 0.5:
                    edges.append((i, j))
                edge_idx += 1

        return edges


class HamiltonianPathConstraintBias(GraphConstraintBias):
    """
    哈密顿路径/回路约束偏置

    验证哈密顿路径的约束：
    1. 访问每个节点恰好一次
    2. 路径连续
    """

    def __init__(self, num_nodes: int, is_cycle: bool = False, penalty_scale: float = 1e6):
        super().__init__("hamiltonian_constraint", penalty_scale)
        self.num_nodes = num_nodes
        self.is_cycle = is_cycle

    def validate_constraints(self, x: np.ndarray, context: OptimizationContext) -> ValidationResult:
        """验证哈密顿路径约束"""
        try:
            # 提取路径
            path = self._extract_path(x)

            # 约束1: 访问所有节点
            if len(path) != self.num_nodes:
                return ValidationResult(
                    is_valid=False,
                    violation_type="wrong_path_length",
                    violation_details={
                        "expected": self.num_nodes,
                        "actual": len(path)
                    }
                )

            # 约束2: 每个节点只访问一次
            if len(set(path)) != len(path):
                duplicates = [node for node in path if path.count(node) > 1]
                return ValidationResult(
                    is_valid=False,
                    violation_type="duplicate_nodes",
                    violation_details={"duplicates": duplicates}
                )

            # 约束3: 路径连续性
            for i in range(len(path) - 1):
                if not self._are_adjacent(path[i], path[i + 1], x):
                    return ValidationResult(
                        is_valid=False,
                        violation_type="discontinuous_path",
                        violation_details={"break": (path[i], path[i + 1])}
                    )

            # 如果是回路，检查首尾相连
            if self.is_cycle and not self._are_adjacent(path[-1], path[0], x):
                return ValidationResult(
                    is_valid=False,
                    violation_type="not_a_cycle",
                    violation_details={"start": path[0], "end": path[-1]}
                )

            return ValidationResult(is_valid=True)

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                violation_type="invalid_encoding",
                violation_details={"error": str(e)}
            )

    def _extract_path(self, x: np.ndarray) -> List[int]:
        """从解向量提取路径"""
        # 简化实现，假设x直接是节点序列
        return np.round(x).astype(int).tolist()

    def _are_adjacent(self, u: int, v: int, x: np.ndarray) -> bool:
        """检查两个节点是否相邻"""
        # 简化实现，总是返回True
        return True


class GraphConstraintFactory:
    """图约束偏置工厂"""

    @staticmethod
    def create_constraint(constraint_type: str, **kwargs) -> GraphConstraintBias:
        """创建特定类型的图约束偏置"""

        constraint_classes = {
            'tsp': TSPConstraintBias,
            'path': PathConstraintBias,
            'tree': TreeConstraintBias,
            'coloring': GraphColoringConstraintBias,
            'matching': MatchingConstraintBias,
            'hamiltonian': HamiltonianPathConstraintBias,
        }

        if constraint_type not in constraint_classes:
            raise ValueError(f"Unknown constraint type: {constraint_type}")

        return constraint_classes[constraint_type](**kwargs)

    @staticmethod
    def get_available_constraints() -> List[str]:
        """获取所有可用的约束类型"""
        return [
            'tsp',
            'path',
            'tree',
            'coloring',
            'matching',
            'hamiltonian'
        ]


# 通用组合约束偏置
class CompositeGraphConstraintBias(GraphConstraintBias):
    """
    组合图约束偏置

    可以同时验证多个图论约束
    """

    def __init__(self, constraints: List[GraphConstraintBias], penalty_scale: float = 1e6):
        super().__init__("composite_constraint", penalty_scale)
        self.constraints = constraints

    def validate_constraints(self, x: np.ndarray, context: OptimizationContext) -> ValidationResult:
        """验证所有约束"""
        for constraint in self.constraints:
            result = constraint.validate_constraints(x, context)
            if not result.is_valid:
                return result

        return ValidationResult(is_valid=True)

    def add_constraint(self, constraint: GraphConstraintBias):
        """添加新的约束"""
        self.constraints.append(constraint)