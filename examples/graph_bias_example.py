"""
图偏置使用示例

本示例展示如何使用图偏置系统来解决各种图论优化问题，包括：
- 最小生成树问题
- 图着色问题
- 最短路径问题
- 社区检测问题
- 网络设计问题

Graph Bias Usage Examples

This example demonstrates how to use the graph bias system to solve various graph optimization problems.
"""

import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from typing import List, Tuple

# 导入图偏置系统
from bias import (
    GraphStructure, GraphUtils, GraphBiasFactory,
    ConnectivityBias, SparsityBias, DegreeDistributionBias,
    ShortestPathBias, MaxFlowBias, GraphColoringBias,
    CommunityDetectionBias, GRAPH_BIAS_TEMPLATES
)

# 导入核心优化算法
from core import BlackBoxSolverNSGAII
from core.problems import BlackBoxProblem


def create_sample_graph(num_nodes: int = 10, density: float = 0.3) -> GraphStructure:
    """创建一个示例图"""
    # 使用NetworkX生成随机图
    G = nx.erdos_renyi_graph(num_nodes, density)

    # 转换为边列表
    edge_list = []
    for u, v, data in G.edges(data=True):
        weight = np.random.uniform(1.0, 10.0)  # 随机权重
        edge_list.append((u, v, weight))

    return GraphStructure(
        num_nodes=num_nodes,
        num_edges=len(edge_list),
        directed=False,
        weighted=True,
        edge_list=edge_list
    )


def example_spanning_tree_optimization():
    """示例1：最小生成树优化"""
    print("=" * 60)
    print("示例1：最小生成树优化 (Spanning Tree Optimization)")
    print("=" * 60)

    # 创建图
    graph = create_sample_graph(num_nodes=8, density=0.4)

    # 使用预定义的生成树模板
    template = GRAPH_BIAS_TEMPLATES['spanning_tree']
    print(f"使用模板: {template['description']}")

    # 创建偏置
    biases = []
    for bias_config in template['biases']:
        bias = GraphBiasFactory.create_bias(
            bias_config['type'],
            graph,
            **{k: v for k, v in bias_config.items() if k not in ['type', 'weight']}
        )
        bias.weight = bias_config['weight']
        biases.append(bias)

    # 创建优化问题
    def spanning_tree_objective(x: np.ndarray) -> float:
        """目标函数：最小化总权重"""
        # 解码为边选择
        subgraph = GraphUtils.extract_subgraph(x, graph)

        # 计算总权重
        total_weight = sum(weight for _, _, weight in subgraph.edge_list)

        # 应用偏置
        total_bias = 0.0
        for bias in biases:
            # 这里需要创建一个模拟的OptimizationContext
            from bias_base import OptimizationContext
            context = OptimizationContext(
                generation=1,
                population_size=100,
                current_objective=total_weight
            )
            total_bias += bias.compute(x, context)

        # 目标是最小化权重，所以加上偏置（负偏置表示奖励）
        return total_weight + total_bias

    # 定义问题
    problem = BlackBoxProblem(
        name="spanning_tree",
        n_var=len(graph.edge_list),
        n_obj=1,
        n_constr=0,
        xl=0.0,
        xu=1.0,
        function=spanning_tree_objective
    )

    # 设置求解器
    solver = BlackBoxSolverNSGAII(problem)

    # 求解
    print("开始优化...")
    solver.run(max_gen=100)

    # 获取结果
    best_solution = solver.population[0]
    best_edges = []
    edge_idx = 0

    for i in range(graph.num_nodes):
        for j in range(i + 1, graph.num_nodes):
            if edge_idx < len(best_solution) and best_solution[edge_idx] > 0.5:
                weight = graph.adjacency_matrix[i, j] if graph.adjacency_matrix is not None else 1.0
                best_edges.append((i, j, weight))
            edge_idx += 1

    print(f"\n最优解包含 {len(best_edges)} 条边")
    print("边列表:", best_edges)

    # 验证连通性
    if best_edges:
        G = nx.Graph()
        G.add_weighted_edges_from(best_edges)
        if nx.is_connected(G):
            print("✓ 解是连通的")
            print(f"✓ 总权重: {sum(weight for _, _, weight in best_edges):.2f}")
        else:
            print("✗ 解不连通")


def example_graph_coloring():
    """示例2：图着色问题"""
    print("\n" + "=" * 60)
    print("示例2：图着色问题 (Graph Coloring)")
    print("=" * 60)

    # 创建图
    graph = create_sample_graph(num_nodes=12, density=0.3)

    # 创建着色偏置
    coloring_bias = GraphColoringBias(graph, max_colors=4, weight=2.0)

    # 优化目标：最小化使用的颜色数量
    def graph_coloring_objective(x: np.ndarray) -> float:
        """目标函数：最小化颜色冲突和颜色数量"""
        from bias_base import OptimizationContext
        context = OptimizationContext(
            generation=1,
            population_size=100,
            current_objective=len(np.unique(np.round(x).astype(int) % 4))
        )

        # 计算颜色冲突惩罚
        conflict_penalty = -coloring_bias.compute(x, context)

        # 计算使用的颜色数量
        colors = np.unique(np.round(x).astype(int) % 4)
        num_colors = len(colors)

        return num_colors + conflict_penalty

    # 定义问题
    problem = BlackBoxProblem(
        name="graph_coloring",
        n_var=graph.num_nodes,  # 每个节点一个颜色
        n_obj=1,
        n_constr=0,
        xl=0.0,
        xu=4.0,
        function=graph_coloring_objective
    )

    # 设置求解器
    solver = BlackBoxSolverNSGAII(problem)

    # 求解
    print("开始着色优化...")
    solver.run(max_gen=150)

    # 获取结果
    best_solution = solver.population[0]
    colors = np.round(best_solution).astype(int) % 4

    print(f"\n最优着色方案:")
    for i, color in enumerate(colors):
        print(f"节点 {i}: 颜色 {color}")

    print(f"使用的颜色数: {len(np.unique(colors))}")

    # 验证着色
    conflicts = 0
    for i in range(graph.num_nodes):
        for j in range(i + 1, graph.num_nodes):
            if graph.adjacency_matrix[i, j] > 0 and colors[i] == colors[j]:
                conflicts += 1
                print(f"冲突: 边 ({i}, {j}) 的两个节点都是颜色 {colors[i]}")

    if conflicts == 0:
        print("✓ 没有颜色冲突，找到了有效着色！")
    else:
        print(f"✗ 发现 {conflicts} 个颜色冲突")


def example_shortest_path():
    """示例3：最短路径优化"""
    print("\n" + "=" * 60)
    print("示例3：最短路径优化 (Shortest Path)")
    print("=" * 60)

    # 创建一个具有明显短路径的图
    num_nodes = 15
    G = nx.path_graph(num_nodes)  # 创建路径图

    # 添加一些额外的边
    extra_edges = [(0, 7), (3, 12), (5, 14), (8, 14)]
    for u, v in extra_edges:
        G.add_edge(u, v, weight=np.random.uniform(1.0, 3.0))

    # 设置边权重
    for u, v in G.edges():
        if G[u][v].get('weight') is None:
            G[u][v]['weight'] = np.random.uniform(1.0, 5.0)

    # 转换为图结构
    edge_list = [(u, v, G[u][v]['weight']) for u, v in G.edges()]
    graph = GraphStructure(
        num_nodes=num_nodes,
        num_edges=len(edge_list),
        directed=False,
        weighted=True,
        edge_list=edge_list
    )

    # 设置源点和目标点
    source, target = 0, 14

    # 创建最短路径偏置
    path_bias = ShortestPathBias(graph, source=source, target=target, weight=3.0)

    # 创建稀疏性偏置（避免选择太多边）
    sparsity_bias = SparsityBias(graph, target_density=0.1, weight=1.0)

    def shortest_path_objective(x: np.ndarray) -> float:
        """目标函数：最小化路径长度"""
        from bias_base import OptimizationContext
        context = OptimizationContext(
            generation=1,
            population_size=100,
            current_objective=0.0
        )

        # 应用偏置
        total_bias = 0.0
        total_bias += path_bias.compute(x, context)
        total_bias += sparsity_bias.compute(x, context)

        # 返回偏置值（偏置已经是负值，表示最小化目标）
        return -total_bias

    # 定义问题
    problem = BlackBoxProblem(
        name="shortest_path",
        n_var=len(graph.edge_list),
        n_obj=1,
        n_constr=0,
        xl=0.0,
        xu=1.0,
        function=shortest_path_objective
    )

    # 设置求解器
    solver = BlackBoxSolverNSGAII(problem)

    # 求解
    print(f"寻找从节点 {source} 到节点 {target} 的最短路径...")
    solver.run(max_gen=100)

    # 获取结果
    best_solution = solver.population[0]
    selected_edges = []
    edge_idx = 0

    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            if edge_idx < len(best_solution) and best_solution[edge_idx] > 0.5:
                # 查找对应的权重
                for u, v, weight in edge_list:
                    if (u == i and v == j) or (u == j and v == i):
                        selected_edges.append((i, j, weight))
                        break
            edge_idx += 1

    print(f"\n选中的路径包含 {len(selected_edges)} 条边")

    # 验证路径
    if selected_edges:
        path_G = nx.Graph()
        path_G.add_weighted_edges_from(selected_edges)

        if nx.has_path(path_G, source, target):
            path = nx.shortest_path(path_G, source, target, weight='weight')
            path_length = nx.shortest_path_length(path_G, source, target, weight='weight')
            print(f"✓ 找到路径: {path}")
            print(f"✓ 路径长度: {path_length:.2f}")
        else:
            print("✗ 没有找到从源点到目标点的路径")


def example_community_detection():
    """示例4：社区检测"""
    print("\n" + "=" * 60)
    print("示例4：社区检测 (Community Detection)")
    print("=" * 60)

    # 创建具有明显社区结构的图
    # 社区1: 节点 0-4
    # 社区2: 节点 5-9
    # 社区3: 节点 10-14
    communities = [
        list(range(0, 5)),
        list(range(5, 10)),
        list(range(10, 15))
    ]

    G = nx.Graph()
    G.add_nodes_from(range(15))

    # 社区内边（高密度）
    for comm in communities:
        for i in comm:
            for j in comm:
                if i < j and np.random.random() < 0.7:  # 70% 社区内连接
                    G.add_edge(i, j, weight=np.random.uniform(2.0, 5.0))

    # 社区间边（低密度）
    for i in range(15):
        for j in range(i + 1, 15):
            # 检查是否在不同社区
            in_same_comm = any(i in comm and j in comm for comm in communities)
            if not in_same_comm and np.random.random() < 0.1:  # 10% 社区间连接
                G.add_edge(i, j, weight=np.random.uniform(0.5, 1.5))

    # 转换为图结构
    edge_list = [(u, v, G[u][v]['weight']) for u, v in G.edges()]
    graph = GraphStructure(
        num_nodes=15,
        num_edges=len(edge_list),
        directed=False,
        weighted=True,
        edge_list=edge_list
    )

    # 创建社区检测偏置
    community_bias = CommunityDetectionBias(graph, expected_communities=3, weight=2.0)

    # 度分布偏置（鼓励异质性）
    degree_bias = DegreeDistributionBias(
        graph, target_degree_pattern="scale_free", weight=1.0
    )

    def community_detection_objective(x: np.ndarray) -> float:
        """目标函数：最大化模块度"""
        from bias_base import OptimizationContext
        context = OptimizationContext(
            generation=1,
            population_size=100,
            current_objective=0.0
        )

        # 计算总偏置（偏置值已经是我们要优化的目标）
        total_bias = community_bias.compute(x, context)
        total_bias += degree_bias.compute(x, context)

        # 返回负值因为我们要最大化模块度
        return -total_bias

    # 定义问题
    problem = BlackBoxProblem(
        name="community_detection",
        n_var=graph.num_nodes,  # 每个节点一个社区标签
        n_obj=1,
        n_constr=0,
        xl=0.0,
        xu=3.0,
        function=community_detection_objective
    )

    # 设置求解器
    solver = BlackBoxSolverNSGAII(problem)

    # 求解
    print("检测社区结构...")
    solver.run(max_gen=120)

    # 获取结果
    best_solution = solver.population[0]
    detected_communities = np.round(best_solution).astype(int) % 3

    print("\n检测结果:")
    for comm_id in range(3):
        nodes = [i for i, comm in enumerate(detected_communities) if comm == comm_id]
        print(f"社区 {comm_id}: {nodes}")

    # 与真实社区比较
    print("\n真实社区:")
    for i, comm in enumerate(communities):
        print(f"社区 {i}: {comm}")

    # 计算调整兰德指数（简单版本）
    from sklearn.metrics import adjusted_rand_score
    true_labels = []
    detected_labels = []

    for i in range(15):
        # 确定真实社区标签
        for j, comm in enumerate(communities):
            if i in comm:
                true_labels.append(j)
                break

        detected_labels.append(detected_communities[i])

    ari = adjusted_rand_score(true_labels, detected_labels)
    print(f"\n调整兰德指数: {ari:.3f}")
    if ari > 0.7:
        print("✓ 社区检测效果良好！")
    elif ari > 0.4:
        print("○ 社区检测效果一般")
    else:
        print("✗ 社区检测效果不佳")


def example_network_design():
    """示例5：网络设计问题"""
    print("\n" + "=" * 60)
    print("示例5：网络设计问题 (Network Design)")
    print("=" * 60)

    # 创建一个需要设计的网络
    num_nodes = 20
    G = nx.erdos_renyi_graph(num_nodes, 0.15)  # 稀疏初始图

    # 设置边权重
    for u, v in G.edges():
        G[u][v]['weight'] = np.random.uniform(1.0, 10.0)

    # 转换为图结构
    edge_list = [(u, v, G[u][v]['weight']) for u, v in G.edges()]
    graph = GraphStructure(
        num_nodes=num_nodes,
        num_edges=len(edge_list),
        directed=False,
        weighted=True,
        edge_list=edge_list
    )

    # 使用网络设计模板
    template = GRAPH_BIAS_TEMPLATES['network_design']
    print(f"使用网络设计模板: {template['description']}")

    # 创建偏置组合
    biases = []
    for bias_config in template['biases']:
        if bias_config['type'] == 'degree_distribution':
            bias = GraphBiasFactory.create_bias(
                bias_config['type'],
                graph,
                target_degree_pattern=bias_config['target_degree_pattern']
            )
        elif bias_config['type'] == 'sparsity':
            bias = GraphBiasFactory.create_bias(
                bias_config['type'],
                graph,
                target_density=bias_config['target_density']
            )
        else:
            bias = GraphBiasFactory.create_bias(bias_config['type'], graph)

        bias.weight = bias_config['weight']
        biases.append(bias)

    def network_design_objective(x: np.ndarray) -> float:
        """网络设计目标函数"""
        from bias_base import OptimizationContext
        context = OptimizationContext(
            generation=1,
            population_size=100,
            current_objective=0.0
        )

        # 计算网络成本（边权重之和）
        subgraph = GraphUtils.extract_subgraph(x, graph)
        total_cost = sum(weight for _, _, weight in subgraph.edge_list)

        # 应用所有偏置
        total_bias = sum(bias.compute(x, context) for bias in biases)

        # 平衡成本和网络质量
        return total_cost - total_bias  # 偏置是正数，表示奖励

    # 定义问题
    problem = BlackBoxProblem(
        name="network_design",
        n_var=len(graph.edge_list),
        n_obj=1,
        n_constr=0,
        xl=0.0,
        xu=1.0,
        function=network_design_objective
    )

    # 设置求解器
    solver = BlackBoxSolverNSGAII(problem)

    # 求解
    print("开始网络设计优化...")
    solver.run(max_gen=150)

    # 分析结果
    best_solution = solver.population[0]
    designed_graph = GraphUtils.extract_subgraph(best_solution, graph)

    print(f"\n设计的网络:")
    print(f"- 节点数: {graph.num_nodes}")
    print(f"- 选择的边数: {designed_graph.num_edges}")
    print(f"- 网络密度: {designed_graph.num_edges / (graph.num_nodes * (graph.num_nodes - 1) / 2):.3f}")

    # 计算网络性质
    if designed_graph.edge_list:
        G = nx.Graph()
        G.add_weighted_edges_from(designed_graph.edge_list)

        # 连通性
        is_connected = nx.is_connected(G)
        print(f"- 连通性: {'是' if is_connected else '否'}")

        # 平均度
        avg_degree = sum(dict(G.degree()).values()) / len(G.nodes())
        print(f"- 平均度: {avg_degree:.2f}")

        # 聚类系数
        clustering = nx.average_clustering(G)
        print(f"- 平均聚类系数: {clustering:.3f}")

        # 总成本
        total_cost = sum(weight for _, _, weight in designed_graph.edge_list)
        print(f"- 总建设成本: {total_cost:.2f}")


def main():
    """运行所有示例"""
    print("图偏置系统使用示例")
    print("Graph Bias System Usage Examples")
    print("=" * 60)

    # 运行各个示例
    try:
        example_spanning_tree_optimization()
    except Exception as e:
        print(f"生成树示例出错: {e}")

    try:
        example_graph_coloring()
    except Exception as e:
        print(f"图着色示例出错: {e}")

    try:
        example_shortest_path()
    except Exception as e:
        print(f"最短路径示例出错: {e}")

    try:
        example_community_detection()
    except Exception as e:
        print(f"社区检测示例出错: {e}")

    try:
        example_network_design()
    except Exception as e:
        print(f"网络设计示例出错: {e}")

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()