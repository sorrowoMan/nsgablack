"""
图偏置(Graph Bias)系统 - 将图论问题的结构特性编码到优化算法中

Graph Bias System - Encoding structural properties of graph problems into optimization algorithms

主要特性:
- 支持多种图结构表示(邻接矩阵、边列表、邻接表)
- 实现常见图论问题的专用偏置
- 可扩展的图偏置框架
- 与现有偏置系统无缝集成

Key Features:
- Support multiple graph representations (adjacency matrix, edge list, adjacency list)
- Implement specialized biases for common graph problems
- Extensible graph bias framework
- Seamless integration with existing bias system
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Union, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
try:
    import networkx as nx
except Exception:  # optional dependency
    nx = None
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import shortest_path, minimum_spanning_tree

from ...core.base import AlgorithmicBias, DomainBias, OptimizationContext


@dataclass
class GraphStructure:
    """图结构的数据类，支持多种表示方式"""

    # 图的基本信息
    num_nodes: int
    num_edges: int
    directed: bool = False
    weighted: bool = False

    # 不同的表示方式
    adjacency_matrix: Optional[np.ndarray] = None  # 邻接矩阵
    edge_list: Optional[List[Tuple[int, int, float]]] = None  # 边列表 (u, v, weight)
    adjacency_list: Optional[Dict[int, List[Tuple[int, float]]]] = None  # 邻接表

    # 图的属性
    node_attributes: Optional[Dict[int, Dict[str, Any]]] = None  # 节点属性
    edge_attributes: Optional[Dict[Tuple[int, int], Dict[str, Any]]] = None  # 边属性

    def __post_init__(self):
        """自动补全不同的表示方式"""
        if self.adjacency_matrix is None and self.edge_list is not None:
            self._build_adjacency_matrix_from_edges()
        elif self.edge_list is None and self.adjacency_matrix is not None:
            self._build_edge_list_from_matrix()

    def _build_adjacency_matrix_from_edges(self):
        """从边列表构建邻接矩阵"""
        self.adjacency_matrix = np.zeros((self.num_nodes, self.num_nodes))
        for u, v, weight in self.edge_list:
            self.adjacency_matrix[u, v] = weight
            if not self.directed:
                self.adjacency_matrix[v, u] = weight

    def _build_edge_list_from_edges(self):
        """从邻接矩阵构建边列表"""
        self.edge_list = []
        for i in range(self.num_nodes):
            for j in range(self.num_nodes):
                if self.adjacency_matrix[i, j] != 0:
                    self.edge_list.append((i, j, self.adjacency_matrix[i, j]))


class GraphUtils:
    """图操作工具类"""

    @staticmethod
    def compute_graph_properties(graph: GraphStructure) -> Dict[str, float]:
        """计算图的基本性质"""
        props = {}

        if graph.adjacency_matrix is not None:
            # 度数统计
            degrees = np.sum(graph.adjacency_matrix > 0, axis=1)
            props['avg_degree'] = np.mean(degrees)
            props['max_degree'] = np.max(degrees)
            props['min_degree'] = np.min(degrees)
            props['degree_variance'] = np.var(degrees)

            # 密度
            max_edges = graph.num_nodes * (graph.num_nodes - 1) / (2 if not graph.directed else 1)
            props['density'] = graph.num_edges / max_edges

            # 聚类系数（基于三角形的局部聚类）
            props['avg_clustering'] = GraphUtils._compute_clustering_coefficient(graph)

        return props

    @staticmethod
    def _compute_clustering_coefficient(graph: GraphStructure) -> float:
        """计算平均聚类系数"""
        if graph.adjacency_matrix is None:
            return 0.0

        n = graph.num_nodes
        clustering_coeffs = []

        for i in range(n):
            # 获取节点i的邻居
            neighbors = np.where(graph.adjacency_matrix[i] > 0)[0]
            k = len(neighbors)

            if k < 2:
                clustering_coeffs.append(0.0)
                continue

            # 计算邻居之间的连接数
            neighbor_edges = 0
            for j_idx in range(k):
                for k_idx in range(j_idx + 1, k):
                    j, k_neighbor = neighbors[j_idx], neighbors[k_idx]
                    if graph.adjacency_matrix[j, k_neighbor] > 0:
                        neighbor_edges += 1

            # 聚类系数
            clustering = 2 * neighbor_edges / (k * (k - 1)) if not graph.directed else neighbor_edges / (k * (k - 1))
            clustering_coeffs.append(clustering)

        return np.mean(clustering_coeffs)

    @staticmethod
    def extract_subgraph(solution: np.ndarray, graph: GraphStructure) -> GraphStructure:
        """从解向量中提取子图"""
        # 假设解向量的每个元素对应图中的一条边是否被选择
        selected_edges = []
        edge_idx = 0

        for i in range(graph.num_nodes):
            for j in range(i + 1, graph.num_nodes):  # 避免重复边
                if edge_idx < len(solution) and solution[edge_idx] > 0.5:  # 二进制决策
                    weight = graph.adjacency_matrix[i, j] if graph.adjacency_matrix is not None else 1.0
                    selected_edges.append((i, j, weight))
                edge_idx += 1

        return GraphStructure(
            num_nodes=graph.num_nodes,
            num_edges=len(selected_edges),
            directed=graph.directed,
            weighted=graph.weighted,
            edge_list=selected_edges
        )


class GraphBias(DomainBias):
    """图偏置的基类"""
    context_requires = ("problem_data",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: problem_data; outputs scalar bias only."



    def __init__(self, name: str, graph: GraphStructure, weight: float = 1.0):
        super().__init__(name, weight)
        self.graph = graph
        self.graph_properties = GraphUtils.compute_graph_properties(graph)

    def encode_solution_to_graph(self, x: np.ndarray) -> GraphStructure:
        """将解向量编码为图结构"""
        return GraphUtils.extract_subgraph(x, self.graph)


class ConnectivityBias(GraphBias):
    """连通性偏置 - 鼓励生成连通的子图"""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "No explicit context dependency; outputs scalar bias only."



    def __init__(self, graph: GraphStructure, weight: float = 2.0):
        super().__init__("connectivity", graph, weight)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        subgraph = self.encode_solution_to_graph(x)

        if subgraph.num_edges == 0:
            return -self.weight * 10.0  # 严重惩罚空图

        # 使用NetworkX检查连通性
        try:
            if subgraph.edge_list:
                G = nx.Graph()
                G.add_weighted_edges_from(subgraph.edge_list)

                if nx.is_connected(G):
                    # 奖励连通图，连通组件越多惩罚越大
                    return self.weight * 1.0
                else:
                    components = nx.number_connected_components(G)
                    penalty = components - 1
                    return -self.weight * penalty
            else:
                return -self.weight * 10.0
        except:
            return -self.weight * 5.0


class SparsityBias(GraphBias):
    """稀疏性偏置 - 控制子图的边的数量"""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "No explicit context dependency; outputs scalar bias only."



    def __init__(self, graph: GraphStructure, target_density: float = 0.1, weight: float = 1.0):
        super().__init__("sparsity", graph, weight)
        self.target_density = target_density
        self.target_edges = int(target_density * graph.num_nodes * (graph.num_nodes - 1) / 2)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        subgraph = self.encode_solution_to_graph(x)

        # 计算边数偏差
        edge_diff = abs(subgraph.num_edges - self.target_edges)

        # 使用指数衰减函数，偏离目标越多惩罚越大
        penalty = np.exp(edge_diff / max(self.target_edges, 1)) - 1

        return -self.weight * penalty


class DegreeDistributionBias(GraphBias):
    """度分布偏置 - 鼓励特定的度分布模式"""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "No explicit context dependency; outputs scalar bias only."



    def __init__(self, graph: GraphStructure, target_degree_pattern: str = "uniform",
                 weight: float = 1.0):
        super().__init__("degree_distribution", graph, weight)
        self.target_pattern = target_degree_pattern

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        subgraph = self.encode_solution_to_graph(x)

        if subgraph.adjacency_matrix is None:
            return 0.0

        degrees = np.sum(subgraph.adjacency_matrix > 0, axis=1)

        if self.target_pattern == "uniform":
            # 鼓励均匀度分布
            degree_variance = np.var(degrees)
            return -self.weight * degree_variance

        elif self.target_pattern == "scale_free":
            # 鼓励无标度网络特性（少数节点高度数）
            degrees_sorted = np.sort(degrees)[::-1]  # 降序
            if degrees_sorted[0] > 0:
                # 计算度分布的Gini系数
                gini = self._compute_gini_coefficient(degrees_sorted)
                return self.weight * gini  # Gini系数越高，分布越不均匀
            return 0.0

        elif self.target_pattern == "small_world":
            # 鼓励小世界网络特性（高聚类系数）
            clustering = GraphUtils._compute_clustering_coefficient(subgraph)
            return self.weight * clustering

        return 0.0

    def _compute_gini_coefficient(self, values: np.ndarray) -> float:
        """计算基尼系数"""
        if np.all(values == values[0]):
            return 0.0

        values = np.sort(values)
        n = len(values)
        index = np.arange(1, n + 1)
        gini = (2 * np.sum(index * values)) / (n * np.sum(values)) - (n + 1) / n
        return gini


class ShortestPathBias(GraphBias):
    """最短路径偏置 - 针对最短路径问题的专用偏置"""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "No explicit context dependency; outputs scalar bias only."



    def __init__(self, graph: GraphStructure, source: int, target: int,
                 weight: float = 2.0):
        super().__init__("shortest_path", graph, weight)
        self.source = source
        self.target = target

        # 预计算参考最短路径
        if graph.adjacency_matrix is not None:
            try:
                distances = shortest_path(
                    csgraph=csr_matrix(graph.adjacency_matrix),
                    directed=graph.directed,
                    unweighted=False,
                    return_predecessors=False
                )
                self.reference_distance = distances[source, target]
            except:
                self.reference_distance = float('inf')
        else:
            self.reference_distance = float('inf')

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        subgraph = self.encode_solution_to_graph(x)

        if subgraph.num_edges == 0:
            return -self.weight * 100.0

        # 使用NetworkX计算最短路径
        try:
            if subgraph.edge_list:
                G = nx.Graph()
                G.add_weighted_edges_from(subgraph.edge_list)

                if nx.has_path(G, self.source, self.target):
                    path_length = nx.shortest_path_length(G, self.source, self.target, weight='weight')

                    # 奖励比参考路径更短的路径
                    if path_length < self.reference_distance:
                        improvement = self.reference_distance - path_length
                        return self.weight * improvement
                    else:
                        # 惩罚过长的路径
                        return -self.weight * (path_length - self.reference_distance)
                else:
                    return -self.weight * 50.0  # 惩罚不连通的情况
        except:
            pass

        return -self.weight * 100.0


class MaxFlowBias(GraphBias):
    """最大流偏置 - 针对最大流问题的专用偏置"""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "No explicit context dependency; outputs scalar bias only."



    def __init__(self, graph: GraphStructure, source: int, sink: int,
                 weight: float = 2.0):
        super().__init__("max_flow", graph, weight)
        self.source = source
        self.sink = sink

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        subgraph = self.encode_solution_to_graph(x)

        if subgraph.num_edges == 0:
            return -self.weight * 100.0

        try:
            if subgraph.edge_list:
                G = nx.DiGraph() if self.graph.directed else nx.Graph()

                # 将权重转换为容量（假设边权重表示容量）
                for u, v, weight in subgraph.edge_list:
                    capacity = max(weight, 1.0)  # 确保容量至少为1
                    G.add_edge(u, v, capacity=capacity)

                # 计算最大流
                flow_value, _ = nx.maximum_flow(G, self.source, self.sink)

                # 奖励更大的流值
                return self.weight * flow_value
        except:
            pass

        return -self.weight * 100.0


class GraphColoringBias(GraphBias):
    """图着色偏置 - 针对图着色问题的专用偏置"""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "No explicit context dependency; outputs scalar bias only."



    def __init__(self, graph: GraphStructure, max_colors: int = 4,
                 weight: float = 2.0):
        super().__init__("graph_coloring", graph, weight)
        self.max_colors = max_colors

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        # 假设解向量编码了每个节点的颜色
        if len(x) != self.graph.num_nodes:
            return -self.weight * 100.0

        colors = np.round(x).astype(int) % self.max_colors
        conflicts = 0

        if self.graph.adjacency_matrix is not None:
            for i in range(self.graph.num_nodes):
                for j in range(i + 1, self.graph.num_nodes):
                    if self.graph.adjacency_matrix[i, j] > 0:  # 存在边
                        if colors[i] == colors[j]:  # 颜色冲突
                            conflicts += 1

        # 惩罚颜色冲突
        return -self.weight * conflicts

    def encode_solution_to_graph(self, x: np.ndarray) -> GraphStructure:
        """重写以适应着色问题的编码方式"""
        # 对于着色问题，解向量直接编码颜色，不需要提取子图
        return self.graph  # 返回原图


class CommunityDetectionBias(GraphBias):
    """社区检测偏置 - 鼓励模块化结构"""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "No explicit context dependency; outputs scalar bias only."



    def __init__(self, graph: GraphStructure, expected_communities: int = 3,
                 weight: float = 1.0):
        super().__init__("community_detection", graph, weight)
        self.expected_communities = expected_communities

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        # 假设解向量编码了每个节点的社区归属
        if len(x) != self.graph.num_nodes:
            return -self.weight * 100.0

        communities = np.round(x).astype(int) % self.expected_communities

        # 计算模块度 (Modularity)
        if self.graph.adjacency_matrix is not None:
            modularity = self._compute_modularity(communities)
            return self.weight * modularity

        return 0.0

    def _compute_modularity(self, communities: np.ndarray) -> float:
        """计算网络的模块度"""
        if self.graph.adjacency_matrix is None:
            return 0.0

        m = self.graph.num_edges  # 总边数
        if m == 0:
            return 0.0

        modularity = 0.0

        for i in range(self.graph.num_nodes):
            for j in range(self.graph.num_nodes):
                if communities[i] == communities[j]:
                    A_ij = self.graph.adjacency_matrix[i, j]
                    k_i = np.sum(self.graph.adjacency_matrix[i, :] > 0)
                    k_j = np.sum(self.graph.adjacency_matrix[:, j] > 0)
                    modularity += A_ij - (k_i * k_j) / (2 * m)

        return modularity / (2 * m)


class GraphBiasFactory:
    """图偏置工厂类"""

    @staticmethod
    def create_bias(bias_type: str, graph: GraphStructure, **kwargs) -> GraphBias:
        """创建特定类型的图偏置"""

        bias_classes = {
            'connectivity': ConnectivityBias,
            'sparsity': SparsityBias,
            'degree_distribution': DegreeDistributionBias,
            'shortest_path': ShortestPathBias,
            'max_flow': MaxFlowBias,
            'graph_coloring': GraphColoringBias,
            'community_detection': CommunityDetectionBias,
        }

        if bias_type not in bias_classes:
            raise ValueError(f"Unknown graph bias type: {bias_type}")

        return bias_classes[bias_type](graph, **kwargs)

    @staticmethod
    def get_available_biases() -> List[str]:
        """获取所有可用的图偏置类型"""
        return [
            'connectivity',
            'sparsity',
            'degree_distribution',
            'shortest_path',
            'max_flow',
            'graph_coloring',
            'community_detection'
        ]


# 预定义的图偏置模板
GRAPH_BIAS_TEMPLATES = {
    'spanning_tree': {
        'biases': [
            {'type': 'connectivity', 'weight': 3.0},
            {'type': 'sparsity', 'target_density': 0.05, 'weight': 2.0}
        ],
        'description': '生成最小生成树或类似的稀疏连通子图'
    },

    'clustering': {
        'biases': [
            {'type': 'degree_distribution', 'target_degree_pattern': 'small_world', 'weight': 2.0},
            {'type': 'community_detection', 'expected_communities': 3, 'weight': 1.5}
        ],
        'description': '生成具有明显聚类结构的图'
    },

    'network_design': {
        'biases': [
            {'type': 'connectivity', 'weight': 2.5},
            {'type': 'degree_distribution', 'target_degree_pattern': 'scale_free', 'weight': 1.5},
            {'type': 'sparsity', 'target_density': 0.15, 'weight': 1.0}
        ],
        'description': '设计高效的网络拓扑结构'
    },

    'shortest_path_optimization': {
        'biases': [
            {'type': 'shortest_path', 'source': 0, 'target': -1, 'weight': 3.0},
            {'type': 'sparsity', 'target_density': 0.1, 'weight': 1.0}
        ],
        'description': '优化两点间的最短路径'
    }
}
