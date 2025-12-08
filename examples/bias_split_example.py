"""
偏置库分离示例 - Bias Library Split Example
演示如何使用分离后的偏置库系统

这个示例展示了偏置库 v2.0 的分离架构：
- bias_base.py: 基础类定义
- bias_library_algorithmic.py: 算法偏置实现
- bias_library_domain.py: 业务偏置实现
- bias_v2.py: 主要管理器和接口
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from bias_v2 import (
    UniversalBiasManager,
    OptimizationContext,
    create_bias_manager_from_template,
    print_bias_library_info
)

# 也可以直接从分离的库中导入
from bias_library_algorithmic import (
    DiversityBias, ConvergenceBias, ExplorationBias
)
from bias_library_domain import (
    ConstraintBias, PreferenceBias, EngineeringDesignBias
)


def demonstrate_split_bias_library():
    """演示分离后的偏置库功能"""

    print("=" * 60)
    print("偏置库分离示例 - Bias Library Split Example")
    print("=" * 60)

    # 1. 创建通用偏置管理器
    print("\n1. 创建通用偏置管理器...")
    manager = UniversalBiasManager()
    print(f"   [OK] 算法偏置权重: {manager.bias_weights['algorithmic']}")
    print(f"   [OK] 业务偏置权重: {manager.bias_weights['domain']}")

    # 2. 添加算法偏置
    print("\n2. 添加算法偏置...")
    diversity_bias = DiversityBias(weight=0.2)
    convergence_bias = ConvergenceBias(weight=0.1, early_gen=10, late_gen=50)

    manager.algorithmic_manager.add_bias(diversity_bias)
    manager.algorithmic_manager.add_bias(convergence_bias)
    print("   ✓ 已添加多样性偏置和收敛性偏置")

    # 3. 添加业务偏置
    print("\n3. 添加业务偏置...")
    constraint_bias = ConstraintBias(weight=2.0)

    # 添加一些示例约束
    def stress_constraint(x):
        """应力约束：应力应小于100"""
        stress = np.sum(x * x) * 10  # 简化的应力计算
        return max(0, stress - 100)

    def cost_constraint(x):
        """成本约束：成本应小于50"""
        cost = np.sum(np.abs(x)) * 5  # 简化的成本计算
        return max(0, cost - 50)

    constraint_bias.add_hard_constraint(stress_constraint)
    constraint_bias.add_soft_constraint(cost_constraint)

    manager.domain_manager.add_bias(constraint_bias)
    print("   ✓ 已添加约束偏置（应力硬约束，成本软约束）")

    # 4. 计算偏置值
    print("\n4. 测试偏置计算...")

    # 创建测试个体
    test_x = np.array([2.0, 3.0])

    # 创建优化上下文
    context = OptimizationContext(
        generation=25,  # 中期迭代
        individual=test_x,
        population=[
            np.array([1.0, 2.0]),
            np.array([2.5, 3.5]),
            np.array([1.8, 2.8])
        ]
    )

    # 计算总偏置
    total_bias = manager.compute_total_bias(test_x, context)
    print(f"   ✓ 测试个体: {test_x}")
    print(f"   ✓ 总偏置值: {total_bias:.4f}")

    # 分别计算算法偏置和业务偏置
    alg_bias = manager.algorithmic_manager.compute_algorithmic_bias(test_x, context)
    domain_bias = manager.domain_manager.compute_domain_bias(test_x, context)
    print(f"   ✓ 算法偏置: {alg_bias:.4f}")
    print(f"   ✓ 业务偏置: {domain_bias:.4f}")

    # 5. 动态调整权重
    print("\n5. 测试动态权重调整...")
    print(f"   调整前权重: 算法={manager.bias_weights['algorithmic']:.2f}, 业务={manager.bias_weights['domain']:.2f}")

    # 模拟陷入局部最优的情况
    optimization_state = {'is_stuck': True, 'is_violating_constraints': False}
    manager.adjust_weights(optimization_state)
    print(f"   陷入局部最优后: 算法={manager.bias_weights['algorithmic']:.2f}, 业务={manager.bias_weights['domain']:.2f}")

    # 模拟违反约束的情况
    optimization_state = {'is_stuck': False, 'is_violating_constraints': True}
    manager.adjust_weights(optimization_state)
    print(f"   违反约束后: 算法={manager.bias_weights['algorithmic']:.2f}, 业务={manager.bias_weights['domain']:.2f}")

    # 6. 使用模板创建偏置管理器
    print("\n6. 使用模板创建偏置管理器...")
    engineering_manager = create_bias_manager_from_template('basic_engineering')
    print("   ✓ 已创建基础工程设计模板")

    finance_manager = create_bias_manager_from_template('financial_optimization')
    print("   ✓ 已创建金融优化模板")

    ml_manager = create_bias_manager_from_template('machine_learning')
    print("   ✓ 已创建机器学习模板")

    # 7. 显示偏置库信息
    print("\n7. 偏置库信息:")
    print_bias_library_info()

    print("\n" + "=" * 60)
    print("✅ 偏置库分离示例完成!")
    print("✅ 所有功能正常工作!")
    print("=" * 60)


def demonstrate_individual_bias_usage():
    """演示单独使用分离的偏置库"""

    print("\n" + "=" * 60)
    print("独立偏置库使用示例")
    print("=" * 60)

    # 直接使用算法偏置
    print("\n1. 直接使用算法偏置...")
    diversity_bias = DiversityBias(weight=0.3, metric='euclidean')
    exploration_bias = ExplorationBias(weight=0.2, stagnation_threshold=15)

    context = OptimizationContext(
        generation=30,
        individual=np.array([1.0, 1.0]),
        population=[
            np.array([0.9, 1.1]),
            np.array([1.1, 0.9]),
            np.array([0.8, 1.2])
        ],
        metrics={'best_fitness': 0.95}
    )

    alg_bias1 = diversity_bias.compute(np.array([1.0, 1.0]), context)
    alg_bias2 = exploration_bias.compute(np.array([1.0, 1.0]), context)

    print(f"   ✓ 多样性偏置: {alg_bias1:.4f}")
    print(f"   ✓ 探索性偏置: {alg_bias2:.4f}")

    # 直接使用业务偏置
    print("\n2. 直接使用业务偏置...")
    preference_bias = PreferenceBias(weight=1.0)
    preference_bias.set_preference('performance', 'maximize', weight=2.0)
    preference_bias.set_preference('cost', 'minimize', weight=1.5)

    context_with_metrics = OptimizationContext(
        generation=30,
        individual=np.array([1.0, 1.0]),
        metrics={'performance': 0.85, 'cost': 120.0}
    )

    domain_bias = preference_bias.compute(np.array([1.0, 1.0]), context_with_metrics)
    print(f"   ✓ 偏好偏置: {domain_bias:.4f}")

    print("\n✅ 独立偏置库使用示例完成!")


if __name__ == "__main__":
    demonstrate_split_bias_library()
    demonstrate_individual_bias_usage()

    print("\n🎉 所有示例运行成功!")
    print("📚 偏置库已成功分离为:")
    print("   - bias_base.py: 基础类")
    print("   - bias_library_algorithmic.py: 算法偏置库")
    print("   - bias_library_domain.py: 业务偏置库")
    print("   - bias_v2.py: 主要接口和管理器")