"""
Bias贡献分析系统

自动记录和分析每个偏置的贡献，生成详细的报告。
这是偏置系统的核心功能，默认启用，零配置。
"""

import time
import json
from pathlib import Path
from typing import Dict, List, Any, Optional


class BiasAnalytics:
    """
    偏置贡献分析器

    功能：
    - 自动记录每个偏置的调用次数和贡献值
    - 分析偏置随时间的变化趋势
    - 检测偏置间的冲突和协同
    - 生成优化建议
    - 输出JSON和Markdown格式的报告
    """

    def __init__(self, output_dir: str = "bias_reports", enabled: bool = True):
        """
        初始化分析器

        Args:
            output_dir: 报告输出目录
            enabled: 是否启用分析（默认启用）
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.enabled = enabled
        self.detailed = False  # 是否记录每次调用的详细信息

    def generate_report(self, bias_manager, solver_result: Dict[str, Any]) -> str:
        """
        生成完整的贡献分析报告

        Args:
            bias_manager: UniversalBiasManager实例
            solver_result: 求解器结果

        Returns:
            报告文件路径
        """
        if not self.enabled:
            return ""

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"bias_report_{timestamp}.json"

        # 收集所有偏置的统计
        report_data = {
            'metadata': self._collect_metadata(solver_result),
            'summary': self._generate_summary(bias_manager),
            'algorithmic_biases': self._collect_bias_stats(
                bias_manager.algorithmic_manager if hasattr(bias_manager, 'algorithmic_manager') else None
            ),
            'domain_biases': self._collect_bias_stats(
                bias_manager.domain_manager if hasattr(bias_manager, 'domain_manager') else None
            ),
            'interactions': self._analyze_interactions(bias_manager),
            'recommendations': self._generate_recommendations(bias_manager)
        }

        # 保存JSON
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        # 生成Markdown报告
        md_file = self._generate_markdown_report(report_data, timestamp)

        # 打印摘要
        self._print_summary(report_data)

        return str(report_file)

    def _collect_metadata(self, solver_result: Dict[str, Any]) -> Dict[str, Any]:
        """收集元数据"""
        return {
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'solver_result': {
                'generation': solver_result.get('generation'),
                'time': solver_result.get('time'),
                'evaluation_count': solver_result.get('evaluation_count')
            }
        }

    def _generate_summary(self, bias_manager) -> Dict[str, Any]:
        """生成总体摘要"""
        all_biases = []

        # 收集算法偏置
        if hasattr(bias_manager, 'algorithmic_manager'):
            for bias in bias_manager.algorithmic_manager.biases.values():
                if bias.enabled and bias.usage_count > 0:
                    all_biases.append(bias)

        # 收集领域偏置
        if hasattr(bias_manager, 'domain_manager'):
            for bias in bias_manager.domain_manager.biases.values():
                if bias.enabled and bias.usage_count > 0:
                    all_biases.append(bias)

        if not all_biases:
            return {
                'total_enabled': 0,
                'total_contributions': 0.0,
                'message': 'No active biases with usage'
            }

        # 计算总贡献
        total_contribution = sum(b.total_bias_value for b in all_biases)

        # 排序
        sorted_biases = sorted(
            all_biases,
            key=lambda b: b.total_bias_value,
            reverse=True
        )

        return {
            'total_enabled': len(all_biases),
            'total_contributions': total_contribution,
            'top_contributor': sorted_biases[0].name if sorted_biases else None,
            'rankings': [
                {
                    'rank': i+1,
                    'name': b.name,
                    'contribution': b.total_bias_value,
                    'percentage': (b.total_bias_value / total_contribution * 100)
                                   if total_contribution > 0 else 0,
                    'weight': b.weight,
                    'usage_count': b.usage_count
                }
                for i, b in enumerate(sorted_biases)
            ]
        }

    def _collect_bias_stats(self, manager) -> List[Dict[str, Any]]:
        """收集管理器下所有偏置的统计"""
        if manager is None:
            return []

        stats = []
        for bias in manager.biases.values():
            stats.append(bias.get_statistics())
        return stats

    def _analyze_interactions(self, bias_manager) -> Dict[str, Any]:
        """分析偏置间的交互"""
        conflicts = []
        synergies = []

        # 检测算法偏置间的冲突
        if hasattr(bias_manager, 'algorithmic_manager'):
            algo_biases = bias_manager.algorithmic_manager.biases
            conv_bias = algo_biases.get('convergence')
            div_bias = algo_biases.get('diversity')

            # 收敛 vs 多样性冲突
            if conv_bias and div_bias and conv_bias.enabled and div_bias.enabled:
                if conv_bias.weight > 0.3 and div_bias.weight > 0.3:
                    conflicts.append({
                        'type': 'convergence_diversity_conflict',
                        'biases': ['convergence', 'diversity'],
                        'severity': 'high',
                        'message': '高收敛权重和高多样性权重可能相互抵消',
                        'suggestion': '建议收敛阶段增加收敛权重，探索阶段增加多样性权重'
                    })

            # SA + TS 协同
            sa_bias = algo_biases.get('simulated_annealing')
            ts_bias = algo_biases.get('tabu_search')
            if sa_bias and ts_bias and sa_bias.enabled and ts_bias.enabled:
                synergies.append({
                    'type': 'sa_ts_synergy',
                    'biases': ['simulated_annealing', 'tabu_search'],
                    'message': '模拟退火和禁忌搜索配合良好（全局+局部）'
                })

        return {
            'conflicts': conflicts,
            'synergies': synergies
        }

    def _generate_recommendations(self, bias_manager) -> List[str]:
        """生成优化建议"""
        recommendations = []

        # 检查未使用的偏置
        all_managers = []
        if hasattr(bias_manager, 'algorithmic_manager'):
            all_managers.append(bias_manager.algorithmic_manager)
        if hasattr(bias_manager, 'domain_manager'):
            all_managers.append(bias_manager.domain_manager)

        for manager in all_managers:
            for bias in manager.biases.values():
                if bias.enabled and bias.usage_count == 0:
                    recommendations.append(
                        f"⚠️ 偏置 '{bias.name}' 已启用但从未被调用，可能配置有误"
                    )

        # 检查权重失衡
        all_biases = []
        for manager in all_managers:
            for bias in manager.biases.values():
                if bias.enabled and bias.usage_count > 0:
                    all_biases.append(bias)

        if all_biases:
            max_weight = max(b.weight for b in all_biases)
            min_weight = min(b.weight for b in all_biases)

            if max_weight / (min_weight + 1e-10) > 10:
                recommendations.append(
                    f"💡 权重失衡严重（最大{max_weight:.2f} vs 最小{min_weight:.2f}），"
                    f"考虑调整平衡以发挥所有偏置的作用"
                )

        # 检查贡献率过低
        for bias in all_biases:
            if bias.usage_count > 100 and bias.get_average_bias() < 0.001:
                recommendations.append(
                    f"💡 偏置 '{bias.name}' 贡献率很低（{bias.get_average_bias():.6f}），"
                    f"{'考虑增加权重' if bias.weight < 1.0 else '考虑禁用'}"
                )

        # 检查领域偏置是否足够
        if hasattr(bias_manager, 'domain_manager'):
            domain_biases = [b for b in bias_manager.domain_manager.biases.values()
                           if b.enabled]
            if len(domain_biases) == 0:
                recommendations.append(
                    "ℹ️ 未启用任何领域偏置，可以考虑添加业务约束偏置"
                )

        return recommendations

    def _generate_markdown_report(self, report_data: Dict, timestamp: str) -> str:
        """生成Markdown格式的报告"""
        md_file = self.output_dir / f"bias_report_{timestamp}.md"

        lines = [
            "# Bias 贡献分析报告\n",
            f"**生成时间**: {report_data['metadata']['timestamp']}",
            f"**优化代数**: {report_data['metadata']['solver_result']['generation']}",
            f"**运行时长**: {report_data['metadata']['solver_result']['time']:.2f}秒",
            f"**评估次数**: {report_data['metadata']['solver_result']['evaluation_count']}\n",
            "---\n",
            "## 📊 总体摘要\n",
        ]

        summary = report_data['summary']
        if summary.get('message'):
            lines.append(f"*{summary['message']}*\n")
        else:
            lines.extend([
                f"- **启用偏置数量**: {summary['total_enabled']}",
                f"- **总贡献值**: {summary['total_contributions']:.2f}",
                f"- **最大贡献者**: {summary['top_contributor']}\n",
                "### 贡献排名\n",
                "| 排名 | 偏置名称 | 贡献值 | 占比 | 权重 | 调用次数 |",
                "|------|----------|--------|------|------|----------|",
            ])

            for ranking in summary['rankings']:
                lines.append(
                    f"| {ranking['rank']} | {ranking['name']} | "
                    f"{ranking['contribution']:.4f} | {ranking['percentage']:.1f}% | "
                    f"{ranking['weight']:.2f} | {ranking['usage_count']} |"
                )

        # 算法偏置详情
        if report_data['algorithmic_biases']:
            lines.extend([
                "\n---\n",
                "## 🔧 算法偏置详情\n",
            ])

            for bias_stat in report_data['algorithmic_biases']:
                lines.extend(self._format_bias_detail(bias_stat))

        # 领域偏置详情
        if report_data['domain_biases']:
            lines.extend([
                "\n---\n",
                "## 🎯 领域偏置详情\n",
            ])

            for bias_stat in report_data['domain_biases']:
                lines.extend(self._format_bias_detail(bias_stat))

        # 交互分析
        interactions = report_data['interactions']
        if interactions['conflicts'] or interactions['synergies']:
            lines.extend([
                "\n---\n",
                "## 🔗 偏置交互分析\n",
            ])

            if interactions['conflicts']:
                lines.append("### ⚠️ 潜在冲突\n")
                for conflict in interactions['conflicts']:
                    lines.extend([
                        f"**{conflict['type']}**: {conflict['message']}\n",
                        f"- 涉及偏置: {', '.join(conflict['biases'])}\n",
                        f"- 严重程度: {conflict['severity']}\n",
                        f"- 建议: {conflict.get('suggestion', '无')}\n"
                    ])

            if interactions['synergies']:
                lines.append("### ✅ 协同效应\n")
                for synergy in interactions['synergies']:
                    lines.extend([
                        f"**{synergy['type']}**: {synergy['message']}\n",
                        f"- 涉及偏置: {', '.join(synergy['biases'])}\n"
                    ])

        # 建议
        if report_data['recommendations']:
            lines.extend([
                "\n---\n",
                "## 💡 优化建议\n",
            ])
            for rec in report_data['recommendations']:
                lines.append(f"{rec}\n")

        # 写入文件
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return str(md_file)

    def _format_bias_detail(self, bias_stat: Dict[str, Any]) -> List[str]:
        """格式化单个偏置的详细信息"""
        name = bias_stat.get('name', 'Unknown')
        enabled = bias_stat.get('enabled', False)
        weight = bias_stat.get('weight', 0.0)

        lines = [
            f"### {name}\n",
            f"- **状态**: {'✅ 启用' if enabled else '❌ 禁用'}",
            f"- **权重**: {weight:.2f}",
        ]

        if bias_stat.get('usage_count', 0) == 0:
            lines.extend([
                f"- **使用次数**: 0 (未使用)\n",
            ])
            return lines

        # 有使用记录
        usage_count = bias_stat['usage_count']
        total_contrib = bias_stat['total_contribution']
        avg_contrib = bias_stat['average_contribution']

        lines.extend([
            f"- **使用次数**: {usage_count}",
            f"- **总贡献**: {total_contrib:.4f}",
            f"- **平均贡献**: {avg_contrib:.6f}\n",
        ])

        # 添加趋势信息
        per_gen_stats = bias_stat.get('per_generation_stats', [])
        if per_gen_stats:
            lines.append("#### 趋势分析\n")
            lines.append("| 代数 | 平均偏置 | 调用次数 | 最小值 | 最大值 | 标准差 |")
            lines.append("|------|----------|----------|--------|--------|--------|")

            # 每10代显示一次，避免太长
            for gen_stat in per_gen_stats[::max(1, len(per_gen_stats)//10)]:
                lines.append(
                    f"| {gen_stat['generation']} | {gen_stat['avg_bias']:.4f} | "
                    f"{gen_stat['call_count']} | {gen_stat['min_bias']:.4f} | "
                    f"{gen_stat['max_bias']:.4f} | {gen_stat['std_bias']:.4f} |"
                )

            lines.append("")

        return lines

    def _print_summary(self, report_data: Dict):
        """打印摘要到控制台"""
        print("\n" + "="*60)
        print("📊 Bias 贡献分析报告")
        print("="*60)

        summary = report_data['summary']
        if summary.get('message'):
            print(f"\n{summary['message']}")
        else:
            print(f"\n启用偏置: {summary['total_enabled']} 个")
            print(f"总贡献值: {summary['total_contributions']:.2f}")
            print(f"最大贡献者: {summary['top_contributor']}")

            print("\n🏆 TOP 3 贡献者:")
            for ranking in summary['rankings'][:3]:
                print(f"  {ranking['rank']}. {ranking['name']}: "
                      f"{ranking['contribution']:.2f} ({ranking['percentage']:.1f}%)")

        # 打印建议
        if report_data['recommendations']:
            print("\n💡 优化建议:")
            for rec in report_data['recommendations'][:5]:  # 最多显示5条
                print(f"  {rec}")

        print("\n" + "="*60)
