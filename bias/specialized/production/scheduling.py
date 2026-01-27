"""
生产调度偏置实现模块

该模块提供专门针对生产调度问题的偏置实现，用于：
- 处理复杂的生产约束和工艺要求
- 优化生产连续性和设备利用率
- 平衡多个相互冲突的生产目标
- 集成历史数据和专家知识

生产调度偏置的特点：
- 硬约束：必须满足的生产能力和资源限制
- 软约束：尽量满足的工艺和质量要求
- 多目标：同时优化成本、时间、质量等指标
- 动态性：生产环境变化时的快速响应

适用场景：
- 制造业生产排程
- 流程工业调度
- 项目管理优化
- 资源分配问题
"""

import numpy as np
from typing import List, Dict, Any, Callable

# 导入核心偏置类
from ...core.manager import UniversalBiasManager
from ...core.base import OptimizationContext, DomainBias, AlgorithmicBias
from ...domain.constraint import ConstraintBias
from ...algorithmic.diversity import DiversityBias

# 尝试导入贝叶斯偏置（可选）
try:
    from ...specialized.bayesian import BayesianGuidanceBias, BayesianExplorationBias
except ImportError:
    BayesianGuidanceBias = None
    BayesianExplorationBias = None


class ProductionSchedulingBiasManager:
    """
    生产调度偏置管理器 - 专门处理生产调度优化问题

    该管理器整合了多种生产调度专用的偏置，包括：
    - 生产约束偏置：处理设备产能、物料限制等硬约束
    - 连续生产偏置：减少换线成本，提高生产效率
    - 多样性偏置：避免生产方案过早收敛
    - 贝叶斯引导偏置：基于历史数据智能引导搜索

    核心功能：
    1. 约束满足：确保调度方案符合生产实际限制
    2. 成本优化：最小化换线、停工等生产成本
    3. 效率提升：最大化设备利用率和生产连续性
    4. 质量保证：满足工艺和质量要求
    """

    def __init__(self, machine_bom, inventory_data, machine_ids, days,
                 max_machines_per_day=8):
        """
        初始化生产调度偏置管理器

        Args:
            machine_bom: 机器物料清单（设备产能和工艺要求）
            inventory_data: 库存数据（原材料和成品库存）
            machine_ids: 设备ID列表
            days: 调度天数
            max_machines_per_day: 每天最大并行设备数
        """
        self.machine_bom = machine_bom                     # 设备物料清单
        self.inventory_data = inventory_data               # 库存数据
        self.machine_ids = machine_ids                     # 设备ID列表
        self.days = days                                   # 调度天数
        self.max_machines_per_day = max_machines_per_day  # 每日最大设备数

        # 创建通用偏置管理器
        self.bias_manager = UniversalBiasManager()

        # 设置偏置权重平衡
        # 提高算法偏置权重，因为贝叶斯引导需要更多权重发挥作用
        self._configure_bias_weights()

        # 初始化各种专用偏置
        self._setup_constraints()       # 设置生产约束偏置
        self._setup_algorithmic_bias()  # 设置算法层面偏置

    def _configure_bias_weights(self):
        """配置偏置权重平衡"""
        try:
            # 方法1：使用字典参数设置
            self.bias_manager.set_bias_weights({
                'algorithmic': 0.5,  # 算法偏置权重（提高至0.5）
                'domain': 0.5        # 领域偏置权重（约束处理）
            })
        except (TypeError, AttributeError):
            try:
                # 方法2：直接设置属性
                self.bias_manager.bias_weights = {
                    'algorithmic': 0.5,
                    'domain': 0.5
                }
            except (TypeError, AttributeError):
                # 方法3：使用单独的方法
                try:
                    self.bias_manager.set_bias_weights(0.5, 0.5)
                except:
                    print("警告：无法设置偏置权重，将使用默认值")

    def _setup_constraints(self):
        """设置生产调度的约束偏置"""
        # 创建约束偏置
        constraint_bias = ProductionConstraintBias(
            self.machine_bom,
            self.inventory_data,
            self.machine_ids,
            self.days,
            self.max_machines_per_day
        )
        self.bias_manager.domain_manager.add_bias(constraint_bias)

    def _setup_algorithmic_bias(self):
        """设置算法层面的偏置"""
        # 添加多样性偏置，避免早熟收敛
        diversity_bias = ProductionDiversityBias(weight=0.15)
        self.bias_manager.algorithmic_manager.add_bias(diversity_bias)

        # 添加连续生产偏置，减少换线成本
        continuity_bias = ProductionContinuityBias(
            self.machine_ids,
            self.days,
            weight=0.25
        )
        self.bias_manager.algorithmic_manager.add_bias(continuity_bias)

        # 添加贝叶斯引导偏置，基于历史搜索信息智能引导
        try:
            bayesian_guidance = BayesianGuidanceBias(
                weight=0.4,  # 较高权重，因为贝叶斯引导很重要
                buffer_size=100,  # 保存更多历史点用于建模
                acquisition='ei',  # Expected Improvement获取函数
                kernel='matern',  # Matern核函数适合生产调度的不连续性
                adaptive_weight=True,  # 自适应调整权重
                exploration_factor=0.15  # 适度的探索倾向
            )
            self.bias_manager.algorithmic_manager.add_bias(bayesian_guidance)
            print("已添加贝叶斯引导偏置")
        except Exception as e:
            print(f"贝叶斯引导偏置添加失败: {e}，继续使用其他偏置")

        # 添加贝叶斯探索偏置，专注于发现新的生产模式
        try:
            bayesian_exploration = BayesianExplorationBias(
                weight=0.2,  # 中等权重，鼓励探索
                uncertainty_threshold=0.1,  # 不确定性阈值
                decay_rate=0.95  # 权重衰减率
            )
            self.bias_manager.algorithmic_manager.add_bias(bayesian_exploration)
            print("已添加贝叶斯探索偏置")
        except Exception as e:
            print(f"贝叶斯探索偏置添加失败: {e}，继续使用其他偏置")

    def compute_bias(self, x: np.ndarray, context: OptimizationContext) -> float:
        """计算总偏置值"""
        return self.bias_manager.compute_total_bias(x, context)


class ProductionConstraintBias(DomainBias):
    """生产调度约束偏置"""

    def __init__(self, machine_bom, inventory_data, machine_ids, days,
                 max_machines_per_day=8, weight=1.0):
        super().__init__("production_constraints", weight)
        self.machine_bom = machine_bom
        self.inventory_data = inventory_data
        self.machine_ids = machine_ids
        self.num_machines = len(machine_ids)
        self.days = days
        self.max_machines_per_day = max_machines_per_day

        # 初始化物料信息
        self._setup_material_info()

    def _setup_material_info(self):
        """设置物料使用信息"""
        self.material_users = {}
        self.active_materials = set()

        for m_idx, m_id in enumerate(self.machine_ids):
            for mat in self.machine_bom.get(m_id, []):
                self.active_materials.add(mat)
                if mat not in self.material_users:
                    self.material_users[mat] = []
                self.material_users[mat].append(m_idx)

        self.active_materials_list = list(self.active_materials)

    def _decode_plan(self, x: np.ndarray) -> np.ndarray:
        """解码生产计划"""
        x_reshaped = x.reshape((self.num_machines, self.days))
        plan = np.round(x_reshaped).astype(int)
        return plan

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        改进的偏置计算：硬性约束排除 + 整数解引导

        策略：
        1. 硬性约束违反：返回极大值，完全排除不可行解
        2. 整数解引导：鼓励接近整数的解
        3. 软约束：渐进式优化
        """
        plan = self._decode_plan(x)

        # === 硬性约束检查：违反则返回极大值 ===
        # 1. 硬约束：机器数量约束（每天最多8个机种）
        machine_violations = self._compute_machine_constraint_violations(plan)
        if machine_violations > 0:
            return float(1e15)  # 极大惩罚，完全排除

        # 2. 硬约束：物料库存约束（不允许负库存）
        material_shortage = self._compute_material_shortage(plan)
        if material_shortage > 0:
            return float(1e15)  # 极大惩罚，完全排除

        # === 整数解引导 ===
        # 鼓励解向量接近整数（减少后续四舍五入的影响）
        integer_penalty = self._compute_integer_penalty(x)

        # === 软约束优化（仅在可行解中考虑）===
        total_penalty = integer_penalty

        # 3. 软约束：生产平滑性（避免产量大幅波动）
        smoothness_penalty = self._compute_smoothness_violation(plan)
        total_penalty += smoothness_penalty * 10.0  # 中等权重

        # 4. 软约束：最小批量（避免碎片化生产）
        # 小于最小批量的生产会被惩罚
        batch_violation = self._compute_batch_violation(plan)
        total_penalty += batch_violation * 5.0  # 较低权重

        # 5. 偏好约束：生产连续性奖励
        # 连续生产天数越多，奖励越大（负惩罚）
        continuity_reward = self._compute_continuity_reward(plan)
        total_penalty -= continuity_reward * 1.0  # 奖励（负惩罚）

        return self.weight * total_penalty

    def _compute_integer_penalty(self, x: np.ndarray) -> float:
        """
        计算整数惩罚：鼓励解向量接近整数

        策略：
        - 对于每个维度，计算其与最近整数的距离
        - 距离越小，惩罚越低
        - 使用平滑的惩罚函数，避免梯度突变
        """
        # 计算每个元素与最近整数的距离
        fractional_part = np.abs(x - np.round(x))

        # 使用平滑的惩罚函数：距离的平方
        # 距离为0时惩罚为0，距离为0.5时惩罚为0.25
        integer_penalty = np.sum(fractional_part ** 2)

        # 可选：加权某些维度的整数要求
        # 例如，某些机器类型更需要整数解
        # 这里暂时统一处理

        return integer_penalty

    def _compute_machine_constraint_violations(self, plan: np.ndarray) -> float:
        """计算机器数量约束违反（超出限制的机种数）"""
        daily_active = np.sum(plan > 0, axis=0)
        # 计算每天超出8个机种的数量
        violations = np.maximum(0, daily_active - self.max_machines_per_day)
        return float(np.sum(violations))

    def _compute_material_shortage(self, plan: np.ndarray) -> float:
        """计算物料短缺总量"""
        total_shortage = 0.0
        current_stock = {mat: self.inventory_data[mat]['initial']
                        for mat in self.active_materials_list}

        for t in range(self.days):
            # 每日入库
            for mat in self.active_materials_list:
                if t < len(self.inventory_data[mat]['inbound']):
                    current_stock[mat] += self.inventory_data[mat]['inbound'][t]

            # 计算每日消耗和短缺
            for mat in self.active_materials_list:
                users = self.material_users.get(mat, [])
                if users:
                    demand = np.sum(plan[users, t])
                    if demand > current_stock[mat]:
                        total_shortage += (demand - current_stock[mat])
                        current_stock[mat] = 0
                    else:
                        current_stock[mat] -= demand

        return total_shortage

    def _compute_smoothness_violation(self, plan: np.ndarray) -> float:
        """计算生产平滑性违反（相邻天产量变化）"""
        daily_production = np.sum(plan, axis=0)
        # 计算相邻天产量的绝对差
        production_changes = np.abs(np.diff(daily_production))
        # 大的变化会被惩罚
        large_changes = np.maximum(0, production_changes - np.mean(daily_production) * 0.3)
        return float(np.sum(large_changes))

    def _compute_batch_violation(self, plan: np.ndarray) -> float:
        """计算最小批量违反"""
        min_batch_size = 50
        # 找出所有大于0但小于最小批量的生产
        small_batches = plan[(plan > 0) & (plan < min_batch_size)]
        return float(np.sum(small_batches))

    def _compute_continuity_reward(self, plan: np.ndarray) -> float:
        """计算生产连续性奖励"""
        total_continuous_days = 0
        for m_idx in range(plan.shape[0]):
            # 计算每个机种的连续生产段
            continuous_segments = self._count_continuous_segments(plan[m_idx, :])
            total_continuous_days += continuous_segments
        return total_continuous_days

    def _count_continuous_segments(self, machine_series: np.ndarray) -> int:
        """计算连续生产段的总天数"""
        total = 0
        current = 0
        for val in machine_series:
            if val > 0:
                current += 1
            else:
                total += current
                current = 0
        total += current
        return total

  

class ProductionDiversityBias(AlgorithmicBias):
    """生产调度多样性偏置"""

    def __init__(self, weight=0.2):
        super().__init__("production_diversity", weight)
        self.diversity_threshold = 0.1  # 多样性阈值

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """促进解的多样性"""
        if context.population is None or len(context.population) == 0:
            return 0.0

        # 计算当前解与种群中其他解的平均距离
        distances = []
        for individual in context.population:
            # 使用欧氏距离
            dist = np.linalg.norm(x - individual)
            distances.append(dist)

        if distances:
            avg_distance = np.mean(distances)
            # 距离越大，多样性越高，奖励越多（负偏置）
            return -self.weight * avg_distance

        return 0.0


class ProductionContinuityBias(AlgorithmicBias):
    """生产连续性偏置，减少换线成本"""

    def __init__(self, machine_ids, days, weight=0.3):
        super().__init__("production_continuity", weight)
        self.machine_ids = machine_ids
        self.num_machines = len(machine_ids)
        self.days = days

    def _decode_plan(self, x: np.ndarray) -> np.ndarray:
        """解码生产计划"""
        x_reshaped = x.reshape((self.num_machines, self.days))
        plan = np.round(x_reshaped).astype(int)
        return plan

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """计算生产连续性奖励"""
        plan = self._decode_plan(x)
        total_reward = 0.0

        for m_idx in range(self.num_machines):
            # 计算每个机种的连续生产天数
            continuous_days = self._count_continuous_production_days(plan[m_idx, :])

            # 连续生产天数越多，奖励越多
            total_reward += continuous_days * 100

        # 奖励为负偏置（降低目标值）
        return -self.weight * total_reward

    def _count_continuous_production_days(self, machine_series: np.ndarray) -> int:
        """计算连续生产段的总天数"""
        total_continuous = 0
        current_streak = 0

        for day in range(len(machine_series)):
            if machine_series[day] > 0:
                # 检查是否连续
                if day == 0 or machine_series[day-1] > 0:
                    current_streak += 1
                else:
                    total_continuous += current_streak
                    current_streak = 1
            else:
                total_continuous += current_streak
                current_streak = 0

        total_continuous += current_streak
        return total_continuous


class ProductionOptimizationContext(OptimizationContext):
    """生产调度优化的上下文信息"""

    def __init__(self, generation: int, individual: np.ndarray,
                 population: List[np.ndarray] = None,
                 metrics: Dict[str, float] = None,
                 current_stock: Dict[str, float] = None,
                 day_index: int = None):
        super().__init__(generation, individual, population, metrics)
        self.current_stock = current_stock or {}
        self.day_index = day_index
        self.is_material_shortage = False
        self.is_over_capacity = False

    def check_constraint_violations(self, plan: np.ndarray, max_machines_per_day: int):
        """检查约束违反情况"""
        # 检查机器数量约束
        daily_active = np.sum(plan > 0, axis=0)
        self.is_over_capacity = np.any(daily_active > max_machines_per_day)

        # 可以添加更多约束检查
        # 例如：物料短缺检查等


class ProductionSchedulingBias:
    """简化的生产调度偏置类"""

    def __init__(self, domain_type="production_scheduling", adaptive=True):
        self.domain_type = domain_type
        self.adaptive = adaptive
        self.max_machines_per_day = 8
        self.min_production_per_machine = 100

    def apply(self, solution):
        """应用生产调度偏置到解"""
        if isinstance(solution, np.ndarray):
            schedule = solution.copy()
        else:
            schedule = np.array(solution)

        # 重塑为二维调度矩阵
        if len(schedule.shape) == 1:
            # 假设格式为 [machine1_day1, machine1_day2, ..., machine2_day1, ...]
            machines = 22
            days = 30
            schedule = schedule.reshape(machines, days)

        # 应用约束
        for day in range(schedule.shape[1]):
            daily_active = np.sum(schedule[:, day] > 0)
            if daily_active > self.max_machines_per_day:
                # 保留产量最高的机器
                machine_production = schedule[:, day]
                active_machines = np.where(machine_production > 0)[0]
                if len(active_machines) > 0:
                    productions = machine_production[active_machines]
                    top_indices = np.argsort(productions)[-self.max_machines_per_day:]
                    keep_machines = active_machines[top_indices]

                    # 将其他机器的生产量设为0
                    for machine in active_machines:
                        if machine not in keep_machines:
                            schedule[machine, day] = 0

        # 应用最小生产量约束
        for machine in range(schedule.shape[0]):
            for day in range(schedule.shape[1]):
                if 0 < schedule[machine, day] < self.min_production_per_machine:
                    schedule[machine, day] = 0

        return schedule.flatten()

    def validate(self, solution):
        """验证解是否满足约束"""
        if isinstance(solution, np.ndarray):
            schedule = solution.copy()
        else:
            schedule = np.array(solution)

        if len(schedule.shape) == 1:
            machines = 22
            days = 30
            schedule = schedule.reshape(machines, days)

        violations = 0
        for day in range(schedule.shape[1]):
            daily_active = np.sum(schedule[:, day] > 0)
            if daily_active > self.max_machines_per_day:
                violations += 1

        return violations == 0


# 便捷函数：创建生产调度偏置系统
def create_production_bias_system(machine_bom, inventory_data, machine_ids, days,
                                 max_machines_per_day=8) -> ProductionSchedulingBiasManager:
    """创建生产调度偏置系统的便捷函数"""
    return ProductionSchedulingBiasManager(
        machine_bom, inventory_data, machine_ids, days, max_machines_per_day
    )