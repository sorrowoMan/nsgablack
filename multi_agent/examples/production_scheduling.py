"""
生产调度多智能体优化示例

展示如何使用多智能体系统解决生产调度问题
"""

import sys
import os
import time
import numpy as np
import matplotlib.pyplot as plt

# 添加路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from nsgablack.multi_agent import MultiAgentOptimizer, AgentRole, get_bias_profile
from produce_plan_simplified import ProductionSchedulingProblem, load_data


def run_production_scheduling_example():
    """运行生产调度示例"""
    print("=" * 80)
    print("生产调度多智能体优化示例")
    print("=" * 80)

    # 加载数据
    print("[1] 加载生产数据...")
    machine_ids, machine_bom, inventory_data, weights, days, _ = load_data()

    if machine_ids is None:
        print("错误: 无法加载数据")
        return

    print(f"  - 机器数量: {len(machine_ids)}")
    print(f"  - 计划天数: {days}")

    # 创建生产调度问题
    print("[2] 创建生产调度问题...")
    problem = ProductionSchedulingProblem(
        machine_ids=machine_ids,
        machine_bom=machine_bom,
        inventory_data=inventory_data,
        weights=weights,
        days=days,
        max_machines_per_day=6,  # 减小问题规模
        use_bias_system=True
    )

    # 配置多智能体优化器
    print("[3] 配置多智能体优化器...")

    # 为不同角色创建偏置配置
    config = {
        'total_population': 200,
        'max_generations': 80,
        'communication_interval': 5,
        'adaptation_interval': 15,
        'dynamic_ratios': True,
        'agent_config': {
            AgentRole.EXPLORER: {
                'ratio': 0.3,
                'bias_profile': get_bias_profile('explorer_default'),
                'description': '发现新的生产模式'
            },
            AgentRole.EXPLOITER: {
                'ratio': 0.35,
                'bias_profile': get_bias_profile('exploiter_default'),
                'description': '优化已知的高效生产方案'
            },
            AgentRole.WAITER: {
                'ratio': 0.2,
                'bias_profile': get_bias_profile('waiter_default'),
                'description': '学习最佳实践和模式'
            },
            AgentRole.COORDINATOR: {
                'ratio': 0.15,
                'bias_profile': get_bias_profile('coordinator_default'),
                'description': '协调全局生产策略'
            }
        },
        'bias_system': {
            'enabled': True,
            'dynamic_adjustment': True,
            'learning_enabled': True
        },
        'visualization': {
            'enabled': True,
            'save_plots': True,
            'real_time': False
        }
    }

    # 创建优化器
    optimizer = MultiAgentOptimizer(problem, config)

    # 运行优化
    print("[4] 开始多智能体优化...")
    start_time = time.time()

    try:
        results = optimizer.optimize()

        end_time = time.time()
        print(f"[5] 优化完成！")
        print(f"  - 耗时: {end_time - start_time:.2f} 秒")
        print(f"  - 找到 {len(results['pareto_front'])} 个Pareto最优解")

        # 分析结果
        analyze_results(results, problem)

        # 可视化结果
        visualize_production_results(results, problem, optimizer)

        # 保存结果
        save_results(results, problem, end_time - start_time)

    except Exception as e:
        print(f"优化过程中出错: {e}")
        import traceback
        traceback.print_exc()


def analyze_results(results: dict, problem):
    """分析优化结果"""
    print("\n" + "=" * 60)
    print("结果分析")
    print("=" * 60)

    # 全局最优解分析
    if results.get('global_best'):
        best = results['global_best']
        print(f"\n[全局最优解]")
        print(f"  目标值: {best['objectives']}")
        print(f"  约束违背: {sum(abs(c) for c in (best.get('constraints', []))):.4f}")

        # 解码生产计划
        plan = problem._decode(best['solution'])
        total_production = sum(1 for day in plan for m in day if m in problem.machine_bom)
        print(f"  总生产次数: {total_production}")

    # 智能体贡献分析
    print(f"\n[智能体贡献分析]")
    agent_stats = results.get('agent_statistics', {})
    for role, stats in agent_stats.items():
        if stats:
            avg_contribution = np.mean(stats.get('contributions', [0]))
            best_contribution = np.min(stats.get('best_objectives', [float('inf')]))
            print(f"  {role}:")
            print(f"    平均贡献: {avg_contribution:.4f}")
            print(f"    最佳目标: {best_contribution:.4f}")

    # 偏置系统性能
    print(f"\n[偏置系统性能]")
    bias_stats = results.get('bias_statistics', {})
    if bias_stats:
        print(f"  动态调整次数: {bias_stats.get('adaptations', 0)}")
        print(f"  平均偏置更新时间: {bias_stats.get('avg_update_time', 0):.4f}秒")


def visualize_production_results(results: dict, problem, optimizer):
    """可视化生产调度结果"""
    print("\n[可视化] 生成生产调度图表...")

    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    # 1. Pareto前沿
    pareto_front = results.get('pareto_front', [])
    if len(pareto_front) > 1:
        obj_array = np.array([p['objectives'] for p in pareto_front])
        axes[0, 0].scatter(obj_array[:, 0], obj_array[:, 1], alpha=0.6, s=50)
        if results.get('global_best'):
            best_obj = results['global_best']['objectives']
            axes[0, 0].scatter(best_obj[0], best_obj[1], color='red', s=200, marker='*', label='最优解')
        axes[0, 0].set_xlabel('物料剩余')
        axes[0, 0].set_ylabel('产量方差')
        axes[0, 0].set_title('Pareto前沿')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)

    # 2. 智能体角色贡献
    role_colors = {
        'explorer': 'red',
        'exploiter': 'blue',
        'waiter': 'green',
        'coordinator': 'purple'
    }
    agent_stats = results.get('agent_statistics', {})

    for role, stats in agent_stats.items():
        if stats and 'contributions' in stats:
            contributions = stats['contributions']
            color = role_colors.get(role, 'gray')
            axes[0, 1].plot(contributions, color=color, label=role, linewidth=2)

    axes[0, 1].set_xlabel('记录点')
    axes[0, 1].set_ylabel('贡献度')
    axes[0, 1].set_title('智能体角色贡献变化')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)

    # 3. 多样性变化
    diversity_history = results.get('diversity_history', [])
    if diversity_history:
        axes[0, 2].plot(diversity_history, 'b-', linewidth=2)
        axes[0, 2].set_xlabel('进化代数')
        axes[0, 2].set_ylabel('种群多样性')
        axes[0, 2].set_title('多样性变化趋势')
        axes[0, 2].grid(True, alpha=0.3)

    # 4. 最优解生产计划热力图
    if results.get('global_best'):
        best_solution = results['global_best']['solution']
        best_plan = problem._decode(best_solution)

        production_matrix = np.zeros((problem.days, len(problem.machine_ids)))
        for d, day_plan in enumerate(best_plan):
            for machine_id in day_plan:
                if machine_id in problem.machine_ids:
                    m_idx = problem.machine_ids.index(machine_id)
                    production_matrix[d, m_idx] += 1

        im = axes[1, 0].imshow(production_matrix.T, cmap='YlOrRd', aspect='auto')
        axes[1, 0].set_xlabel('天数')
        axes[1, 0].set_ylabel('机器类型')
        axes[1, 0].set_title('最优生产计划')
        plt.colorbar(im, ax=axes[1, 0])

    # 5. 每日生产量
    if results.get('global_best'):
        best_plan = problem._decode(results['global_best']['solution'])
        daily_production = []
        for day_plan in best_plan:
            count = sum(1 for m in day_plan if m in problem.machine_bom)
            daily_production.append(count)

        axes[1, 1].bar(range(len(daily_production)), daily_production)
        axes[1, 1].set_xlabel('天数')
        axes[1, 1].set_ylabel('生产次数')
        axes[1, 1].set_title('每日生产量分布')

    # 6. 收敛曲线
    best_history = results.get('best_objective_history', [])
    if best_history:
        best_values = [np.mean(obj) for obj in best_history]
        axes[1, 2].plot(best_values, 'r-', linewidth=2)
        axes[1, 2].set_xlabel('进化代数')
        axes[1, 2].set_ylabel('平均目标值')
        axes[1, 2].set_title('收敛曲线')
        axes[1, 2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('production_multi_agent_example_results.png', dpi=150, bbox_inches='tight')
    print("[可视化] 图表已保存为 production_multi_agent_example_results.png")


def save_results(results: dict, problem, elapsed_time: float):
    """保存结果"""
    import json
    import pandas as pd
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 保存详细结果
    save_data = {
        'timestamp': timestamp,
        'elapsed_time': elapsed_time,
        'problem_info': {
            'machine_count': len(problem.machine_ids),
            'days': problem.days,
            'max_machines_per_day': problem.max_machines_per_day
        },
        'optimization_config': results.get('config', {}),
        'statistics': {
            'total_evaluations': results.get('total_evaluations', 0),
            'communications': results.get('communications', 0),
            'adaptations': results.get('adaptations', 0)
        },
        'pareto_front_size': len(results.get('pareto_front', [])),
        'pareto_front': [
            {
                'objectives': entry['objectives'],
                'constraints': entry.get('constraints', [])
            }
            for entry in results.get('pareto_front', [])
        ],
        'global_best': results.get('global_best'),
        'agent_statistics': results.get('agent_statistics', {}),
        'bias_statistics': results.get('bias_statistics', {})
    }

    # 保存JSON文件
    json_filename = f'production_ma_result_{timestamp}.json'
    try:
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        print(f"[保存] 结果已保存到: {json_filename}")
    except Exception as e:
        print(f"[保存] JSON保存失败: {e}")

    # 保存生产计划
    if results.get('global_best'):
        best_plan = problem._decode(results['global_best']['solution'])
        plan_data = []

        for d, day_plan in enumerate(best_plan):
            for m, machine_id in enumerate(day_plan):
                plan_data.append({
                    'day': d + 1,
                    'slot': m + 1,
                    'machine_id': machine_id,
                    'valid': machine_id in problem.machine_bom
                })

        plan_df = pd.DataFrame(plan_data)
        plan_filename = f'production_plan_{timestamp}.csv'
        try:
            plan_df.to_csv(plan_filename, index=False, encoding='utf-8')
            print(f"[保存] 生产计划已保存到: {plan_filename}")
        except Exception as e:
            print(f"[保存] 生产计划保存失败: {e}")


def demonstrate_bias_system():
    """演示偏置系统的作用"""
    print("\n" + "=" * 80)
    print("偏置系统演示")
    print("=" * 80)

    # 创建简单问题
    from nsgablack.multi_agent.core.role import RoleRegistry
    from nsgablack.multi_agent.bias.profiles import BiasLibrary

    print("[1] 预定义偏置配置:")
    for profile_name in BiasLibrary.list_profiles():
        profile = BiasLibrary.get_profile(profile_name)
        print(f"  - {profile_name}: {profile.description}")

    print("\n[2] 角色特性:")
    for role in RoleRegistry.get_all_roles():
        characteristics = RoleRegistry.get_characteristics(role)
        if characteristics:
            print(f"  - {role.value}:")
            print(f"    探索率: {characteristics.exploration_rate:.2f}")
            print(f"    开发率: {characteristics.exploitation_rate:.2f}")
            print(f"    学习率: {characteristics.learning_rate:.2f}")

    print("\n[3] 动态偏置调整演示:")
    from nsgablack.multi_agent.bias.profiles import DynamicBiasProfile

    # 创建动态偏置
    base_profile = BiasLibrary.get_profile('explorer_default')
    dynamic_profile = DynamicBiasProfile(
        name="demo_dynamic",
        parameters=base_profile.parameters.copy(),
        adaptation_rate=0.2
    )

    print("  初始参数:")
    for key, value in dynamic_profile.parameters.items():
        print(f"    {key}: {value:.3f}")

    # 模拟反馈
    print("\n  模拟优化反馈...")
    for i in range(5):
        feedback = {
            'performance_improvement': np.random.uniform(-0.1, 0.2),
            'diversity': np.random.uniform(0.3, 0.9),
            'constraint_satisfaction': np.random.uniform(0.7, 1.0)
        }
        dynamic_profile.update_from_feedback(feedback, i)

        if i == 2:
            dynamic_profile.adapt_for_stage('middle')
        elif i == 4:
            dynamic_profile.adapt_for_stage('late')

    print("\n  调整后参数:")
    for key, value in dynamic_profile.parameters.items():
        print(f"    {key}: {value:.3f}")

    print(f"\n  学习率: {dynamic_profile.learning_rate:.4f}")
    print(f"  当前阶段: {dynamic_profile.current_stage}")


def main():
    """主函数"""
    try:
        # 运行生产调度示例
        run_production_scheduling_example()

        # 演示偏置系统
        demonstrate_bias_system()

        print("\n" + "=" * 80)
        print("示例运行完成！")
        print("=" * 80)

    except Exception as e:
        print(f"\n[错误] 运行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()