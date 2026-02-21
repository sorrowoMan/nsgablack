# refactor_pipeline.py 整文件逐行批注版

- 源文件。`nsgablack/examples/cases/production_scheduling/refactor_pipeline.py`
- 总行数。1300
- 说明：这是整文件逐行批注版（每一行都有解释，空行不标注）。

```text
0001 | # -*- coding: utf-8 -*- || 注释：解释当前代码段用途或工程约束。
0002 | """Representation pipeline pieces for production scheduling.""" || 文档字符串开始：说明模块或函数意图。
0003 | 
0004 | from __future__ import annotations || from 导入：按命名空间引入对象。
0005 | 
0006 | from dataclasses import dataclass || from 导入：按命名空间引入对象。
0007 | from typing import Optional || from 导入：按命名空间引入对象。
0008 | 
0009 | import sys || import 导入：引入模块。
0010 | from pathlib import Path || from 导入：按命名空间引入对象。
0011 | 
0012 | import numpy as np || import 导入：引入模块。
0013 | 
0014 | def _ensure_importable() -> None: || 调用导入兜底，确保可导入 nsgablack。
0015 |     try: || 异常保护开始。
0016 |         import nsgablack  # noqa: F401 || import 导入：引入模块。
0017 |         return || 执行语句。
0018 |     except Exception: || 异常处理分支。
0019 |         pass || 流程控制语句。
0020 |     repo_root = Path(__file__).resolve().parents[1] || 赋值语句。
0021 |     if str(repo_root) not in sys.path: || 条件分支。
0022 |         sys.path.insert(0, str(repo_root)) || 执行语句。
0023 | 
0024 | 
0025 | _ensure_importable() || 调用导入兜底，确保可导入 nsgablack。
0026 | 
0027 | from nsgablack.representation import RepresentationPipeline || from 导入：按命名空间引入对象。
0028 | 
0029 | try: || 异常保护开始。
0030 |     from nsgablack.utils.context.context_keys import KEY_MUTATION_SIGMA, KEY_VNS_K || from 导入：按命名空间引入对象。
0031 | except Exception: || 异常处理分支。
0032 |     KEY_MUTATION_SIGMA = "mutation_sigma" || 赋值语句。
0033 |     KEY_VNS_K = "vns_k" || 赋值语句。
0034 | 
0035 | 
0036 | @dataclass || 装饰器声明。
0037 | class ProductionScheduleInitializer: || 基础初始化器：按日随机激活机种并分配产量。
0038 |     machines: int || 执行语句。
0039 |     days: int || 执行语句。
0040 |     min_machines_per_day: int || 执行语句。
0041 |     max_machines_per_day: int || 执行语句。
0042 |     min_production_per_machine: int || 执行语句。
0043 |     max_production_per_machine: int || 执行语句。
0044 |     context_requires = () || 赋值语句。
0045 |     context_provides = () || 赋值语句。
0046 |     context_mutates = () || 赋值语句。
0047 |     context_cache = () || 赋值语句。
0048 |     context_notes = ("Uses constructor constraints/data only; no context I/O.",) || 赋值语句。
0049 | 
0050 |     def initialize(self, problem, context=None) -> np.ndarray: || 定义函数 `initialize`。
0051 |         schedule = np.zeros((self.machines, self.days), dtype=float) || 赋值语句。
0052 |         for day in range(self.days): || 循环遍历。
0053 |             if self.max_machines_per_day <= 0: || 条件分支。
0054 |                 continue || 流程控制语句。
0055 |             lower = max(0, self.min_machines_per_day) || 赋值语句。
0056 |             upper = max(lower, self.max_machines_per_day) || 赋值语句。
0057 |             active_count = int(np.random.randint(lower, upper + 1)) || 赋值语句。
0058 |             if active_count == 0: || 条件分支。
0059 |                 continue || 流程控制语句。
0060 |             active_idx = np.random.choice(self.machines, size=active_count, replace=False) || 赋值语句。
0061 |             production = np.random.randint( || 赋值语句。
0062 |                 self.min_production_per_machine, || 执行语句。
0063 |                 self.max_production_per_machine + 1, || 执行语句。
0064 |                 size=active_count, || 赋值语句。
0065 |             ) || 执行语句。
0066 |             schedule[active_idx, day] = production || 赋值语句。
0067 |         return schedule.reshape(-1) || 返回输出。
0068 | 
0069 | 
0070 | @dataclass || 装饰器声明。
0071 | class SupplyAwareInitializer: || 供应感知初始化器：结合 BOM/库存做可行初始化。
0072 |     machines: int || 执行语句。
0073 |     days: int || 执行语句。
0074 |     min_machines_per_day: int || 执行语句。
0075 |     max_machines_per_day: int || 执行语句。
0076 |     min_production_per_machine: int || 执行语句。
0077 |     max_production_per_machine: int || 执行语句。
0078 |     bom_matrix: np.ndarray || 执行语句。
0079 |     supply_matrix: np.ndarray || 执行语句。
0080 |     machine_weights: Optional[np.ndarray] = None || 赋值语句。
0081 |     soft_min_ratio: float = 0.2 || 赋值语句。
0082 |     min_prod_ratio: float = 0.02 || 赋值语句。
0083 |     min_prod_abs: int = 100 || 赋值语句。
0084 |     context_requires = () || 赋值语句。
0085 |     context_provides = () || 赋值语句。
0086 |     context_mutates = () || 赋值语句。
0087 |     context_cache = () || 赋值语句。
0088 |     context_notes = ("Supply-aware initializer reads constructor matrices; no context I/O.",) || 赋值语句。
0089 | 
0090 |     def initialize(self, problem, context=None) -> np.ndarray: || 定义函数 `initialize`。
0091 |         schedule = np.zeros((self.machines, self.days), dtype=float) || 赋值语句。
0092 |         current_stock = np.zeros(self.supply_matrix.shape[0], dtype=float) || 赋值语句。
0093 |         req_indices = [np.where(self.bom_matrix[m])[0] for m in range(self.machines)] || 赋值语句。
0094 |         base_soft_min = max(1, int(self.min_production_per_machine * self.soft_min_ratio)) || 赋值语句。
0095 |         weight_vec = ( || 赋值语句。
0096 |             np.asarray(self.machine_weights, dtype=float) || 赋值语句。
0097 |             if self.machine_weights is not None and len(self.machine_weights) == self.machines || 条件分支。
0098 |             else np.ones(self.machines, dtype=float) || 其他情况分支。
0099 |         ) || 执行语句。
0100 |         weight_vec = np.clip(weight_vec, 0.05, None) || 赋值语句。
0101 |         weight_norm = weight_vec / max(np.max(weight_vec), 1e-6) || 赋值语句。
0102 |         prev_active = np.zeros(self.machines, dtype=bool) || 赋值语句。
0103 | 
0104 |         for day in range(self.days): || 循环遍历。
0105 |             current_stock += self.supply_matrix[:, day] || 赋值语句。
0106 | 
0107 |             probs = weight_vec / np.sum(weight_vec) || 赋值语句。
0108 |             machine_order = np.random.choice(self.machines, size=self.machines, replace=False, p=probs) || 赋值语句。
0109 |             soft_min = base_soft_min || 赋值语句。
0110 |             chosen = [] || 赋值语句。
0111 |             availability = {} || 赋值语句。
0112 | 
0113 |             while True: || 条件循环。
0114 |                 feasible = [] || 赋值语句。
0115 |                 availability.clear() || 执行语句。
0116 |                 for m in machine_order: || 循环遍历。
0117 |                     req = req_indices[m] || 赋值语句。
0118 |                     if req.size == 0: || 条件分支。
0119 |                         feasible.append(m) || 执行语句。
0120 |                         availability[m] = float(self.max_production_per_machine) || 赋值语句。
0121 |                         continue || 流程控制语句。
0122 |                     avail = float(np.min(current_stock[req])) || 赋值语句。
0123 |                     if avail >= soft_min: || 条件分支。
0124 |                         feasible.append(m) || 执行语句。
0125 |                         availability[m] = avail || 赋值语句。
0126 | 
0127 |                 lower = max(0, self.min_machines_per_day) || 赋值语句。
0128 |                 upper = max(lower, min(self.max_machines_per_day, len(feasible))) || 赋值语句。
0129 |                 target = upper || 赋值语句。
0130 | 
0131 |                 feasible.sort( || 执行语句。
0132 |                     key=lambda idx: availability.get(idx, 0.0) * (0.5 + weight_norm[idx]), || 赋值语句。
0133 |                     reverse=True, || 赋值语句。
0134 |                 ) || 执行语句。
0135 |                 chosen = [] || 赋值语句。
0136 |                 for m in feasible: || 循环遍历。
0137 |                     if m in chosen: || 条件分支。
0138 |                         continue || 流程控制语句。
0139 |                     if prev_active[m]: || 条件分支。
0140 |                         chosen.append(m) || 执行语句。
0141 |                     if len(chosen) >= target: || 条件分支。
0142 |                         break || 流程控制语句。
0143 |                 if len(chosen) < target: || 条件分支。
0144 |                     for m in feasible: || 循环遍历。
0145 |                         if m in chosen: || 条件分支。
0146 |                             continue || 流程控制语句。
0147 |                         chosen.append(m) || 执行语句。
0148 |                         if len(chosen) >= target: || 条件分支。
0149 |                             break || 流程控制语句。
0150 | 
0151 |                 if len(chosen) >= lower or soft_min <= 1: || 条件分支。
0152 |                     break || 流程控制语句。
0153 |                 soft_min = max(1, soft_min // 2) || 赋值语句。
0154 | 
0155 |             if not chosen: || 条件分支。
0156 |                 continue || 流程控制语句。
0157 | 
0158 |             for m in chosen: || 循环遍历。
0159 |                 req = req_indices[m] || 赋值语句。
0160 |                 if req.size == 0: || 条件分支。
0161 |                     avail = float(self.max_production_per_machine) || 赋值语句。
0162 |                 else: || 其他情况分支。
0163 |                     avail = float(np.min(current_stock[req])) || 赋值语句。
0164 |                 if avail < soft_min: || 条件分支。
0165 |                     continue || 流程控制语句。
0166 |                 upper_prod = min(self.max_production_per_machine, int(avail)) || 赋值语句。
0167 |                 if upper_prod <= 0: || 条件分支。
0168 |                     continue || 流程控制语句。
0169 |                 low = min(self.min_production_per_machine, upper_prod) || 赋值语句。
0170 |                 low = max(1, low) || 赋值语句。
0171 |                 production = int(np.random.randint(low, upper_prod + 1)) || 赋值语句。
0172 |                 schedule[m, day] = production || 赋值语句。
0173 |                 if req.size > 0: || 条件分支。
0174 |                     current_stock[req] = np.maximum(0.0, current_stock[req] - production) || 赋值语句。
0175 | 
0176 |             # dynamic minimum production threshold || 注释：解释当前代码段用途或工程约束。
0177 |             day_total = float(np.sum(schedule[:, day])) || 赋值语句。
0178 |             threshold = max(self.min_prod_abs, self.min_prod_ratio * day_total) || 赋值语句。
0179 |             if threshold > 0: || 条件分支。
0180 |                 for m in list(chosen): || 循环遍历。
0181 |                     if schedule[m, day] < threshold: || 条件分支。
0182 |                         prod = schedule[m, day] || 赋值语句。
0183 |                         schedule[m, day] = 0.0 || 赋值语句。
0184 |                         req = req_indices[m] || 赋值语句。
0185 |                         if req.size > 0 and prod > 0: || 条件分支。
0186 |                             current_stock[req] = current_stock[req] + prod || 赋值语句。
0187 | 
0188 |             prev_active = schedule[:, day] > 0 || 赋值语句。
0189 | 
0190 |         return schedule.reshape(-1) || 返回输出。
0191 | 
0192 | 
0193 | @dataclass || 装饰器声明。
0194 | class ProductionScheduleMutation: || 排产变异器：支持 sigma 与 VNS 深度联动。
0195 |     sigma: float = 0.5 || 赋值语句。
0196 |     per_gene_rate: float = 0.05 || 赋值语句。
0197 |     toggle_rate: float = 0.02 || 赋值语句。
0198 |     max_production_per_machine: int = 3000 || 赋值语句。
0199 | 
0200 |     # VNS compatibility contract: VNSAdapter writes these keys into context. || 注释：解释当前代码段用途或工程约束。
0201 |     sigma_key: str = KEY_MUTATION_SIGMA || 赋值语句。
0202 |     k_key: str = KEY_VNS_K || 赋值语句。
0203 | 
0204 |     # Neighborhood-depth scaling (k -> stronger perturbation). || 注释：解释当前代码段用途或工程约束。
0205 |     k_sigma_scale: float = 0.18 || 赋值语句。
0206 |     k_rate_scale: float = 0.12 || 赋值语句。
0207 |     min_per_gene_rate: float = 0.01 || 赋值语句。
0208 |     max_per_gene_rate: float = 0.35 || 赋值语句。
0209 |     context_requires = () || 赋值语句。
0210 |     context_provides = () || 赋值语句。
0211 |     context_mutates = () || 赋值语句。
0212 |     context_cache = () || 赋值语句。
0213 |     context_notes = ( || 赋值语句。
0214 |         "Optionally reads mutation_sigma/vns_k from context when provided.", || 执行语句。
0215 |     ) || 执行语句。
0216 | 
0217 |     def _runtime_params(self, context=None) -> tuple[float, float]: || 从 context 解析运行时变异参数。
0218 |         sigma = float(self.sigma) || 赋值语句。
0219 |         per_gene_rate = float(self.per_gene_rate) || 赋值语句。
0220 |         if isinstance(context, dict): || 条件分支。
0221 |             raw_sigma = context.get(self.sigma_key) || 赋值语句。
0222 |             if raw_sigma is not None: || 条件分支。
0223 |                 try: || 异常保护开始。
0224 |                     sigma = max(1e-9, float(raw_sigma)) || 赋值语句。
0225 |                 except Exception: || 异常处理分支。
0226 |                     pass || 流程控制语句。
0227 | 
0228 |             raw_k = context.get(self.k_key) || 赋值语句。
0229 |             if raw_k is not None: || 条件分支。
0230 |                 try: || 异常保护开始。
0231 |                     k = max(0, int(raw_k)) || 赋值语句。
0232 |                     sigma *= 1.0 + float(self.k_sigma_scale) * float(k) || 赋值语句。
0233 |                     per_gene_rate *= 1.0 + float(self.k_rate_scale) * float(k) || 赋值语句。
0234 |                 except Exception: || 异常处理分支。
0235 |                     pass || 流程控制语句。
0236 | 
0237 |         per_gene_rate = float(np.clip(per_gene_rate, self.min_per_gene_rate, self.max_per_gene_rate)) || 赋值语句。
0238 |         return sigma, per_gene_rate || 返回输出。
0239 | 
0240 |     def mutate(self, x: np.ndarray, context=None) -> np.ndarray: || 定义函数 `mutate`。
0241 |         vec = np.array(x, dtype=float, copy=True) || 赋值语句。
0242 |         if vec.size == 0: || 条件分支。
0243 |             return vec || 返回输出。
0244 | 
0245 |         sigma, per_gene_rate = self._runtime_params(context) || 赋值语句。
0246 | 
0247 |         mask = np.random.rand(vec.size) < per_gene_rate || 赋值语句。
0248 |         if np.any(mask): || 条件分支。
0249 |             vec[mask] += np.random.normal(0.0, sigma, size=int(np.sum(mask))) || 赋值语句。
0250 | 
0251 |         if self.toggle_rate > 0: || 条件分支。
0252 |             toggle_mask = np.random.rand(vec.size) < self.toggle_rate || 赋值语句。
0253 |             if np.any(toggle_mask): || 条件分支。
0254 |                 toggles = np.random.randint(0, self.max_production_per_machine + 1, size=int(np.sum(toggle_mask))) || 赋值语句。
0255 |                 vec[toggle_mask] = toggles || 赋值语句。
0256 | 
0257 |         vec = np.clip(np.floor(vec), 0, self.max_production_per_machine).astype(float) || 赋值语句。
0258 |         return vec || 返回输出。
0259 | 
0260 | 
0261 | @dataclass || 装饰器声明。
0262 | class ProductionScheduleRepair: || 基础修复器：处理机台数与产量边界。
0263 |     machines: int || 执行语句。
0264 |     days: int || 执行语句。
0265 |     min_machines_per_day: int || 执行语句。
0266 |     max_machines_per_day: int || 执行语句。
0267 |     min_production_per_machine: int || 执行语句。
0268 |     max_production_per_machine: int || 执行语句。
0269 |     context_requires = () || 赋值语句。
0270 |     context_provides = () || 赋值语句。
0271 |     context_mutates = () || 赋值语句。
0272 |     context_cache = () || 赋值语句。
0273 |     context_notes = ("Hard-constraint repair over machine/day production matrix; no context I/O.",) || 赋值语句。
0274 | 
0275 |     def repair(self, x: np.ndarray, context=None) -> np.ndarray: || 定义函数 `repair`。
0276 |         schedule = np.array(x, dtype=float, copy=True).reshape(self.machines, self.days) || 赋值语句。
0277 |         schedule = np.clip(schedule, 0, self.max_production_per_machine) || 赋值语句。
0278 | 
0279 |         for day in range(self.days): || 循环遍历。
0280 |             day_values = schedule[:, day] || 赋值语句。
0281 |             active_mask = day_values > 0 || 赋值语句。
0282 |             active_count = int(np.sum(active_mask)) || 赋值语句。
0283 | 
0284 |             if active_count > self.max_machines_per_day: || 条件分支。
0285 |                 active_idx = np.where(active_mask)[0] || 赋值语句。
0286 |                 order = active_idx[np.argsort(day_values[active_idx])] || 赋值语句。
0287 |                 drop = order[: active_count - self.max_machines_per_day] || 赋值语句。
0288 |                 schedule[drop, day] = 0.0 || 赋值语句。
0289 | 
0290 |             if self.min_machines_per_day > 0: || 条件分支。
0291 |                 active_mask = schedule[:, day] > 0 || 赋值语句。
0292 |                 active_count = int(np.sum(active_mask)) || 赋值语句。
0293 |                 if active_count < self.min_machines_per_day: || 条件分支。
0294 |                     inactive_idx = np.where(~active_mask)[0] || 赋值语句。
0295 |                     need = min(len(inactive_idx), self.min_machines_per_day - active_count) || 赋值语句。
0296 |                     if need > 0: || 条件分支。
0297 |                         chosen = np.random.choice(inactive_idx, size=need, replace=False) || 赋值语句。
0298 |                         schedule[chosen, day] = float(self.min_production_per_machine) || 赋值语句。
0299 | 
0300 |             low_mask = (schedule[:, day] > 0) & (schedule[:, day] < self.min_production_per_machine) || 赋值语句。
0301 |             schedule[low_mask, day] = 0.0 || 赋值语句。
0302 | 
0303 |         schedule = np.clip(schedule, 0, self.max_production_per_machine) || 赋值语句。
0304 |         return schedule.reshape(-1) || 返回输出。
0305 | 
0306 | 
0307 | @dataclass || 装饰器声明。
0308 | class SupplyAwareScheduleRepair: || 高级修复器：执行平滑、覆盖与连续性修复。
0309 |     machines: int || 执行语句。
0310 |     days: int || 执行语句。
0311 |     min_production_per_machine: int || 执行语句。
0312 |     bom_matrix: np.ndarray || 执行语句。
0313 |     supply_matrix: np.ndarray || 执行语句。
0314 |     base_repair: ProductionScheduleRepair || 执行语句。
0315 |     machine_weights: Optional[np.ndarray] = None || 赋值语句。
0316 |     soft_min_ratio: float = 0.2 || 赋值语句。
0317 |     continuity_bonus: float = 600.0 || 赋值语句。
0318 |     weight_bonus: float = 200.0 || 赋值语句。
0319 |     coverage_bonus: float = 300.0 || 赋值语句。
0320 |     weight_mix: float = 0.6 || 赋值语句。
0321 |     min_prod_ratio: float = 0.02 || 赋值语句。
0322 |     min_prod_abs: int = 100 || 赋值语句。
0323 |     material_cap_ratio: float = 1.2 || 赋值语句。
0324 |     daily_floor_ratio: float = 0.6 || 赋值语句。
0325 |     donor_keep_ratio: float = 0.7 || 赋值语句。
0326 |     daily_cap_ratio: float = 1.3 || 赋值语句。
0327 |     reserve_ratio: float = 0.6 || 赋值语句。
0328 |     budget_mode: str = "today" || 赋值语句。
0329 |     backfill_window: int = 0 || 赋值语句。
0330 |     smooth_strength: float = 0.6 || 赋值语句。
0331 |     smooth_passes: int = 2 || 赋值语句。
0332 |     coverage_passes: int = 2 || 赋值语句。
0333 |     fragment_passes: int = 2 || 赋值语句。
0334 |     continuity_swap: bool = True || 赋值语句。
0335 |     enforce_material_feasible: bool = True || 赋值语句。
0336 |     context_requires = () || 赋值语句。
0337 |     context_provides = () || 赋值语句。
0338 |     context_mutates = () || 赋值语句。
0339 |     context_cache = () || 赋值语句。
0340 |     context_notes = ("Supply/BOM-aware hard repair uses constructor matrices; no context I/O.",) || 赋值语句。
0341 | 
0342 |     def _prune_fragments(self, schedule: np.ndarray) -> np.ndarray: || 片段裁剪：去掉过小生产片段。
0343 |         passes = max(1, int(self.fragment_passes)) || 赋值语句。
0344 |         for _ in range(passes): || 循环遍历。
0345 |             changed = False || 赋值语句。
0346 |             for day in range(self.days): || 循环遍历。
0347 |                 before = schedule[:, day].copy() || 赋值语句。
0348 |                 active_before = before > 0 || 赋值语句。
0349 |                 active_count_before = int(np.sum(active_before)) || 赋值语句。
0350 |                 if active_count_before <= 1: || 条件分支。
0351 |                     continue || 流程控制语句。
0352 | 
0353 |                 day_total = float(np.sum(before)) || 赋值语句。
0354 |                 if day_total <= 1e-9: || 条件分支。
0355 |                     continue || 流程控制语句。
0356 |                 threshold = max(float(self.min_prod_abs), self.min_prod_ratio * day_total) || 赋值语句。
0357 |                 if day_total < float(self.min_prod_abs): || 条件分支。
0358 |                     threshold = max(1.0, self.min_prod_ratio * day_total) || 赋值语句。
0359 |                 if threshold <= 0: || 条件分支。
0360 |                     continue || 流程控制语句。
0361 |                 mask = (schedule[:, day] > 0) & (schedule[:, day] < threshold) || 赋值语句。
0362 |                 if np.any(mask): || 条件分支。
0363 |                     schedule[mask, day] = 0.0 || 赋值语句。
0364 |                     active_after = int(np.sum(schedule[:, day] > 0)) || 赋值语句。
0365 |                     min_keep = max(1, min(int(self.base_repair.min_machines_per_day), active_count_before)) || 赋值语句。
0366 |                     if active_after < min_keep: || 条件分支。
0367 |                         # Keep the largest productions to avoid empty/too-sparse days. || 注释：解释当前代码段用途或工程约束。
0368 |                         keep_idx = np.argsort(before)[-min_keep:] || 赋值语句。
0369 |                         schedule[:, day] = 0.0 || 赋值语句。
0370 |                         schedule[keep_idx, day] = before[keep_idx] || 赋值语句。
0371 |                     changed = True || 赋值语句。
0372 |             if not changed: || 条件分支。
0373 |                 break || 流程控制语句。
0374 |         return schedule || 返回输出。
0375 | 
0376 |     def _balance_forward(self, schedule: np.ndarray, weight_norm: np.ndarray) -> np.ndarray: || 前向平衡：跨天搬移产量降低波动。
0377 |         max_machines = int(self.base_repair.max_machines_per_day) || 赋值语句。
0378 |         if max_machines <= 0: || 条件分支。
0379 |             return schedule || 返回输出。
0380 |         min_shift = max(1.0, float(max(self.min_prod_abs, self.min_production_per_machine))) || 赋值语句。
0381 |         donor_floor = max(1, int(self.base_repair.min_machines_per_day)) || 赋值语句。
0382 |         passes = max(1, int(self.smooth_passes)) || 赋值语句。
0383 |         for _ in range(passes): || 循环遍历。
0384 |             daily_totals = np.sum(schedule, axis=0).astype(float) || 赋值语句。
0385 |             target_total = float(np.mean(daily_totals)) || 赋值语句。
0386 |             if target_total < min_shift: || 条件分支。
0387 |                 target_total = min_shift || 赋值语句。
0388 |             baseline_totals = daily_totals.copy() || 赋值语句。
0389 |             for day in range(1, self.days): || 循环遍历。
0390 |                 active = schedule[:, day] > 0 || 赋值语句。
0391 |                 active_count = int(np.sum(active)) || 赋值语句。
0392 |                 if active_count >= max_machines and daily_totals[day] >= target_total: || 条件分支。
0393 |                     continue || 流程控制语句。
0394 |                 lookback = self.backfill_window || 赋值语句。
0395 |                 if lookback <= 0: || 条件分支。
0396 |                     start_day = 0 || 赋值语句。
0397 |                 else: || 其他情况分支。
0398 |                     start_day = max(0, day - lookback) || 赋值语句。
0399 |                 needed_total = max(0.0, target_total - daily_totals[day]) || 赋值语句。
0400 |                 if self.smooth_strength > 0 and day > 0: || 条件分支。
0401 |                     adj_gap = daily_totals[day - 1] - daily_totals[day] || 赋值语句。
0402 |                     if adj_gap > 0: || 条件分支。
0403 |                         needed_total = max(needed_total, adj_gap * float(self.smooth_strength)) || 赋值语句。
0404 |                 missing = max(0, max_machines - active_count) || 赋值语句。
0405 |                 if missing > 0: || 条件分支。
0406 |                     needed_total = max(needed_total, min_shift * float(missing)) || 赋值语句。
0407 |                 per_new_target = max(min_shift, needed_total / max(1, missing)) if missing > 0 else min_shift || 赋值语句。
0408 |                 for donor_day in range(day - 1, start_day - 1, -1): || 循环遍历。
0409 |                     if active_count >= max_machines and needed_total <= 1e-6: || 条件分支。
0410 |                         break || 流程控制语句。
0411 |                     donor_active = schedule[:, donor_day] > 0 || 赋值语句。
0412 |                     donor_count = int(np.sum(donor_active)) || 赋值语句。
0413 |                     if donor_count <= 0: || 条件分支。
0414 |                         continue || 流程控制语句。
0415 |                     can_expand = schedule[:, day] < (self.base_repair.max_production_per_machine - 1e-6) || 赋值语句。
0416 |                     candidates = np.where(donor_active & can_expand)[0] || 赋值语句。
0417 |                     if candidates.size == 0: || 条件分支。
0418 |                         continue || 流程控制语句。
0419 |                     if active_count < max_machines: || 条件分支。
0420 |                         inactive_first = [] || 赋值语句。
0421 |                         active_first = [] || 赋值语句。
0422 |                         for m in candidates: || 循环遍历。
0423 |                             if schedule[m, day] <= 1e-12: || 条件分支。
0424 |                                 inactive_first.append(m) || 执行语句。
0425 |                             else: || 其他情况分支。
0426 |                                 active_first.append(m) || 执行语句。
0427 |                         inactive_first = sorted( || 赋值语句。
0428 |                             inactive_first, || 执行语句。
0429 |                             key=lambda m: (schedule[m, donor_day], weight_norm[m]), || 赋值语句。
0430 |                             reverse=True, || 赋值语句。
0431 |                         ) || 执行语句。
0432 |                         active_first = sorted( || 赋值语句。
0433 |                             active_first, || 执行语句。
0434 |                             key=lambda m: (schedule[m, donor_day], weight_norm[m]), || 赋值语句。
0435 |                             reverse=True, || 赋值语句。
0436 |                         ) || 执行语句。
0437 |                         candidates = inactive_first + active_first || 赋值语句。
0438 |                     else: || 其他情况分支。
0439 |                         candidates = sorted( || 赋值语句。
0440 |                             candidates, || 执行语句。
0441 |                             key=lambda m: (schedule[m, donor_day], weight_norm[m]), || 赋值语句。
0442 |                             reverse=True, || 赋值语句。
0443 |                         ) || 执行语句。
0444 |                     donor_floor_total = max( || 赋值语句。
0445 |                         float(self.min_prod_abs), || 执行语句。
0446 |                         float(target_total) * max(0.1, float(self.daily_floor_ratio)), || 执行语句。
0447 |                         float(baseline_totals[donor_day]) * float(self.donor_keep_ratio), || 执行语句。
0448 |                     ) || 执行语句。
0449 |                     donor_surplus = max(0.0, daily_totals[donor_day] - donor_floor_total) || 赋值语句。
0450 |                     for m in candidates: || 循环遍历。
0451 |                         if active_count >= max_machines and needed_total <= 1e-6: || 条件分支。
0452 |                             break || 流程控制语句。
0453 |                         if schedule[m, day] <= 1e-12 and active_count >= max_machines: || 条件分支。
0454 |                             continue || 流程控制语句。
0455 |                         donor_prod = schedule[m, donor_day] || 赋值语句。
0456 |                         if donor_prod <= 0: || 条件分支。
0457 |                             continue || 流程控制语句。
0458 |                         extra_cap = float(self.base_repair.max_production_per_machine) - schedule[m, day] || 赋值语句。
0459 |                         if extra_cap <= 0: || 条件分支。
0460 |                             continue || 流程控制语句。
0461 |                         if donor_surplus > 1e-6: || 条件分支。
0462 |                             target_move = max(needed_total, min_shift) || 赋值语句。
0463 |                             if schedule[m, day] <= 1e-12 and active_count < max_machines: || 条件分支。
0464 |                                 target_move = max(per_new_target, min_shift) || 赋值语句。
0465 |                             move = min(donor_prod, extra_cap, donor_surplus, target_move) || 赋值语句。
0466 |                         else: || 其他情况分支。
0467 |                             if active_count >= max_machines: || 条件分支。
0468 |                                 continue || 流程控制语句。
0469 |                             move = min(donor_prod, extra_cap, per_new_target) || 赋值语句。
0470 |                         if move <= 1e-6: || 条件分支。
0471 |                             continue || 流程控制语句。
0472 |                         if donor_count <= donor_floor and donor_prod - move <= 1e-6: || 条件分支。
0473 |                             continue || 流程控制语句。
0474 |                         schedule[m, donor_day] -= move || 赋值语句。
0475 |                         schedule[m, day] += move || 赋值语句。
0476 |                         if schedule[m, donor_day] <= 1e-6: || 条件分支。
0477 |                             schedule[m, donor_day] = 0.0 || 赋值语句。
0478 |                             donor_count -= 1 || 赋值语句。
0479 |                         if schedule[m, day] > 0 and not active[m]: || 条件分支。
0480 |                             active[m] = True || 赋值语句。
0481 |                             active_count += 1 || 赋值语句。
0482 |                             missing = max(0, max_machines - active_count) || 赋值语句。
0483 |                             per_new_target = max(min_shift, needed_total / max(1, missing)) if missing > 0 else min_shift || 赋值语句。
0484 |                         daily_totals[donor_day] -= move || 赋值语句。
0485 |                         daily_totals[day] += move || 赋值语句。
0486 |                         donor_surplus = max(0.0, donor_surplus - move) || 赋值语句。
0487 |                         if needed_total > 0: || 条件分支。
0488 |                             needed_total = max(0.0, needed_total - move) || 赋值语句。
0489 |         return schedule || 返回输出。
0490 | 
0491 |     def _backfill_coverage(self, schedule: np.ndarray, weight_norm: np.ndarray) -> np.ndarray: || 覆盖回填：优先补齐未生产机种。
0492 |         max_machines = int(self.base_repair.max_machines_per_day) || 赋值语句。
0493 |         if max_machines <= 0 or self.days <= 1: || 条件分支。
0494 |             return schedule || 返回输出。
0495 | 
0496 |         day_totals = np.sum(schedule, axis=0).astype(float) || 赋值语句。
0497 |         target_total = max(float(self.min_prod_abs), float(np.mean(day_totals))) || 赋值语句。
0498 |         baseline_totals = day_totals.copy() || 赋值语句。
0499 | 
0500 |         def _threshold_from_total(total: float) -> float: || 定义函数 `_threshold_from_total`。
0501 |             threshold = max(float(self.min_prod_abs), self.min_prod_ratio * total) || 赋值语句。
0502 |             if total < float(self.min_prod_abs): || 条件分支。
0503 |                 threshold = max(1.0, self.min_prod_ratio * total) || 赋值语句。
0504 |             return float(threshold) || 返回输出。
0505 | 
0506 |         for day in range(1, self.days): || 循环遍历。
0507 |             active_mask = schedule[:, day] > 0 || 赋值语句。
0508 |             active_count = int(np.sum(active_mask)) || 赋值语句。
0509 |             if active_count >= max_machines: || 条件分支。
0510 |                 continue || 流程控制语句。
0511 |             missing = max_machines - active_count || 赋值语句。
0512 |             base_threshold = _threshold_from_total(float(day_totals[day])) || 赋值语句。
0513 |             needed_total = max(0.0, target_total - float(day_totals[day])) || 赋值语句。
0514 |             base_target_min = max(1.0, base_threshold) || 赋值语句。
0515 |             if missing > 0 and needed_total > 0: || 条件分支。
0516 |                 base_target_min = max(base_target_min, needed_total / float(missing)) || 赋值语句。
0517 |             prev_active = schedule[:, day - 1] > 0 || 赋值语句。
0518 |             candidates = [int(m) for m in np.where(prev_active & ~active_mask)[0]] || 赋值语句。
0519 |             for m in np.where(~active_mask)[0]: || 循环遍历。
0520 |                 if int(m) not in candidates: || 条件分支。
0521 |                     candidates.append(int(m)) || 执行语句。
0522 |             candidates = sorted(candidates, key=lambda m: weight_norm[m], reverse=True) || 赋值语句。
0523 |             if self.backfill_window > 0: || 条件分支。
0524 |                 start_day = max(0, day - int(self.backfill_window)) || 赋值语句。
0525 |             else: || 其他情况分支。
0526 |                 start_day = 0 || 赋值语句。
0527 |             for m in candidates: || 循环遍历。
0528 |                 if missing <= 0: || 条件分支。
0529 |                     break || 流程控制语句。
0530 |                 donor_days = list(range(day - 1, start_day - 1, -1)) || 赋值语句。
0531 |                 donor_days.sort(key=lambda d: schedule[m, d], reverse=True) || 赋值语句。
0532 |                 for donor_day in donor_days: || 循环遍历。
0533 |                     donor_prod = float(schedule[m, donor_day]) || 赋值语句。
0534 |                     if donor_prod <= 0: || 条件分支。
0535 |                         continue || 流程控制语句。
0536 |                     donor_threshold = _threshold_from_total(float(day_totals[donor_day])) || 赋值语句。
0537 |                     movable = donor_prod - donor_threshold || 赋值语句。
0538 |                     if movable <= 1e-6: || 条件分支。
0539 |                         continue || 流程控制语句。
0540 |                     donor_active = int(np.sum(schedule[:, donor_day] > 0)) || 赋值语句。
0541 |                     donor_avg = float(day_totals[donor_day]) / float(max(1, donor_active)) || 赋值语句。
0542 |                     global_avg = float(target_total) / float(max(1, max_machines)) || 赋值语句。
0543 |                     needed_per_machine = needed_total / float(max(1, missing)) || 赋值语句。
0544 |                     dynamic_target = max( || 赋值语句。
0545 |                         base_target_min, || 执行语句。
0546 |                         needed_per_machine, || 执行语句。
0547 |                         global_avg, || 执行语句。
0548 |                         donor_avg * 0.6, || 执行语句。
0549 |                         donor_prod * 0.4, || 执行语句。
0550 |                     ) || 执行语句。
0551 |                     move = min(movable, dynamic_target) || 赋值语句。
0552 |                     donor_floor_total = max( || 赋值语句。
0553 |                         float(self.min_prod_abs), || 执行语句。
0554 |                         float(target_total) * max(0.1, float(self.daily_floor_ratio)), || 执行语句。
0555 |                         float(baseline_totals[donor_day]) * float(self.donor_keep_ratio), || 执行语句。
0556 |                     ) || 执行语句。
0557 |                     max_by_day = max(0.0, float(day_totals[donor_day]) - donor_floor_total) || 赋值语句。
0558 |                     if max_by_day <= 1e-6: || 条件分支。
0559 |                         continue || 流程控制语句。
0560 |                     if move > max_by_day: || 条件分支。
0561 |                         move = max_by_day || 赋值语句。
0562 |                     if move <= 1e-6: || 条件分支。
0563 |                         continue || 流程控制语句。
0564 |                     schedule[m, donor_day] -= move || 赋值语句。
0565 |                     schedule[m, day] += move || 赋值语句。
0566 |                     day_totals[donor_day] = max(0.0, float(day_totals[donor_day]) - move) || 赋值语句。
0567 |                     day_totals[day] = float(day_totals[day]) + move || 赋值语句。
0568 |                     active_mask[m] = True || 赋值语句。
0569 |                     missing -= 1 || 赋值语句。
0570 |                     base_threshold = _threshold_from_total(float(day_totals[day])) || 赋值语句。
0571 |                     needed_total = max(0.0, target_total - float(day_totals[day])) || 赋值语句。
0572 |                     base_target_min = max(1.0, base_threshold) || 赋值语句。
0573 |                     if missing > 0 and needed_total > 0: || 条件分支。
0574 |                         base_target_min = max(base_target_min, needed_total / float(missing)) || 赋值语句。
0575 |                     break || 流程控制语句。
0576 | 
0577 |             # Top-up low-production machines even if already active. || 注释：解释当前代码段用途或工程约束。
0578 |             needed_total = max(0.0, target_total - float(day_totals[day])) || 赋值语句。
0579 |             base_threshold = _threshold_from_total(float(day_totals[day])) || 赋值语句。
0580 |             target_min = max(1.0, base_threshold) || 赋值语句。
0581 |             if needed_total > 0: || 条件分支。
0582 |                 target_min = max(target_min, needed_total / float(max_machines)) || 赋值语句。
0583 |             low_machines = np.where((schedule[:, day] > 0) & (schedule[:, day] < target_min))[0] || 赋值语句。
0584 |             low_machines = sorted(low_machines, key=lambda m: schedule[m, day]) || 赋值语句。
0585 |             for m in low_machines: || 循环遍历。
0586 |                 need = target_min - float(schedule[m, day]) || 赋值语句。
0587 |                 if need <= 1e-6: || 条件分支。
0588 |                     continue || 流程控制语句。
0589 |                 donor_days = list(range(day - 1, start_day - 1, -1)) || 赋值语句。
0590 |                 donor_days.sort(key=lambda d: (schedule[m, d], d), reverse=True) || 赋值语句。
0591 |                 for donor_day in donor_days: || 循环遍历。
0592 |                     donor_prod = float(schedule[m, donor_day]) || 赋值语句。
0593 |                     if donor_prod <= 0: || 条件分支。
0594 |                         continue || 流程控制语句。
0595 |                     donor_threshold = _threshold_from_total(float(day_totals[donor_day])) || 赋值语句。
0596 |                     movable = donor_prod - donor_threshold || 赋值语句。
0597 |                     if movable <= 1e-6: || 条件分支。
0598 |                         continue || 流程控制语句。
0599 |                     move = min(movable, need) || 赋值语句。
0600 |                     donor_floor_total = max( || 赋值语句。
0601 |                         float(self.min_prod_abs), || 执行语句。
0602 |                         float(target_total) * max(0.1, float(self.daily_floor_ratio)), || 执行语句。
0603 |                         float(baseline_totals[donor_day]) * float(self.donor_keep_ratio), || 执行语句。
0604 |                     ) || 执行语句。
0605 |                     max_by_day = max(0.0, float(day_totals[donor_day]) - donor_floor_total) || 赋值语句。
0606 |                     if max_by_day <= 1e-6: || 条件分支。
0607 |                         continue || 流程控制语句。
0608 |                     if move > max_by_day: || 条件分支。
0609 |                         move = max_by_day || 赋值语句。
0610 |                     if move <= 1e-6: || 条件分支。
0611 |                         continue || 流程控制语句。
0612 |                     schedule[m, donor_day] -= move || 赋值语句。
0613 |                     schedule[m, day] += move || 赋值语句。
0614 |                     day_totals[donor_day] = max(0.0, float(day_totals[donor_day]) - move) || 赋值语句。
0615 |                     day_totals[day] = float(day_totals[day]) + move || 赋值语句。
0616 |                     need -= move || 赋值语句。
0617 |                     if need <= 1e-6: || 条件分支。
0618 |                         break || 流程控制语句。
0619 |         return schedule || 返回输出。
0620 | 
0621 |     def _continuity_swap(self, schedule: np.ndarray, weight_norm: np.ndarray) -> np.ndarray: || 连续性交换：减少开停切换。
0622 |         if not self.continuity_swap or self.days <= 1: || 条件分支。
0623 |             return schedule || 返回输出。
0624 |         min_shift = max(1.0, float(max(self.min_prod_abs, self.min_production_per_machine))) || 赋值语句。
0625 |         req_indices = [np.where(self.bom_matrix[m])[0] for m in range(self.machines)] || 赋值语句。
0626 |         current_stock = np.zeros(self.supply_matrix.shape[0], dtype=float) || 赋值语句。
0627 |         deferred = [] || 赋值语句。
0628 |         max_machines = int(self.base_repair.max_machines_per_day) || 赋值语句。
0629 |         max_per_machine = float(self.base_repair.max_production_per_machine) || 赋值语句。
0630 | 
0631 |         for day in range(self.days): || 循环遍历。
0632 |             current_stock += self.supply_matrix[:, day] || 赋值语句。
0633 |             day_prod = schedule[:, day].copy() || 赋值语句。
0634 |             day_usage = day_prod @ self.bom_matrix.astype(float) || 赋值语句。
0635 |             available = np.maximum(0.0, current_stock - day_usage) || 赋值语句。
0636 | 
0637 |             if day > 0: || 条件分支。
0638 |                 prev_active = schedule[:, day - 1] > 0 || 赋值语句。
0639 |                 new_idx = np.where((day_prod > 0) & (~prev_active))[0] || 赋值语句。
0640 |                 missing_idx = np.where(prev_active & (day_prod <= 0))[0] || 赋值语句。
0641 |                 if new_idx.size > 0 and missing_idx.size > 0: || 条件分支。
0642 |                     missing_order = sorted( || 赋值语句。
0643 |                         missing_idx, || 执行语句。
0644 |                         key=lambda m: (schedule[m, day - 1], weight_norm[m]), || 赋值语句。
0645 |                         reverse=True, || 赋值语句。
0646 |                     ) || 执行语句。
0647 |                     new_order = sorted( || 赋值语句。
0648 |                         new_idx, || 执行语句。
0649 |                         key=lambda m: (weight_norm[m], day_prod[m]), || 赋值语句。
0650 |                     ) || 执行语句。
0651 |                     for i in missing_order: || 循环遍历。
0652 |                         if not new_order: || 条件分支。
0653 |                             break || 流程控制语句。
0654 |                         req_i = req_indices[i] || 赋值语句。
0655 |                         for j in list(new_order): || 循环遍历。
0656 |                             prod_j = day_prod[j] || 赋值语句。
0657 |                             if prod_j < min_shift: || 条件分支。
0658 |                                 continue || 流程控制语句。
0659 |                             req_j = req_indices[j] || 赋值语句。
0660 |                             if req_i.size > 0: || 条件分支。
0661 |                                 avail_after = available.copy() || 赋值语句。
0662 |                                 if req_j.size > 0: || 条件分支。
0663 |                                     avail_after[req_j] += prod_j || 赋值语句。
0664 |                                 if np.any(avail_after[req_i] < prod_j - 1e-6): || 条件分支。
0665 |                                     continue || 流程控制语句。
0666 |                             day_prod[j] = 0.0 || 赋值语句。
0667 |                             day_prod[i] = prod_j || 赋值语句。
0668 |                             if req_j.size > 0: || 条件分支。
0669 |                                 available[req_j] += prod_j || 赋值语句。
0670 |                             if req_i.size > 0: || 条件分支。
0671 |                                 available[req_i] -= prod_j || 赋值语句。
0672 |                             deferred.append([int(j), float(prod_j), day + 1]) || 执行语句。
0673 |                             new_order.remove(j) || 执行语句。
0674 |                             break || 流程控制语句。
0675 | 
0676 |             if deferred: || 条件分支。
0677 |                 active_mask = day_prod > 0 || 赋值语句。
0678 |                 active_count = int(np.sum(active_mask)) || 赋值语句。
0679 |                 deferred.sort(key=lambda item: (item[2], -weight_norm[item[0]])) || 赋值语句。
0680 |                 remaining = [] || 赋值语句。
0681 |                 for m, qty, earliest in deferred: || 循环遍历。
0682 |                     if day < earliest: || 条件分支。
0683 |                         remaining.append([m, qty, earliest]) || 执行语句。
0684 |                         continue || 流程控制语句。
0685 |                     cap = max_per_machine - day_prod[m] || 赋值语句。
0686 |                     if cap <= 1e-6: || 条件分支。
0687 |                         remaining.append([m, qty, earliest]) || 执行语句。
0688 |                         continue || 流程控制语句。
0689 |                     if day_prod[m] <= 0 and active_count >= max_machines: || 条件分支。
0690 |                         remaining.append([m, qty, earliest]) || 执行语句。
0691 |                         continue || 流程控制语句。
0692 |                     req = req_indices[m] || 赋值语句。
0693 |                     max_feasible = cap if req.size == 0 else float(np.min(available[req])) || 执行语句。
0694 |                     add = min(cap, max_feasible, qty) || 赋值语句。
0695 |                     if add < min_shift: || 条件分支。
0696 |                         remaining.append([m, qty, earliest]) || 执行语句。
0697 |                         continue || 流程控制语句。
0698 |                     day_prod[m] += add || 赋值语句。
0699 |                     if req.size > 0: || 条件分支。
0700 |                         available[req] -= add || 赋值语句。
0701 |                     if day_prod[m] > 0 and not active_mask[m]: || 条件分支。
0702 |                         active_mask[m] = True || 赋值语句。
0703 |                         active_count += 1 || 赋值语句。
0704 |                     leftover = qty - add || 赋值语句。
0705 |                     if leftover > 1e-6: || 条件分支。
0706 |                         remaining.append([m, leftover, day + 1]) || 执行语句。
0707 |                 deferred = remaining || 赋值语句。
0708 | 
0709 |             schedule[:, day] = day_prod || 赋值语句。
0710 |             day_usage = day_prod @ self.bom_matrix.astype(float) || 赋值语句。
0711 |             current_stock = np.maximum(0.0, current_stock - day_usage) || 赋值语句。
0712 | 
0713 |         return schedule || 返回输出。
0714 | 
0715 |     def _enforce_material_feasibility(self, schedule: np.ndarray, weight_norm: np.ndarray) -> np.ndarray: || 物料可行性修复：确保库存不透支。
0716 |         if not self.enforce_material_feasible: || 条件分支。
0717 |             return schedule || 返回输出。
0718 |         current_stock = np.zeros(self.supply_matrix.shape[0], dtype=float) || 赋值语句。
0719 |         req_indices = [np.where(self.bom_matrix[m])[0] for m in range(self.machines)] || 赋值语句。
0720 |         prev_active = np.zeros(self.machines, dtype=bool) || 赋值语句。
0721 |         max_per_machine = float(self.base_repair.max_production_per_machine) || 赋值语句。
0722 | 
0723 |         for day in range(self.days): || 循环遍历。
0724 |             current_stock += self.supply_matrix[:, day] || 赋值语句。
0725 |             day_prod = schedule[:, day].copy() || 赋值语句。
0726 |             if np.sum(day_prod) <= 1e-6: || 条件分支。
0727 |                 prev_active = day_prod > 0 || 赋值语句。
0728 |                 continue || 流程控制语句。
0729 | 
0730 |             priority = day_prod.copy() || 赋值语句。
0731 |             priority += self.weight_bonus * weight_norm || 赋值语句。
0732 |             priority[prev_active] += self.continuity_bonus || 赋值语句。
0733 |             order = np.argsort(priority)[::-1] || 赋值语句。
0734 | 
0735 |             reserve = np.zeros_like(current_stock) || 赋值语句。
0736 |             if self.reserve_ratio > 0 and day < self.days - 1: || 条件分支。
0737 |                 future_total = np.sum(schedule[:, day + 1 :], axis=1) || 赋值语句。
0738 |                 future_requirements = future_total @ self.bom_matrix.astype(float) || 赋值语句。
0739 |                 reserve_target = future_requirements * float(self.reserve_ratio) || 赋值语句。
0740 |                 reserve_cap = current_stock * float(self.reserve_ratio) || 赋值语句。
0741 |                 reserve = np.minimum(reserve_target, reserve_cap) || 赋值语句。
0742 |             # Lock part of the stock for future scheduled production. || 注释：解释当前代码段用途或工程约束。
0743 |             remaining = np.maximum(0.0, current_stock - reserve) || 赋值语句。
0744 |             for m in order: || 循环遍历。
0745 |                 prod = day_prod[m] || 赋值语句。
0746 |                 if prod <= 1e-12: || 条件分支。
0747 |                     continue || 流程控制语句。
0748 |                 req = req_indices[m] || 赋值语句。
0749 |                 if req.size == 0: || 条件分支。
0750 |                     feasible = max_per_machine || 赋值语句。
0751 |                 else: || 其他情况分支。
0752 |                     feasible = float(np.min(remaining[req])) || 赋值语句。
0753 |                 if feasible <= 1e-12: || 条件分支。
0754 |                     day_prod[m] = 0.0 || 赋值语句。
0755 |                     continue || 流程控制语句。
0756 |                 new_prod = min(prod, feasible, max_per_machine) || 赋值语句。
0757 |                 if new_prod <= 1e-12: || 条件分支。
0758 |                     day_prod[m] = 0.0 || 赋值语句。
0759 |                     continue || 流程控制语句。
0760 |                 day_prod[m] = new_prod || 赋值语句。
0761 |                 if req.size > 0: || 条件分支。
0762 |                     remaining[req] = np.maximum(0.0, remaining[req] - new_prod) || 赋值语句。
0763 | 
0764 |             schedule[:, day] = day_prod || 赋值语句。
0765 |             consumption = day_prod @ self.bom_matrix.astype(float) || 赋值语句。
0766 |             current_stock = np.maximum(0.0, current_stock - consumption) || 赋值语句。
0767 |             prev_active = day_prod > 0 || 赋值语句。
0768 | 
0769 |         return schedule || 返回输出。
0770 | 
0771 |     def repair(self, x: np.ndarray, context=None) -> np.ndarray: || 定义函数 `repair`。
0772 |         schedule_pref = np.array(x, dtype=float, copy=True).reshape(self.machines, self.days) || 赋值语句。
0773 |         schedule_pref = np.clip(schedule_pref, 0, self.base_repair.max_production_per_machine) || 赋值语句。
0774 |         schedule = np.zeros_like(schedule_pref) || 赋值语句。
0775 | 
0776 |         current_stock = np.zeros(self.supply_matrix.shape[0], dtype=float) || 赋值语句。
0777 |         req_indices = [np.where(self.bom_matrix[m])[0] for m in range(self.machines)] || 赋值语句。
0778 |         base_soft_min = max(1, int(self.min_production_per_machine * self.soft_min_ratio)) || 赋值语句。
0779 |         weight_vec = ( || 赋值语句。
0780 |             np.asarray(self.machine_weights, dtype=float) || 赋值语句。
0781 |             if self.machine_weights is not None and len(self.machine_weights) == self.machines || 条件分支。
0782 |             else np.ones(self.machines, dtype=float) || 其他情况分支。
0783 |         ) || 执行语句。
0784 |         weight_vec = np.clip(weight_vec, 0.05, None) || 赋值语句。
0785 |         weight_norm = weight_vec / max(np.max(weight_vec), 1e-6) || 赋值语句。
0786 |         avg_materials = float(np.sum(self.bom_matrix)) / float(max(1, self.machines)) || 赋值语句。
0787 |         avg_materials = max(1e-6, avg_materials) || 赋值语句。
0788 |         prev_active = np.zeros(self.machines, dtype=bool) || 赋值语句。
0789 |         produced_any = np.zeros(self.machines, dtype=bool) || 赋值语句。
0790 |         for day in range(self.days): || 循环遍历。
0791 |             prev_day_active = prev_active.copy() || 赋值语句。
0792 |             current_stock += self.supply_matrix[:, day] || 赋值语句。
0793 |             remaining_days = max(1, self.days - day) || 赋值语句。
0794 |             if day < self.days - 1: || 条件分支。
0795 |                 future_supply = np.sum(self.supply_matrix[:, day + 1 :], axis=1) || 赋值语句。
0796 |             else: || 其他情况分支。
0797 |                 future_supply = np.zeros_like(current_stock) || 赋值语句。
0798 |             remaining_stock = current_stock + future_supply || 赋值语句。
0799 |             target_total = float(np.sum(remaining_stock)) / avg_materials / float(remaining_days) || 赋值语句。
0800 |             min_day_total = max(float(self.min_prod_abs), target_total * self.daily_floor_ratio) || 赋值语句。
0801 |             if self.budget_mode == "today": || 条件分支。
0802 |                 material_budget = np.maximum(0.0, current_stock.copy()) || 赋值语句。
0803 |                 max_day_total = max(min_day_total, float(np.sum(material_budget)) / avg_materials) || 赋值语句。
0804 |             else: || 其他情况分支。
0805 |                 max_day_total = max(min_day_total, target_total * self.daily_cap_ratio) || 赋值语句。
0806 |                 material_budget = remaining_stock / float(remaining_days) || 赋值语句。
0807 |                 material_budget *= self.material_cap_ratio || 赋值语句。
0808 |                 material_budget = np.minimum(material_budget, current_stock) || 赋值语句。
0809 |                 material_budget = np.maximum(0.0, material_budget) || 赋值语句。
0810 |             budget_stock = material_budget.copy() || 赋值语句。
0811 |             if np.sum(budget_stock) <= 1e-6 and np.sum(current_stock) > 1e-6: || 条件分支。
0812 |                 budget_stock = current_stock.copy() || 赋值语句。
0813 | 
0814 |             priority = schedule_pref[:, day].copy() || 赋值语句。
0815 |             priority += self.weight_bonus * weight_norm || 赋值语句。
0816 |             priority[prev_active] += self.continuity_bonus || 赋值语句。
0817 |             priority[~produced_any] += self.coverage_bonus || 赋值语句。
0818 |             order = np.argsort(priority)[::-1] || 赋值语句。
0819 | 
0820 |             soft_min = base_soft_min || 赋值语句。
0821 |             active = [] || 赋值语句。
0822 | 
0823 |             while True: || 条件循环。
0824 |                 active.clear() || 执行语句。
0825 |                 # force continuity when feasible || 注释：解释当前代码段用途或工程约束。
0826 |                 for m in order: || 循环遍历。
0827 |                     if not prev_active[m]: || 条件分支。
0828 |                         continue || 流程控制语句。
0829 |                     if len(active) >= self.base_repair.max_machines_per_day: || 条件分支。
0830 |                         break || 流程控制语句。
0831 |                     req = req_indices[m] || 赋值语句。
0832 |                     avail = float(self.base_repair.max_production_per_machine) if req.size == 0 else float(np.min(budget_stock[req])) || 执行语句。
0833 |                     if avail >= soft_min: || 条件分支。
0834 |                         active.append(m) || 执行语句。
0835 | 
0836 |                 for m in order: || 循环遍历。
0837 |                     if len(active) >= self.base_repair.max_machines_per_day: || 条件分支。
0838 |                         break || 流程控制语句。
0839 |                     if m in active: || 条件分支。
0840 |                         continue || 流程控制语句。
0841 |                     req = req_indices[m] || 赋值语句。
0842 |                     if req.size == 0: || 条件分支。
0843 |                         avail = float(self.base_repair.max_production_per_machine) || 赋值语句。
0844 |                     else: || 其他情况分支。
0845 |                         avail = float(np.min(budget_stock[req])) || 赋值语句。
0846 |                     if avail < soft_min: || 条件分支。
0847 |                         continue || 流程控制语句。
0848 |                     active.append(m) || 执行语句。
0849 | 
0850 |                 if len(active) >= self.base_repair.min_machines_per_day or soft_min <= 1: || 条件分支。
0851 |                     break || 流程控制语句。
0852 |                 soft_min = max(1, soft_min // 2) || 赋值语句。
0853 | 
0854 |             if not active: || 条件分支。
0855 |                 if np.any(current_stock > 0): || 条件分支。
0856 |                     m = int(order[0]) || 赋值语句。
0857 |                     req = req_indices[m] || 赋值语句。
0858 |                     avail = float(np.min(budget_stock[req])) if req.size > 0 else float(self.base_repair.max_production_per_machine) || 赋值语句。
0859 |                     prod = min(avail, float(self.base_repair.max_production_per_machine)) || 赋值语句。
0860 |                     if prod > 0: || 条件分支。
0861 |                         schedule[m, day] = prod || 赋值语句。
0862 |                         if req.size > 0: || 条件分支。
0863 |                             current_stock[req] = np.maximum(0.0, current_stock[req] - prod) || 赋值语句。
0864 |                             budget_stock[req] = np.maximum(0.0, budget_stock[req] - prod) || 赋值语句。
0865 |                         prev_active = schedule[:, day] > 0 || 赋值语句。
0866 |                         continue || 流程控制语句。
0867 |                 prev_active = np.zeros(self.machines, dtype=bool) || 赋值语句。
0868 |                 continue || 流程控制语句。
0869 | 
0870 |             # continuity reserve for next day || 注释：解释当前代码段用途或工程约束。
0871 |             if day < self.days - 1: || 条件分支。
0872 |                 supply_next = self.supply_matrix[:, day + 1] || 赋值语句。
0873 |             else: || 其他情况分支。
0874 |                 supply_next = np.zeros_like(current_stock) || 赋值语句。
0875 | 
0876 |             target_next = min(self.base_repair.max_machines_per_day, self.machines) || 赋值语句。
0877 |             if target_next <= 0: || 条件分支。
0878 |                 reserve = np.zeros_like(current_stock) || 赋值语句。
0879 |             else: || 其他情况分支。
0880 |                 active_set = set(active) || 赋值语句。
0881 |                 next_candidates = [] || 赋值语句。
0882 |                 for m in order: || 循环遍历。
0883 |                     if m in active_set: || 条件分支。
0884 |                         next_candidates.append(m) || 执行语句。
0885 |                 for m in order: || 循环遍历。
0886 |                     if m not in active_set: || 条件分支。
0887 |                         next_candidates.append(m) || 执行语句。
0888 |                 selected_next = list(next_candidates[:target_next]) || 赋值语句。
0889 | 
0890 |                 required_counts = np.zeros_like(current_stock) || 赋值语句。
0891 |                 for m in selected_next: || 循环遍历。
0892 |                     req = req_indices[m] || 赋值语句。
0893 |                     if req.size > 0: || 条件分支。
0894 |                         required_counts[req] += 1 || 赋值语句。
0895 |                 reserve = np.maximum(0.0, required_counts * soft_min - supply_next) || 赋值语句。
0896 |                 reserve = np.maximum(0.0, reserve * self.reserve_ratio) || 赋值语句。
0897 | 
0898 |                 # drop low-priority machines from next-day target if reserve is impossible || 注释：解释当前代码段用途或工程约束。
0899 |                 total_available = current_stock + supply_next || 赋值语句。
0900 |                 if np.any(reserve > total_available): || 条件分支。
0901 |                     for m in next_candidates[::-1]: || 循环遍历。
0902 |                         if m not in selected_next: || 条件分支。
0903 |                             continue || 流程控制语句。
0904 |                         req = req_indices[m] || 赋值语句。
0905 |                         if req.size > 0: || 条件分支。
0906 |                             required_counts[req] = np.maximum(0, required_counts[req] - 1) || 赋值语句。
0907 |                         selected_next.remove(m) || 执行语句。
0908 |                         reserve = np.maximum(0.0, required_counts * soft_min - supply_next) || 赋值语句。
0909 |                         reserve = np.maximum(0.0, reserve * self.reserve_ratio) || 赋值语句。
0910 |                         if not np.any(reserve > total_available): || 条件分支。
0911 |                             break || 流程控制语句。
0912 | 
0913 |             available_today = np.maximum(0.0, budget_stock - reserve) || 赋值语句。
0914 | 
0915 |             # base allocation + weighted allocation || 注释：解释当前代码段用途或工程约束。
0916 |             base_floor = max(1.0, float(soft_min)) || 赋值语句。
0917 |             if active and base_floor > 0: || 条件分支。
0918 |                 while True: || 条件循环。
0919 |                     required_counts = np.zeros_like(current_stock) || 赋值语句。
0920 |                     for m in active: || 循环遍历。
0921 |                         req = req_indices[m] || 赋值语句。
0922 |                         if req.size > 0: || 条件分支。
0923 |                             required_counts[req] += 1 || 赋值语句。
0924 |                     base_required = required_counts * base_floor || 赋值语句。
0925 |                     over_mask = base_required > (available_today + 1e-6) || 赋值语句。
0926 |                     if not np.any(over_mask): || 条件分支。
0927 |                         break || 流程控制语句。
0928 |                     candidates = [] || 赋值语句。
0929 |                     for m in active: || 循环遍历。
0930 |                         req = req_indices[m] || 赋值语句。
0931 |                         if req.size == 0: || 条件分支。
0932 |                             continue || 流程控制语句。
0933 |                         if np.any(over_mask[req]): || 条件分支。
0934 |                             candidates.append(m) || 执行语句。
0935 |                     if not candidates: || 条件分支。
0936 |                         candidates = list(active) || 赋值语句。
0937 |                     drop = min(candidates, key=lambda m: priority[m]) || 赋值语句。
0938 |                     active.remove(drop) || 执行语句。
0939 |                     if not active: || 条件分支。
0940 |                         break || 流程控制语句。
0941 | 
0942 |             if not active: || 条件分支。
0943 |                 if np.any(available_today > 0): || 条件分支。
0944 |                     for m in order: || 循环遍历。
0945 |                         req = req_indices[m] || 赋值语句。
0946 |                         avail = ( || 赋值语句。
0947 |                             float(np.min(available_today[req])) || 执行语句。
0948 |                             if req.size > 0 || 条件分支。
0949 |                             else float(self.base_repair.max_production_per_machine) || 其他情况分支。
0950 |                         ) || 执行语句。
0951 |                         if avail <= 0: || 条件分支。
0952 |                             continue || 流程控制语句。
0953 |                         prod = min(avail, float(self.base_repair.max_production_per_machine)) || 赋值语句。
0954 |                         if prod <= 0: || 条件分支。
0955 |                             continue || 流程控制语句。
0956 |                         schedule[m, day] = prod || 赋值语句。
0957 |                         if req.size > 0: || 条件分支。
0958 |                             current_stock[req] = np.maximum(0.0, current_stock[req] - prod) || 赋值语句。
0959 |                             budget_stock[req] = np.maximum(0.0, budget_stock[req] - prod) || 赋值语句。
0960 |                         break || 流程控制语句。
0961 |                 prev_active = schedule[:, day] > 0 || 赋值语句。
0962 |                 produced_any |= prev_active || 赋值语句。
0963 |                 continue || 流程控制语句。
0964 | 
0965 |             for m in active: || 循环遍历。
0966 |                 req = req_indices[m] || 赋值语句。
0967 |                 prod = min(base_floor, float(self.base_repair.max_production_per_machine)) || 赋值语句。
0968 |                 if prod <= 0: || 条件分支。
0969 |                     continue || 流程控制语句。
0970 |                 schedule[m, day] = prod || 赋值语句。
0971 |                 if req.size > 0: || 条件分支。
0972 |                     current_stock[req] = np.maximum(0.0, current_stock[req] - prod) || 赋值语句。
0973 |                     budget_stock[req] = np.maximum(0.0, budget_stock[req] - prod) || 赋值语句。
0974 | 
0975 |             available_today = np.maximum(0.0, budget_stock - reserve) || 赋值语句。
0976 |             mix = float(np.clip(self.weight_mix, 0.0, 1.0)) || 赋值语句。
0977 |             weights = (1.0 - mix) + mix * weight_norm || 赋值语句。
0978 |             total_weight = np.zeros_like(current_stock) || 赋值语句。
0979 |             for m in active: || 循环遍历。
0980 |                 req = req_indices[m] || 赋值语句。
0981 |                 if req.size > 0: || 条件分支。
0982 |                     total_weight[req] += weights[m] || 赋值语句。
0983 | 
0984 |             day_total = float(np.sum(schedule[:, day])) || 赋值语句。
0985 |             remaining_cap = max(0.0, max_day_total - day_total) || 赋值语句。
0986 |             alloc_order = sorted(active, key=lambda m: weights[m], reverse=True) || 赋值语句。
0987 |             for m in alloc_order: || 循环遍历。
0988 |                 if remaining_cap <= 0: || 条件分支。
0989 |                     break || 流程控制语句。
0990 |                 req = req_indices[m] || 赋值语句。
0991 |                 extra_cap = float(self.base_repair.max_production_per_machine) - schedule[m, day] || 赋值语句。
0992 |                 if extra_cap <= 0: || 条件分支。
0993 |                     continue || 流程控制语句。
0994 |                 if req.size == 0: || 条件分支。
0995 |                     extra = min(extra_cap, remaining_cap) || 赋值语句。
0996 |                 else: || 其他情况分支。
0997 |                     shares = [] || 赋值语句。
0998 |                     for mat in req: || 循环遍历。
0999 |                         denom = total_weight[mat] || 赋值语句。
1000 |                         if denom <= 1e-9: || 条件分支。
1001 |                             continue || 流程控制语句。
1002 |                         shares.append(available_today[mat] * weights[m] / denom) || 执行语句。
1003 |                     if not shares: || 条件分支。
1004 |                         continue || 流程控制语句。
1005 |                     extra = min(min(shares), extra_cap, remaining_cap) || 赋值语句。
1006 |                 if extra <= 0: || 条件分支。
1007 |                     continue || 流程控制语句。
1008 |                 schedule[m, day] += extra || 赋值语句。
1009 |                 remaining_cap -= extra || 赋值语句。
1010 |                 if req.size > 0: || 条件分支。
1011 |                     current_stock[req] = np.maximum(0.0, current_stock[req] - extra) || 赋值语句。
1012 |                     budget_stock[req] = np.maximum(0.0, budget_stock[req] - extra) || 赋值语句。
1013 |                     available_today[req] = np.maximum(0.0, available_today[req] - extra) || 赋值语句。
1014 | 
1015 |             # expand production for active machines with remaining stock || 注释：解释当前代码段用途或工程约束。
1016 |             day_total = float(np.sum(schedule[:, day])) || 赋值语句。
1017 |             remaining_cap = max(0.0, max_day_total - day_total) || 赋值语句。
1018 |             for m in active: || 循环遍历。
1019 |                 if remaining_cap <= 0: || 条件分支。
1020 |                     break || 流程控制语句。
1021 |                 req = req_indices[m] || 赋值语句。
1022 |                 if req.size == 0: || 条件分支。
1023 |                     avail = float(self.base_repair.max_production_per_machine) || 赋值语句。
1024 |                 else: || 其他情况分支。
1025 |                     avail = float(np.min(np.maximum(0.0, budget_stock[req] - reserve[req]))) || 赋值语句。
1026 |                 if avail <= 0: || 条件分支。
1027 |                     continue || 流程控制语句。
1028 |                 extra_cap = float(self.base_repair.max_production_per_machine) - schedule[m, day] || 赋值语句。
1029 |                 if extra_cap <= 0: || 条件分支。
1030 |                     continue || 流程控制语句。
1031 |                 extra = min(avail, extra_cap, remaining_cap) || 赋值语句。
1032 |                 if extra <= 0: || 条件分支。
1033 |                     continue || 流程控制语句。
1034 |                 schedule[m, day] += extra || 赋值语句。
1035 |                 if req.size > 0: || 条件分支。
1036 |                     current_stock[req] = np.maximum(0.0, current_stock[req] - extra) || 赋值语句。
1037 |                     budget_stock[req] = np.maximum(0.0, budget_stock[req] - extra) || 赋值语句。
1038 |                 remaining_cap -= extra || 赋值语句。
1039 | 
1040 |             # dynamic minimum production threshold per day || 注释：解释当前代码段用途或工程约束。
1041 |             day_total = float(np.sum(schedule[:, day])) || 赋值语句。
1042 |             threshold = max(self.min_prod_abs, self.min_prod_ratio * day_total) || 赋值语句。
1043 |             if day_total < min_day_total and threshold > 1.0: || 条件分支。
1044 |                 ratio = day_total / max(min_day_total, 1e-6) || 赋值语句。
1045 |                 threshold = max(1.0, threshold * max(0.25, ratio)) || 赋值语句。
1046 |             if threshold > 0: || 条件分支。
1047 |                 pruned = True || 赋值语句。
1048 |                 attempts = 0 || 赋值语句。
1049 |                 while pruned and attempts < 3: || 条件循环。
1050 |                     pruned = False || 赋值语句。
1051 |                     attempts += 1 || 赋值语句。
1052 |                     for m in list(active): || 循环遍历。
1053 |                         if schedule[m, day] >= threshold: || 条件分支。
1054 |                             continue || 流程控制语句。
1055 |                         prod = schedule[m, day] || 赋值语句。
1056 |                         schedule[m, day] = 0.0 || 赋值语句。
1057 |                         active.remove(m) || 执行语句。
1058 |                         req = req_indices[m] || 赋值语句。
1059 |                         if req.size > 0 and prod > 0: || 条件分支。
1060 |                             current_stock[req] = current_stock[req] + prod || 赋值语句。
1061 |                             budget_stock[req] = budget_stock[req] + prod || 赋值语句。
1062 |                         pruned = True || 赋值语句。
1063 | 
1064 |                     if len(active) < self.base_repair.min_machines_per_day: || 条件分支。
1065 |                         threshold = max(1.0, threshold * 0.5) || 赋值语句。
1066 |                         # try to refill with machines that can meet threshold || 注释：解释当前代码段用途或工程约束。
1067 |                         for m in order: || 循环遍历。
1068 |                             if len(active) >= self.base_repair.min_machines_per_day: || 条件分支。
1069 |                                 break || 流程控制语句。
1070 |                             if m in active: || 条件分支。
1071 |                                 continue || 流程控制语句。
1072 |                             req = req_indices[m] || 赋值语句。
1073 |                             avail = float(self.base_repair.max_production_per_machine) if req.size == 0 else float(np.min(budget_stock[req])) || 执行语句。
1074 |                             if avail >= threshold: || 条件分支。
1075 |                                 schedule[m, day] = min(avail, float(self.base_repair.max_production_per_machine)) || 赋值语句。
1076 |                                 active.append(m) || 执行语句。
1077 |                                 if req.size > 0: || 条件分支。
1078 |                                     current_stock[req] = np.maximum(0.0, current_stock[req] - schedule[m, day]) || 赋值语句。
1079 |                                     budget_stock[req] = np.maximum(0.0, budget_stock[req] - schedule[m, day]) || 赋值语句。
1080 |                                 pruned = True || 赋值语句。
1081 | 
1082 |             if np.sum(schedule[:, day]) <= 1e-6 and np.any(current_stock > 0): || 条件分支。
1083 |                 for m in order: || 循环遍历。
1084 |                     req = req_indices[m] || 赋值语句。
1085 |                     avail = float(np.min(current_stock[req])) if req.size > 0 else float(self.base_repair.max_production_per_machine) || 赋值语句。
1086 |                     if avail <= 0: || 条件分支。
1087 |                         continue || 流程控制语句。
1088 |                     prod = min(avail, float(self.base_repair.max_production_per_machine)) || 赋值语句。
1089 |                     if prod <= 0: || 条件分支。
1090 |                         continue || 流程控制语句。
1091 |                     schedule[m, day] = prod || 赋值语句。
1092 |                     if req.size > 0: || 条件分支。
1093 |                         current_stock[req] = np.maximum(0.0, current_stock[req] - prod) || 赋值语句。
1094 |                     break || 流程控制语句。
1095 | 
1096 |             # fill to max machines when possible, prefer previous-day machines || 注释：解释当前代码段用途或工程约束。
1097 |             active_mask = schedule[:, day] > 0 || 赋值语句。
1098 |             active_count = int(np.sum(active_mask)) || 赋值语句。
1099 |             if active_count < self.base_repair.max_machines_per_day and np.any(current_stock > 0): || 条件分支。
1100 |                 day_total = float(np.sum(schedule[:, day])) || 赋值语句。
1101 |                 remaining_cap = max(0.0, max_day_total - day_total) || 赋值语句。
1102 |                 if remaining_cap > 0: || 条件分支。
1103 |                     missing = max(1, self.base_repair.max_machines_per_day - active_count) || 赋值语句。
1104 |                     target_per_new = max(float(self.min_production_per_machine), remaining_cap / float(missing)) || 赋值语句。
1105 |                     candidate_order = [] || 赋值语句。
1106 |                     for m in order: || 循环遍历。
1107 |                         if prev_day_active[m] and not active_mask[m]: || 条件分支。
1108 |                             candidate_order.append(m) || 执行语句。
1109 |                     for m in order: || 循环遍历。
1110 |                         if not active_mask[m] and m not in candidate_order: || 条件分支。
1111 |                             candidate_order.append(m) || 执行语句。
1112 | 
1113 |                     for m in candidate_order: || 循环遍历。
1114 |                         if active_count >= self.base_repair.max_machines_per_day or remaining_cap <= 1e-6: || 条件分支。
1115 |                             break || 流程控制语句。
1116 |                         req = req_indices[m] || 赋值语句。
1117 |                         avail = ( || 赋值语句。
1118 |                             float(np.min(current_stock[req])) || 执行语句。
1119 |                             if req.size > 0 || 条件分支。
1120 |                             else float(self.base_repair.max_production_per_machine) || 其他情况分支。
1121 |                         ) || 执行语句。
1122 |                         if avail <= 0: || 条件分支。
1123 |                             continue || 流程控制语句。
1124 |                         extra_cap = float(self.base_repair.max_production_per_machine) - schedule[m, day] || 赋值语句。
1125 |                         if extra_cap <= 0: || 条件分支。
1126 |                             continue || 流程控制语句。
1127 |                         extra = min(avail, extra_cap, target_per_new, remaining_cap) || 赋值语句。
1128 |                         if extra <= 0: || 条件分支。
1129 |                             continue || 流程控制语句。
1130 |                         schedule[m, day] += extra || 赋值语句。
1131 |                         remaining_cap -= extra || 赋值语句。
1132 |                         active_mask[m] = True || 赋值语句。
1133 |                         active_count += 1 || 赋值语句。
1134 |                         if req.size > 0: || 条件分支。
1135 |                             current_stock[req] = np.maximum(0.0, current_stock[req] - extra) || 赋值语句。
1136 | 
1137 |             # force daily minimum production (sacrifice smoothness if needed) || 注释：解释当前代码段用途或工程约束。
1138 |             day_total = float(np.sum(schedule[:, day])) || 赋值语句。
1139 |             if day_total < min_day_total and np.any(current_stock > 0): || 条件分支。
1140 |                 gap = min_day_total - day_total || 赋值语句。
1141 | 
1142 |                 def _lift_with_stock(stock: np.ndarray, allow_new: bool) -> float: || 定义函数 `_lift_with_stock`。
1143 |                     nonlocal gap || 执行语句。
1144 |                     active_mask = schedule[:, day] > 0 || 赋值语句。
1145 |                     active_count = int(np.sum(active_mask)) || 赋值语句。
1146 |                     lift_order = [] || 赋值语句。
1147 |                     for m in order: || 循环遍历。
1148 |                         if active_mask[m]: || 条件分支。
1149 |                             lift_order.append(m) || 执行语句。
1150 |                     if allow_new: || 条件分支。
1151 |                         for m in order: || 循环遍历。
1152 |                             if not active_mask[m]: || 条件分支。
1153 |                                 lift_order.append(m) || 执行语句。
1154 |                     for m in lift_order: || 循环遍历。
1155 |                         if gap <= 1e-6: || 条件分支。
1156 |                             break || 流程控制语句。
1157 |                         req = req_indices[m] || 赋值语句。
1158 |                         is_new = schedule[m, day] <= 1e-12 || 赋值语句。
1159 |                         if is_new and active_count >= self.base_repair.max_machines_per_day: || 条件分支。
1160 |                             continue || 流程控制语句。
1161 |                         extra_cap = float(self.base_repair.max_production_per_machine) - schedule[m, day] || 赋值语句。
1162 |                         if extra_cap <= 0: || 条件分支。
1163 |                             continue || 流程控制语句。
1164 |                         if req.size == 0: || 条件分支。
1165 |                             avail = extra_cap || 赋值语句。
1166 |                         else: || 其他情况分支。
1167 |                             avail = float(np.min(stock[req])) || 赋值语句。
1168 |                             avail = min(avail, extra_cap) || 赋值语句。
1169 |                         if avail <= 0: || 条件分支。
1170 |                             continue || 流程控制语句。
1171 |                         if is_new: || 条件分支。
1172 |                             min_new = max(float(self.min_production_per_machine), threshold) || 赋值语句。
1173 |                         else: || 其他情况分支。
1174 |                             min_new = 0.0 || 赋值语句。
1175 |                         extra = min(avail, gap) || 赋值语句。
1176 |                         if extra < min_new: || 条件分支。
1177 |                             extra = min(avail, min_new) || 赋值语句。
1178 |                             if extra <= 0: || 条件分支。
1179 |                                 continue || 流程控制语句。
1180 |                         schedule[m, day] += extra || 赋值语句。
1181 |                         gap -= extra || 赋值语句。
1182 |                         if req.size > 0: || 条件分支。
1183 |                             stock[req] = np.maximum(0.0, stock[req] - extra) || 赋值语句。
1184 |                             current_stock[req] = np.maximum(0.0, current_stock[req] - extra) || 赋值语句。
1185 |                             if stock is not budget_stock: || 条件分支。
1186 |                                 budget_stock[req] = np.maximum(0.0, budget_stock[req] - extra) || 赋值语句。
1187 |                         if is_new and schedule[m, day] > 0: || 条件分支。
1188 |                             active_count += 1 || 赋值语句。
1189 |                     return gap || 返回输出。
1190 | 
1191 |                 allow_new = len(active) < self.base_repair.max_machines_per_day || 赋值语句。
1192 |                 _lift_with_stock(budget_stock, allow_new=allow_new) || 赋值语句。
1193 |                 if gap > 1e-6: || 条件分支。
1194 |                     _lift_with_stock(current_stock, allow_new=allow_new) || 赋值语句。
1195 | 
1196 |             prev_active = schedule[:, day] > 0 || 赋值语句。
1197 |             produced_any |= prev_active || 赋值语句。
1198 | 
1199 |         schedule = self._balance_forward(schedule, weight_norm) || 赋值语句。
1200 |         schedule = np.floor(schedule) || 赋值语句。
1201 |         schedule = np.clip(schedule, 0, self.base_repair.max_production_per_machine) || 赋值语句。
1202 |         schedule = self._prune_fragments(schedule) || 赋值语句。
1203 | 
1204 |         coverage_rounds = max(1, int(self.coverage_passes)) || 赋值语句。
1205 |         for _ in range(coverage_rounds): || 循环遍历。
1206 |             schedule = self._enforce_material_feasibility(schedule, weight_norm) || 赋值语句。
1207 |             schedule = self._backfill_coverage(schedule, weight_norm) || 赋值语句。
1208 |             schedule = np.floor(schedule) || 赋值语句。
1209 |             schedule = np.clip(schedule, 0, self.base_repair.max_production_per_machine) || 赋值语句。
1210 |             schedule = self._prune_fragments(schedule) || 赋值语句。
1211 | 
1212 |         schedule = self._continuity_swap(schedule, weight_norm) || 赋值语句。
1213 |         schedule = self._enforce_material_feasibility(schedule, weight_norm) || 赋值语句。
1214 |         schedule = self._prune_fragments(schedule) || 赋值语句。
1215 |         return schedule.reshape(-1) || 返回输出。
1216 | 
1217 | 
1218 | def build_schedule_pipeline( || 排产管线总装配入口。
1219 |     problem, || 执行语句。
1220 |     constraints, || 执行语句。
1221 |     *, || 执行语句。
1222 |     material_cap_ratio: float = 2.0, || 赋值语句。
1223 |     daily_floor_ratio: float = 0.55, || 赋值语句。
1224 |     donor_keep_ratio: float = 0.7, || 赋值语句。
1225 |     daily_cap_ratio: float = 2.2, || 赋值语句。
1226 |     reserve_ratio: float = 0.6, || 赋值语句。
1227 |     coverage_bonus: float = 300.0, || 赋值语句。
1228 |     budget_mode: str = "today", || 赋值语句。
1229 |     smooth_strength: float = 0.6, || 赋值语句。
1230 |     smooth_passes: int = 2, || 赋值语句。
1231 | ) -> RepresentationPipeline: || 代码块开始。
1232 |     if getattr(problem, "data", None) is not None: || 条件分支。
1233 |         initializer = SupplyAwareInitializer( || 赋值语句。
1234 |             machines=problem.machines, || 赋值语句。
1235 |             days=problem.days, || 赋值语句。
1236 |             min_machines_per_day=constraints.min_machines_per_day, || 赋值语句。
1237 |             max_machines_per_day=constraints.max_machines_per_day, || 赋值语句。
1238 |             min_production_per_machine=constraints.min_production_per_machine, || 赋值语句。
1239 |             max_production_per_machine=constraints.max_production_per_machine, || 赋值语句。
1240 |             bom_matrix=problem.data.bom_matrix, || 赋值语句。
1241 |             supply_matrix=problem.data.supply_matrix, || 赋值语句。
1242 |             machine_weights=getattr(problem.data, "machine_weights", None), || 赋值语句。
1243 |         ) || 执行语句。
1244 |     else: || 其他情况分支。
1245 |         initializer = ProductionScheduleInitializer( || 赋值语句。
1246 |             machines=problem.machines, || 赋值语句。
1247 |             days=problem.days, || 赋值语句。
1248 |             min_machines_per_day=constraints.min_machines_per_day, || 赋值语句。
1249 |             max_machines_per_day=constraints.max_machines_per_day, || 赋值语句。
1250 |             min_production_per_machine=constraints.min_production_per_machine, || 赋值语句。
1251 |             max_production_per_machine=constraints.max_production_per_machine, || 赋值语句。
1252 |         ) || 执行语句。
1253 |     mutator = ProductionScheduleMutation( || 赋值语句。
1254 |         sigma=0.5, || 赋值语句。
1255 |         per_gene_rate=0.05, || 赋值语句。
1256 |         toggle_rate=0.02, || 赋值语句。
1257 |         max_production_per_machine=constraints.max_production_per_machine, || 赋值语句。
1258 |     ) || 执行语句。
1259 |     base_repair = ProductionScheduleRepair( || 赋值语句。
1260 |         machines=problem.machines, || 赋值语句。
1261 |         days=problem.days, || 赋值语句。
1262 |         min_machines_per_day=constraints.min_machines_per_day, || 赋值语句。
1263 |         max_machines_per_day=constraints.max_machines_per_day, || 赋值语句。
1264 |         min_production_per_machine=constraints.min_production_per_machine, || 赋值语句。
1265 |         max_production_per_machine=constraints.max_production_per_machine, || 赋值语句。
1266 |     ) || 执行语句。
1267 |     if getattr(problem, "data", None) is not None: || 条件分支。
1268 |         repair = SupplyAwareScheduleRepair( || 赋值语句。
1269 |             machines=problem.machines, || 赋值语句。
1270 |             days=problem.days, || 赋值语句。
1271 |             min_production_per_machine=constraints.min_production_per_machine, || 赋值语句。
1272 |             bom_matrix=problem.data.bom_matrix, || 赋值语句。
1273 |             supply_matrix=problem.data.supply_matrix, || 赋值语句。
1274 |             base_repair=base_repair, || 赋值语句。
1275 |             machine_weights=getattr(problem.data, "machine_weights", None), || 赋值语句。
1276 |             soft_min_ratio=0.2, || 赋值语句。
1277 |             continuity_bonus=600.0, || 赋值语句。
1278 |             weight_bonus=200.0, || 赋值语句。
1279 |             coverage_bonus=coverage_bonus, || 赋值语句。
1280 |             min_prod_ratio=0.02, || 赋值语句。
1281 |             min_prod_abs=100, || 赋值语句。
1282 |             material_cap_ratio=material_cap_ratio, || 赋值语句。
1283 |             daily_floor_ratio=daily_floor_ratio, || 赋值语句。
1284 |             donor_keep_ratio=donor_keep_ratio, || 赋值语句。
1285 |             daily_cap_ratio=daily_cap_ratio, || 赋值语句。
1286 |             reserve_ratio=reserve_ratio, || 赋值语句。
1287 |             budget_mode=budget_mode, || 赋值语句。
1288 |             smooth_strength=smooth_strength, || 赋值语句。
1289 |             smooth_passes=smooth_passes, || 赋值语句。
1290 |             coverage_passes=smooth_passes, || 赋值语句。
1291 |             fragment_passes=2, || 赋值语句。
1292 |         ) || 执行语句。
1293 |     else: || 其他情况分支。
1294 |         repair = base_repair || 赋值语句。
1295 |     return RepresentationPipeline( || 返回输出。
1296 |         initializer=initializer, || 赋值语句。
1297 |         mutator=mutator, || 赋值语句。
1298 |         repair=repair, || 赋值语句。
1299 |         encoder=None, || 赋值语句。
1300 |     ) || 执行语句。
```
