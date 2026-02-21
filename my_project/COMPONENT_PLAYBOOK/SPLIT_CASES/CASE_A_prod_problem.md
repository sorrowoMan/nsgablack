# Case A（真实排产）- Problem 逐行批注

来源：`examples/cases/production_scheduling/refactor_problem.py`

下面是**真实排产问题**核心片段，逐行解释：

```python
class ProductionSchedulingProblem(BlackBoxProblem):  # 排产问题类，继承框架标准问题接口
    def __init__(self, data: ProductionData, constraints: ProductionConstraints, name: str = "ProductionScheduling"):  # 构造函数
        self.data = data  # 保存原始数据（BOM、供应、权重等）
        self.constraints = constraints  # 保存约束参数
        self.machines = data.machines  # 机种数量
        self.materials = data.materials  # 物料数量
        self.days = data.days  # 天数
        self.matrix_shape = (self.machines, self.days)  # 排产矩阵形状
        self._bom_float = data.bom_matrix.astype(np.float32)  # 预转 float32，减少重复转换开销
        dimension = self.machines * self.days  # 决策变量是一维向量，长度=机种*天数
        bounds = {f"x{i}": [0, constraints.max_production_per_machine] for i in range(dimension)}  # 每个位置都限制在[0, max_prod]
        objectives = [f"f{i}" for i in range(self.get_num_objectives())]  # 根据是否启用 penalty objective 决定目标数量
        super().__init__(name=name, dimension=dimension, bounds=bounds, objectives=objectives)  # 注册到父类

    def decode_schedule(self, x: np.ndarray) -> np.ndarray:  # 把一维解向量还原成二维排产矩阵
        return np.asarray(x, dtype=float).reshape(self.machines, self.days)  # 形状=(machines, days)

    def _compute_material_shortage(self, schedule: np.ndarray) -> float:  # 逐天模拟库存与消耗
        current_stock = np.zeros(self.materials, dtype=np.float32)  # 当前库存
        total_shortage = 0.0  # 总缺料
        for day in range(self.days):  # 每天循环
            current_stock += self.data.supply_matrix[:, day]  # 当天来料入库
            consumption = schedule[:, day].astype(np.float32) @ self._bom_float  # 当天生产导致的物料消耗
            shortage = np.maximum(0.0, consumption - current_stock)  # 不足部分
            total_shortage += float(np.sum(shortage))  # 累加缺料量
            current_stock = np.maximum(0.0, current_stock - consumption)  # 扣库存，不能为负
        return total_shortage  # 返回总缺料

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:  # 约束违背向量
        schedule = self.decode_schedule(x)  # 向量 -> 矩阵
        comps = self._constraint_components(schedule)  # 计算各类违背量
        return np.array([  # 固定顺序输出，便于 bias/报告复用
            comps["material_shortage"],  # 缺料违背
            comps["excess_machines"],  # 超机器数违背
            comps["shortage_machines"],  # 少机器数违背（若硬约束启用）
            comps["below_min_production"],  # 低于最小产量违背
            comps["above_max_production"],  # 高于最大产量违背
        ], dtype=float)

    def evaluate(self, x: np.ndarray) -> np.ndarray:  # 目标函数
        schedule = self.decode_schedule(x)  # 解码
        total_production = float(np.sum(schedule))  # 总产量
        daily_production = np.sum(schedule, axis=0)  # 每日产量
        penalty = self._compute_penalty(schedule)  # 约束加权惩罚（软+硬）
        production_variance = np.var(daily_production) / ((np.mean(daily_production) + 1e-6) ** 2)  # 归一化方差
        return np.array([  # 多目标：产量最大化等价于最小化(-产量)
            -total_production,  # 目标0：越小越好 => 总产量越大越好
            penalty * float(self.penalty_objective_scale),  # 目标1：惩罚（缩放后）
            production_variance,  # 目标2：日间波动
        ], dtype=float)
```

## 这份真实 Problem 的关键点
- 把生产计划视为二维矩阵，但优化变量是扁平一维向量。
- 约束违背和目标是分开的：约束走 `evaluate_constraints`，目标走 `evaluate`。
- 缺料是通过“逐天库存仿真”计算出来，不是静态一次性计算。
