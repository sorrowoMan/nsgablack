# working_integrated_optimizer.py 整文件逐行批注版

- 源文件。`nsgablack/examples/cases/production_scheduling/working_integrated_optimizer.py`
- 总行数。922
- 说明：这是整文件逐行批注版（每一行都有解释，空行不标注）。

```text
001 | # -*- coding: utf-8 -*- || 注释：解释当前代码段用途或工程约束。
002 | """Refactored entrypoint: pipeline-first production scheduling. || 文档字符串开始：说明模块或函数意图。
003 | 
004 | This script is a real-world application of NSGABlack's decomposition: || 文档字符串内容。
005 | - Problem: `ProductionSchedulingProblem.evaluate(x)` defines objectives. || 文档字符串内容。
006 | - RepresentationPipeline: initializer/mutator/repair enforce feasibility. || 文档字符串内容。
007 | - BiasModule: soft preferences and engineering guidance (optional). || 文档字符串内容。
008 | - Solver/Adapter: choose either the stable NSGA-II base, or a composable || 文档字符串内容。
009 |   multi-strategy controller ("multi-agent" as cooperating strategies). || 文档字符串内容。
010 | """ || 文档字符串结束。
011 | 
012 | from __future__ import annotations || from 导入：按命名空间引入对象。
013 | 
014 | import argparse || import 导入：引入模块。
015 | import os || import 导入：引入模块。
016 | import random || import 导入：引入模块。
017 | import sys || import 导入：引入模块。
018 | import time || import 导入：引入模块。
019 | from pathlib import Path || from 导入：按命名空间引入对象。
020 | from datetime import datetime || from 导入：按命名空间引入对象。
021 | from typing import Optional || from 导入：按命名空间引入对象。
022 | 
023 | import numpy as np || import 导入：引入模块。
024 | 
025 | 
026 | # Ensure local helper import works when executed as a script. || 注释：解释当前代码段用途或工程约束。
027 | _THIS_DIR = Path(__file__).resolve().parent || 赋值语句。
028 | if str(_THIS_DIR) not in sys.path: || 条件分支。
029 |     sys.path.insert(0, str(_THIS_DIR)) || 执行语句。
030 | 
031 | from _bootstrap import ensure_nsgablack_importable  # noqa: E402 || 执行 nsgablack 可导入校验。
032 | 
033 | ensure_nsgablack_importable(Path(__file__)) || 执行 nsgablack 可导入校验。
034 | 
035 | from nsgablack.core.composable_solver import ComposableSolver  # noqa: E402 || from 导入：按命名空间引入对象。
036 | from nsgablack.core.adapters import (  # noqa: E402 || from 导入：按命名空间引入对象。
037 |     AlgorithmAdapter, || 执行语句。
038 |     MOEADAdapter, || 执行语句。
039 |     MOEADConfig, || 执行语句。
040 |     MultiStrategyConfig, || 执行语句。
041 |     MultiStrategyControllerAdapter, || 多角色控制器：统一调度 explorer/exploiter。
042 |     RoleSpec, || 执行语句。
043 |     VNSAdapter, || 执行语句。
044 |     VNSConfig, || 执行语句。
045 | ) || 执行语句。
046 | from nsgablack.plugins import (  # noqa: E402 || from 导入：按命名空间引入对象。
047 |     ParetoArchivePlugin, || 执行语句。
048 |     BenchmarkHarnessPlugin, || 执行语句。
049 |     BenchmarkHarnessConfig, || 执行语句。
050 |     ModuleReportPlugin, || 执行语句。
051 |     ModuleReportConfig, || 执行语句。
052 |     ProfilerPlugin, || 执行语句。
053 |     ProfilerConfig, || 执行语句。
054 | ) || 执行语句。
055 | from nsgablack.utils.parallel import with_parallel_evaluation  # noqa: E402 || from 导入：按命名空间引入对象。
056 | from nsgablack.utils.viz import launch_from_builder  # noqa: E402 || from 导入：按命名空间引入对象。
057 | 
058 | from refactor_bias import build_production_bias_module || from 导入：按命名空间引入对象。
059 | from refactor_data import load_production_data || from 导入：按命名空间引入对象。
060 | from refactor_pipeline import build_schedule_pipeline || from 导入：按命名空间引入对象。
061 | from refactor_problem import ProductionConstraints, ProductionSchedulingProblem || from 导入：按命名空间引入对象。
062 | 
063 | 
064 | _PROBLEM_FACTORY_CACHE = {} || 进程内缓存，避免重复加载数据。
065 | 
066 | 
067 | class ProductionProblemFactory: || 定义可序列化问题工厂，供并行评估使用。
068 |     """ || 文档字符串开始：说明模块或函数意图。
069 |     Picklable factory for multiprocessing parallel evaluation. || 文档字符串内容。
070 | 
071 |     ParallelEvaluator will call `problem_factory()` per task for process backend. || 文档字符串内容。
072 |     To avoid re-loading data repeatedly, we cache the constructed problem inside || 文档字符串内容。
073 |     each worker process. || 文档字符串内容。
074 |     """ || 文档字符串结束。
075 | 
076 |     def __init__( || 定义函数 `__init__`。
077 |         self, || 执行语句。
078 |         *, || 执行语句。
079 |         base_dir: str, || 执行语句。
080 |         bom: Optional[str], || 执行语句。
081 |         supply: Optional[str], || 执行语句。
082 |         machines: int, || 执行语句。
083 |         materials: int, || 执行语句。
084 |         days: int, || 执行语句。
085 |         max_machines: int, || 执行语句。
086 |         min_machines: int, || 执行语句。
087 |         min_prod: int, || 执行语句。
088 |         max_prod: int, || 执行语句。
089 |         shortage_unit_penalty: float, || 执行语句。
090 |         penalty_objective: bool, || 执行语句。
091 |         penalty_scale: float, || 执行语句。
092 |     ) -> None: || 代码块开始。
093 |         self.base_dir = str(base_dir) || 赋值语句。
094 |         self.bom = bom || 赋值语句。
095 |         self.supply = supply || 赋值语句。
096 |         self.machines = int(machines) || 赋值语句。
097 |         self.materials = int(materials) || 赋值语句。
098 |         self.days = int(days) || 赋值语句。
099 |         self.max_machines = int(max_machines) || 赋值语句。
100 |         self.min_machines = int(min_machines) || 赋值语句。
101 |         self.min_prod = int(min_prod) || 赋值语句。
102 |         self.max_prod = int(max_prod) || 赋值语句。
103 |         self.shortage_unit_penalty = float(shortage_unit_penalty) || 赋值语句。
104 |         self.penalty_objective = bool(penalty_objective) || 赋值语句。
105 |         self.penalty_scale = float(penalty_scale) || 赋值语句。
106 | 
107 |         self._cache_key = ( || 赋值语句。
108 |             self.base_dir, || 执行语句。
109 |             self.bom, || 执行语句。
110 |             self.supply, || 执行语句。
111 |             self.machines, || 执行语句。
112 |             self.materials, || 执行语句。
113 |             self.days, || 执行语句。
114 |             self.max_machines, || 执行语句。
115 |             self.min_machines, || 执行语句。
116 |             self.min_prod, || 执行语句。
117 |             self.max_prod, || 执行语句。
118 |             self.shortage_unit_penalty, || 执行语句。
119 |             self.penalty_objective, || 执行语句。
120 |             self.penalty_scale, || 执行语句。
121 |         ) || 执行语句。
122 | 
123 |     def __call__(self) -> ProductionSchedulingProblem: || 定义函数 `__call__`。
124 |         cached = _PROBLEM_FACTORY_CACHE.get(self._cache_key) || 进程内缓存，避免重复加载数据。
125 |         if cached is not None: || 条件分支。
126 |             return cached || 返回输出。
127 | 
128 |         base_dir = Path(self.base_dir) || 赋值语句。
129 |         data = load_production_data( || 赋值语句。
130 |             base_dir=base_dir, || 赋值语句。
131 |             bom_path=Path(self.bom) if self.bom else None, || 赋值语句。
132 |             supply_path=Path(self.supply) if self.supply else None, || 赋值语句。
133 |             machines=self.machines, || 赋值语句。
134 |             materials=self.materials, || 赋值语句。
135 |             days=self.days, || 赋值语句。
136 |             fallback=True, || 赋值语句。
137 |         ) || 执行语句。
138 |         constraints = ProductionConstraints( || 赋值语句。
139 |             max_machines_per_day=self.max_machines, || 赋值语句。
140 |             min_machines_per_day=self.min_machines, || 赋值语句。
141 |             min_production_per_machine=self.min_prod, || 赋值语句。
142 |             max_production_per_machine=self.max_prod, || 赋值语句。
143 |             shortage_unit_penalty=self.shortage_unit_penalty, || 赋值语句。
144 |             include_penalty_objective=self.penalty_objective, || 赋值语句。
145 |             penalty_objective_scale=self.penalty_scale, || 赋值语句。
146 |         ) || 执行语句。
147 |         problem = ProductionSchedulingProblem(data=data, constraints=constraints) || 赋值语句。
148 |         _PROBLEM_FACTORY_CACHE[self._cache_key] = problem || 进程内缓存，避免重复加载数据。
149 |         return problem || 返回输出。
150 | 
151 | 
152 | def _build_problem_factory(args) -> ProductionProblemFactory: || 定义函数 `_build_problem_factory`。
153 |     return ProductionProblemFactory( || 返回输出。
154 |         base_dir=str(Path(__file__).resolve().parent), || 赋值语句。
155 |         bom=args.bom, || 赋值语句。
156 |         supply=args.supply, || 赋值语句。
157 |         machines=args.machines, || 赋值语句。
158 |         materials=args.materials, || 赋值语句。
159 |         days=args.days, || 赋值语句。
160 |         max_machines=args.max_machines, || 赋值语句。
161 |         min_machines=args.min_machines, || 赋值语句。
162 |         min_prod=args.min_prod, || 赋值语句。
163 |         max_prod=args.max_prod, || 赋值语句。
164 |         shortage_unit_penalty=args.shortage_unit_penalty, || 赋值语句。
165 |         penalty_objective=args.penalty_objective, || 赋值语句。
166 |         penalty_scale=args.penalty_scale, || 赋值语句。
167 |     ) || 执行语句。
168 | 
169 | 
170 | class ConsoleProgressPlugin: || 定义控制台进度插件。
171 |     """Minimal console progress to avoid the 'looks stuck' feeling.""" || 文档字符串开始：说明模块或函数意图。
172 | 
173 |     def __init__(self, report_every: int = 10): || 定义函数 `__init__`。
174 |         from nsgablack.plugins import Plugin || from 导入：按命名空间引入对象。
175 | 
176 |         # Use Plugin base to integrate with PluginManager. || 注释：解释当前代码段用途或工程约束。
177 |         class _Impl(Plugin): || 定义类 `_Impl`。
178 |             # Explicit context contract: this plugin only reports runtime progress. || 注释：解释当前代码段用途或工程约束。
179 |             context_requires = () || 赋值语句。
180 |             context_provides = () || 赋值语句。
181 |             context_mutates = () || 赋值语句。
182 |             context_cache = () || 赋值语句。
183 |             context_notes = ( || 赋值语句。
184 |                 "Console progress reporter; reads solver runtime state via hooks and writes no context fields.", || 执行语句。
185 |             ) || 执行语句。
186 | 
187 |             def __init__(self, report_every: int): || 定义函数 `__init__`。
188 |                 super().__init__(name="console_progress") || 赋值语句。
189 |                 self.report_every = int(max(1, report_every)) || 赋值语句。
190 |                 self._t0 = None || 赋值语句。
191 |                 self._last_t = None || 赋值语句。
192 | 
193 |             def on_solver_init(self, solver): || 定义函数 `on_solver_init`。
194 |                 self._t0 = time.time() || 赋值语句。
195 |                 self._last_t = self._t0 || 赋值语句。
196 | 
197 |             def on_generation_end(self, generation: int): || 定义函数 `on_generation_end`。
198 |                 if generation % self.report_every != 0: || 条件分支。
199 |                     return || 执行语句。
200 |                 solver = getattr(self, "solver", None) || 赋值语句。
201 |                 if solver is None: || 条件分支。
202 |                     return || 执行语句。
203 |                 now = time.time() || 赋值语句。
204 |                 dt = (now - self._last_t) if self._last_t is not None else 0.0 || 赋值语句。
205 |                 self._last_t = now || 赋值语句。
206 |                 best = getattr(solver, "best_objective", None) || 赋值语句。
207 |                 n = None || 赋值语句。
208 |                 try: || 异常保护开始。
209 |                     n = int(getattr(solver, "last_step_summary", {}).get("num_candidates")) || 赋值语句。
210 |                 except Exception: || 异常处理分支。
211 |                     n = None || 赋值语句。
212 |                 elapsed = (now - self._t0) if self._t0 is not None else 0.0 || 赋值语句。
213 |                 if best is None: || 条件分支。
214 |                     print(f"[step {generation:04d}] elapsed={elapsed:8.1f}s  last_step={dt:6.2f}s  candidates={n}") || 赋值语句。
215 |                 else: || 其他情况分支。
216 |                     print( || 执行语句。
217 |                         f"[step {generation:04d}] elapsed={elapsed:8.1f}s  last_step={dt:6.2f}s  " || 赋值语句。
218 |                         f"candidates={n}  best_score={best:.6g}" || 赋值语句。
219 |                     ) || 执行语句。
220 | 
221 |         self._plugin = _Impl(report_every=report_every) || 赋值语句。
222 | 
223 |     def __getattr__(self, name): || 定义函数 `__getattr__`。
224 |         return getattr(self._plugin, name) || 返回输出。
225 | 
226 | 
227 | def _build_problem(args) -> ProductionSchedulingProblem: || 定义函数 `_build_problem`。
228 |     data = load_production_data( || 赋值语句。
229 |         base_dir=Path(__file__).resolve().parent, || 赋值语句。
230 |         bom_path=Path(args.bom) if args.bom else None, || 赋值语句。
231 |         supply_path=Path(args.supply) if args.supply else None, || 赋值语句。
232 |         machines=args.machines, || 赋值语句。
233 |         materials=args.materials, || 赋值语句。
234 |         days=args.days, || 赋值语句。
235 |         fallback=True, || 赋值语句。
236 |     ) || 执行语句。
237 |     if getattr(data, "bom_path", None) is not None: || 条件分支。
238 |         print(f"[data] bom={data.bom_path}") || 赋值语句。
239 |     if getattr(data, "supply_path", None) is not None: || 条件分支。
240 |         print(f"[data] supply={data.supply_path}") || 赋值语句。
241 |     constraints = ProductionConstraints( || 赋值语句。
242 |         max_machines_per_day=args.max_machines, || 赋值语句。
243 |         min_machines_per_day=args.min_machines, || 赋值语句。
244 |         min_production_per_machine=args.min_prod, || 赋值语句。
245 |         max_production_per_machine=args.max_prod, || 赋值语句。
246 |         shortage_unit_penalty=args.shortage_unit_penalty, || 赋值语句。
247 |         include_penalty_objective=args.penalty_objective, || 赋值语句。
248 |         penalty_objective_scale=args.penalty_scale, || 赋值语句。
249 |     ) || 执行语句。
250 |     problem = ProductionSchedulingProblem(data=data, constraints=constraints) || 赋值语句。
251 |     return problem || 返回输出。
252 | 
253 | 
254 | def _choose_pareto_solutions(problem, individuals: np.ndarray, objectives: np.ndarray): || 定义函数 `_choose_pareto_solutions`。
255 |     if individuals is None or len(individuals) == 0: || 条件分支。
256 |         return [] || 返回输出。
257 |     penalties = [] || 赋值语句。
258 |     for ind in individuals: || 循环遍历。
259 |         schedule = problem.decode_schedule(ind) || 赋值语句。
260 |         penalties.append(problem._compute_penalty(schedule)) || 执行语句。
261 |     penalties = np.asarray(penalties, dtype=float) || 赋值语句。
262 | 
263 |     idx_penalty = int(np.argmin(penalties)) || 赋值语句。
264 |     idx_prod = int(np.argmin(objectives[:, 0])) || 赋值语句。
265 |     picks = [] || 赋值语句。
266 |     seen = set() || 赋值语句。
267 |     for label, idx in (("penalty", idx_penalty), ("production", idx_prod)): || 循环遍历。
268 |         if idx in seen: || 条件分支。
269 |             continue || 流程控制语句。
270 |         seen.add(idx) || 执行语句。
271 |         picks.append((label, individuals[idx], objectives[idx])) || 执行语句。
272 |     return picks || 返回输出。
273 | 
274 | 
275 | def _crowding_distance(objectives: np.ndarray) -> np.ndarray: || 定义函数 `_crowding_distance`。
276 |     if objectives is None or len(objectives) == 0: || 条件分支。
277 |         return np.array([], dtype=float) || 返回输出。
278 |     n, m = objectives.shape || 赋值语句。
279 |     distance = np.zeros(n, dtype=float) || 赋值语句。
280 |     for obj_idx in range(m): || 循环遍历。
281 |         order = np.argsort(objectives[:, obj_idx]) || 赋值语句。
282 |         distance[order[0]] = np.inf || 赋值语句。
283 |         distance[order[-1]] = np.inf || 赋值语句。
284 |         f_min = objectives[order[0], obj_idx] || 赋值语句。
285 |         f_max = objectives[order[-1], obj_idx] || 赋值语句。
286 |         if f_max - f_min <= 1e-12: || 条件分支。
287 |             continue || 流程控制语句。
288 |         for i in range(1, n - 1): || 循环遍历。
289 |             prev_val = objectives[order[i - 1], obj_idx] || 赋值语句。
290 |             next_val = objectives[order[i + 1], obj_idx] || 赋值语句。
291 |             distance[order[i]] += (next_val - prev_val) / (f_max - f_min) || 赋值语句。
292 |     return distance || 返回输出。
293 | 
294 | 
295 | def _resolve_pareto_export_root(base: Optional[Path]) -> Path: || 定义函数 `_resolve_pareto_export_root`。
296 |     if base is None: || 条件分支。
297 |         base_dir = Path(__file__).resolve().parents[1] || 赋值语句。
298 |         ts = datetime.now().strftime("%Y%m%d_%H%M%S") || 赋值语句。
299 |         root = base_dir / f"生产调度结果_pareto_{ts}" || 赋值语句。
300 |     elif base.suffix: || 条件补充分支。
301 |         root = base.with_name(f"{base.stem}_pareto") || 赋值语句。
302 |     else: || 其他情况分支。
303 |         root = base || 赋值语句。
304 |     root.mkdir(parents=True, exist_ok=True) || 赋值语句。
305 |     return root || 返回输出。
306 | 
307 | 
308 | def _resolve_summary_path(root: Path) -> Path: || 定义函数 `_resolve_summary_path`。
309 |     return root / "pareto_summary.csv" || 返回输出。
310 | 
311 | 
312 | def _export_pareto_batch( || 定义函数 `_export_pareto_batch`。
313 |     problem, || 执行语句。
314 |     individuals: np.ndarray, || 执行语句。
315 |     objectives: np.ndarray, || 执行语句。
316 |     base_export: Optional[Path], || 执行语句。
317 |     mode: str, || 执行语句。
318 |     limit: int, || 执行语句。
319 | ) -> int: || 代码块开始。
320 |     if individuals is None or len(individuals) == 0: || 条件分支。
321 |         return 0 || 返回输出。
322 |     total = len(individuals) || 赋值语句。
323 |     if limit <= 0: || 条件分支。
324 |         limit = total || 赋值语句。
325 |     else: || 其他情况分支。
326 |         limit = max(1, min(int(limit), total)) || 赋值语句。
327 | 
328 |     export_root = _resolve_pareto_export_root(base_export) || 赋值语句。
329 |     ext = ".xlsx" || 赋值语句。
330 |     if base_export is not None and base_export.suffix: || 条件分支。
331 |         ext = base_export.suffix || 赋值语句。
332 | 
333 |     if mode == "crowding": || 条件分支。
334 |         crowd = _crowding_distance(objectives) || 赋值语句。
335 |         order = np.argsort(-crowd) || 赋值语句。
336 |     elif mode == "production": || 条件补充分支。
337 |         order = np.argsort(objectives[:, 0]) || 赋值语句。
338 |     else: || 其他情况分支。
339 |         order = np.arange(total) || 赋值语句。
340 | 
341 |     selected = order[:limit] || 赋值语句。
342 |     rows = [] || 赋值语句。
343 |     for rank, idx in enumerate(selected, start=1): || 循环遍历。
344 |         label = f"pareto{rank:02d}" || 赋值语句。
345 |         schedule = problem.decode_schedule(individuals[idx]) || 赋值语句。
346 |         summary = problem.summarize_schedule(schedule) || 赋值语句。
347 |         export_path = export_root / f"{label}{ext}" || 赋值语句。
348 |         _export_schedule(export_path, schedule) || 执行语句。
349 |         row = {"label": label, "file": str(export_path)} || 赋值语句。
350 |         for j, value in enumerate(objectives[idx]): || 循环遍历。
351 |             row[f"obj{j}"] = float(value) || 赋值语句。
352 |         row.update(summary) || 执行语句。
353 |         rows.append(row) || 执行语句。
354 | 
355 |     if rows: || 条件分支。
356 |         import pandas as pd || import 导入：引入模块。
357 | 
358 |         summary_path = _resolve_summary_path(export_root) || 赋值语句。
359 |         df = pd.DataFrame(rows) || 赋值语句。
360 |         df.to_csv(summary_path, index=False) || 赋值语句。
361 |     return len(rows) || 返回输出。
362 | 
363 | 
364 | def _default_export_path(prefix: str = "生产调度结果", label: Optional[str] = None) -> Path: || 定义函数 `_default_export_path`。
365 |     base_dir = Path(__file__).resolve().parents[1] || 赋值语句。
366 |     ts = datetime.now().strftime("%Y%m%d_%H%M%S") || 赋值语句。
367 |     if label: || 条件分支。
368 |         return base_dir / f"{prefix}_{label}_{ts}.xlsx" || 返回输出。
369 |     return base_dir / f"{prefix}_{ts}.xlsx" || 返回输出。
370 | 
371 | 
372 | def _resolve_export_path(base: Optional[Path], label: str) -> Path: || 定义函数 `_resolve_export_path`。
373 |     if base is None: || 条件分支。
374 |         return _default_export_path(label=label) || 返回输出。
375 |     if base.suffix: || 条件分支。
376 |         return base.with_name(f"{base.stem}_{label}{base.suffix}") || 返回输出。
377 |     return base / _default_export_path(label=label).name || 返回输出。
378 | 
379 | 
380 | def _export_schedule(path: Path, schedule: np.ndarray) -> None: || 定义函数 `_export_schedule`。
381 |     import pandas as pd || import 导入：引入模块。
382 | 
383 |     schedule = np.asarray(schedule, dtype=float) || 赋值语句。
384 |     schedule = np.clip(np.floor(schedule), 0, None).astype(int) || 赋值语句。
385 |     machines, days = schedule.shape || 赋值语句。
386 | 
387 |     data = { || 赋值语句。
388 |         "Day_Index": list(range(days)), || 执行语句。
389 |         "Date": [f"。{day}。" for day in range(days)], || 执行语句。
390 |     } || 执行语句。
391 |     for m in range(machines): || 循环遍历。
392 |         data[f"机种{m}"] = schedule[m, :].tolist() || 赋值语句。
393 | 
394 |     df = pd.DataFrame(data) || 赋值语句。
395 |     if path.suffix.lower() == ".xlsx": || 条件分支。
396 |         # Keep a stable sheet name for downstream visualization scripts. || 注释：解释当前代码段用途或工程约束。
397 |         df.to_excel(path, index=False, sheet_name="生产计划") || 赋值语句。
398 |     else: || 其他情况分支。
399 |         df.to_csv(path, index=False) || 赋值语句。
400 | 
401 | 
402 | def _extract_pareto(solver_or_result) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]: || 定义函数 `_extract_pareto`。
403 |     """ || 文档字符串开始：说明模块或函数意图。
404 |     Normalize Pareto outputs from either: || 文档字符串内容。
405 |     - EvolutionSolver result dict || 文档字符串内容。
406 |     - ComposableSolver + ParetoArchivePlugin (solver.pareto_*) || 文档字符串内容。
407 |     """ || 文档字符串结束。
408 |     if isinstance(solver_or_result, dict): || 条件分支。
409 |         pareto = solver_or_result.get("pareto_solutions") || 赋值语句。
410 |         if isinstance(pareto, dict) and "individuals" in pareto: || 条件分支。
411 |             individuals = np.asarray(pareto["individuals"], dtype=float) || 赋值语句。
412 |             objectives = np.asarray(pareto["objectives"], dtype=float) || 赋值语句。
413 |             return individuals, objectives || 返回输出。
414 |         return None, None || 返回输出。
415 | 
416 |     pareto_X = getattr(solver_or_result, "pareto_solutions", None) || 赋值语句。
417 |     pareto_F = getattr(solver_or_result, "pareto_objectives", None) || 赋值语句。
418 |     if pareto_X is None or pareto_F is None: || 条件分支。
419 |         return None, None || 返回输出。
420 |     return np.asarray(pareto_X, dtype=float), np.asarray(pareto_F, dtype=float) || 返回输出。
421 | 
422 | 
423 | class ProductionRandomSearchAdapter(AlgorithmAdapter): || 探索角色适配器：全局随机探索。
424 |     """Explorer: generate diverse feasible candidates via init+repair.""" || 文档字符串开始：说明模块或函数意图。
425 | 
426 |     def __init__(self, *, batch_size: int = 32): || 定义函数 `__init__`。
427 |         super().__init__(name="production_random_search") || 赋值语句。
428 |         self.batch_size = int(batch_size) || 赋值语句。
429 | 
430 |     def propose(self, solver, context): || 定义函数 `propose`。
431 |         out = [] || 赋值语句。
432 |         for _ in range(max(1, self.batch_size)): || 循环遍历。
433 |             x = solver.init_candidate(context) || 赋值语句。
434 |             x = solver.repair_candidate(x, context) || 赋值语句。
435 |             out.append(x) || 执行语句。
436 |         return out || 返回输出。
437 | 
438 | 
439 | class ProductionLocalSearchAdapter(AlgorithmAdapter): || 开发角色适配器：围绕最优解局部搜索。
440 |     """Exploiter: refine best solution via mutate+repair.""" || 文档字符串开始：说明模块或函数意图。
441 | 
442 |     def __init__(self, *, batch_size: int = 16): || 定义函数 `__init__`。
443 |         super().__init__(name="production_local_search") || 赋值语句。
444 |         self.batch_size = int(batch_size) || 赋值语句。
445 | 
446 |     def propose(self, solver, context): || 定义函数 `propose`。
447 |         base = solver.best_x || 赋值语句。
448 |         out = [] || 赋值语句。
449 |         for _ in range(max(1, self.batch_size)): || 循环遍历。
450 |             if base is None: || 条件分支。
451 |                 x = solver.init_candidate(context) || 赋值语句。
452 |             else: || 其他情况分支。
453 |                 x = solver.mutate_candidate(base, context) || 赋值语句。
454 |             x = solver.repair_candidate(x, context) || 赋值语句。
455 |             out.append(x) || 执行语句。
456 |         return out || 返回输出。
457 | 
458 | 
459 | def run_nsga2(problem, args): || 定义函数 `run_nsga2`。
460 |     raise RuntimeError( || 主动抛错。
461 |         "nsga2 path has been removed from this application entrypoint. " || 执行语句。
462 |         "Use `--solver multi-agent` (default) for cooperative search." || 执行语句。
463 |     ) || 执行语句。
464 | 
465 | 
466 | def build_multi_agent_solver(problem, args): || 多策略协同求解器装配入口。
467 |     """Build solver for multi-agent cooperation (no run).""" || 文档字符串开始：说明模块或函数意图。
468 |     pipeline = build_schedule_pipeline( || 赋值语句。
469 |         problem, || 执行语句。
470 |         problem.constraints, || 执行语句。
471 |         material_cap_ratio=args.material_cap_ratio, || 赋值语句。
472 |         daily_floor_ratio=args.daily_floor_ratio, || 赋值语句。
473 |         donor_keep_ratio=args.donor_keep_ratio, || 赋值语句。
474 |         daily_cap_ratio=args.daily_cap_ratio, || 赋值语句。
475 |         reserve_ratio=args.reserve_ratio, || 赋值语句。
476 |         coverage_bonus=args.coverage_bonus, || 赋值语句。
477 |         budget_mode=args.budget_mode, || 赋值语句。
478 |         smooth_strength=args.smooth_strength, || 赋值语句。
479 |         smooth_passes=args.smooth_passes, || 赋值语句。
480 |     ) || 执行语句。
481 |     if bool(getattr(args, "no_pipeline", False)): || 条件分支。
482 |         # Keep initializer+mutator, but bypass all repair/smoothing so users can do ablation. || 注释：解释当前代码段用途或工程约束。
483 |         pipeline.repair = None || 赋值语句。
484 |     bias_module = ( || 赋值语句。
485 |         None || 执行语句。
486 |         if args.no_bias || 条件分支。
487 |         else build_production_bias_module( || 其他情况分支。
488 |             problem, || 执行语句。
489 |             weights={ || 赋值语句。
490 |                 "coverage_reward": args.coverage_reward, || 执行语句。
491 |                 "smoothness_penalty": args.smoothness_penalty, || 执行语句。
492 |                 "variance_penalty": args.variance_penalty, || 执行语句。
493 |             }, || 执行语句。
494 |         ) || 执行语句。
495 |     ) || 执行语句。
496 | 
497 |     total_batch = max(8, int(args.pop_size)) || 赋值语句。
498 |     explorer_batch = max(4, int(total_batch * 0.65)) || 赋值语句。
499 |     exploiter_batch = max(4, total_batch - explorer_batch) || 赋值语句。
500 | 
501 |     roles = [] || 赋值语句。
502 |     if str(getattr(args, "explorer_adapter", "moead")).lower() == "random": || 条件分支。
503 |         roles.append( || 执行语句。
504 |             RoleSpec( || 定义角色规格（名称、适配器、单元数、权重）。
505 |                 name="explorer", || 赋值语句。
506 |                 adapter=lambda uid: ProductionRandomSearchAdapter(batch_size=max(4, explorer_batch // 4)), || 赋值语句。
507 |                 n_units=4, || 赋值语句。
508 |                 weight=1.0, || 赋值语句。
509 |             ) || 执行语句。
510 |         ) || 执行语句。
511 |     else: || 其他情况分支。
512 |         moead_pop = max(32, int(getattr(args, "moead_pop_size", max(64, args.pop_size // 2)))) || 赋值语句。
513 |         moead_neighbor = max(2, int(getattr(args, "moead_neighborhood", 20))) || 赋值语句。
514 |         moead_nr = max(1, int(getattr(args, "moead_nr", 2))) || 赋值语句。
515 |         moead_delta = float(getattr(args, "moead_delta", 0.9)) || 赋值语句。
516 |         roles.append( || 执行语句。
517 |             RoleSpec( || 定义角色规格（名称、适配器、单元数、权重）。
518 |                 name="explorer", || 赋值语句。
519 |                 adapter=lambda uid: MOEADAdapter( || 为 explorer 角色配置 MOEA/D。
520 |                     MOEADConfig( || 执行语句。
521 |                         population_size=moead_pop, || 赋值语句。
522 |                         neighborhood_size=moead_neighbor, || 赋值语句。
523 |                         batch_size=max(4, explorer_batch), || 赋值语句。
524 |                         delta=moead_delta, || 赋值语句。
525 |                         nr=moead_nr, || 赋值语句。
526 |                         variation="pipeline", || 赋值语句。
527 |                         random_seed=(None if args.seed is None else int(args.seed) + int(uid)), || 赋值语句。
528 |                     ) || 执行语句。
529 |                 ), || 执行语句。
530 |                 n_units=1, || 赋值语句。
531 |                 weight=1.0, || 赋值语句。
532 |             ) || 执行语句。
533 |         ) || 执行语句。
534 |     if str(getattr(args, "exploiter_adapter", "vns")).lower() == "local": || 条件分支。
535 |         roles.append( || 执行语句。
536 |             RoleSpec( || 定义角色规格（名称、适配器、单元数、权重）。
537 |                 name="exploiter", || 赋值语句。
538 |                 adapter=lambda uid: ProductionLocalSearchAdapter(batch_size=max(2, exploiter_batch // 2)), || 赋值语句。
539 |                 n_units=2, || 赋值语句。
540 |                 weight=1.0, || 赋值语句。
541 |             ) || 执行语句。
542 |         ) || 执行语句。
543 |     else: || 其他情况分支。
544 |         vns_batch = max(4, int(getattr(args, "vns_batch_size", exploiter_batch))) || 赋值语句。
545 |         vns_kmax = max(1, int(getattr(args, "vns_k_max", 4))) || 赋值语句。
546 |         vns_sigma = float(getattr(args, "vns_base_sigma", 0.2)) || 赋值语句。
547 |         roles.append( || 执行语句。
548 |             RoleSpec( || 定义角色规格（名称、适配器、单元数、权重）。
549 |                 name="exploiter", || 赋值语句。
550 |                 adapter=lambda uid: VNSAdapter( || 为 exploiter 角色配置 VNS。
551 |                     VNSConfig( || 执行语句。
552 |                         batch_size=vns_batch, || 赋值语句。
553 |                         k_max=vns_kmax, || 赋值语句。
554 |                         base_sigma=vns_sigma, || 赋值语句。
555 |                         scale=1.6, || 赋值语句。
556 |                         objective_aggregation="sum", || 赋值语句。
557 |                     ) || 执行语句。
558 |                 ), || 执行语句。
559 |                 n_units=1, || 赋值语句。
560 |                 weight=1.0, || 赋值语句。
561 |             ) || 执行语句。
562 |         ) || 执行语句。
563 | 
564 |     cfg = MultiStrategyConfig( || 赋值语句。
565 |         total_batch_size=total_batch, || 赋值语句。
566 |         objective_aggregation="sum", || 赋值语句。
567 |         adapt_weights=True, || 赋值语句。
568 |         stagnation_window=max(5, int(args.adapt_interval)), || 赋值语句。
569 |         enable_regions=False, || 赋值语句。
570 |         region_update_interval=max(0, int(args.comm_interval)), || 赋值语句。
571 |         phase_schedule=(("explore", max(5, int(args.generations // 3))), ("exploit", -1)), || 赋值语句。
572 |         phase_roles={"explore": ["explorer"], "exploit": ["exploiter"]}, || 赋值语句。
573 |     ) || 执行语句。
574 | 
575 |     controller = MultiStrategyControllerAdapter(roles=roles, config=cfg) || 多角色控制器：统一调度 explorer/exploiter。
576 | 
577 |     SolverClass = with_parallel_evaluation(ComposableSolver) || 包装求解器以启用并行评估。
578 |     factory = ( || 赋值语句。
579 |         _build_problem_factory(args) || 执行语句。
580 |         if args.parallel and args.parallel_backend in ("process", "ray") || 条件分支。
581 |         else None || 其他情况分支。
582 |     ) || 执行语句。
583 |     solver = SolverClass( || 赋值语句。
584 |         problem=problem, || 赋值语句。
585 |         adapter=controller, || 赋值语句。
586 |         representation_pipeline=pipeline, || 赋值语句。
587 |         bias_module=bias_module, || 赋值语句。
588 |         enable_parallel=bool(args.parallel), || 赋值语句。
589 |         parallel_backend=args.parallel_backend, || 赋值语句。
590 |         parallel_max_workers=args.parallel_workers, || 赋值语句。
591 |         parallel_chunk_size=args.parallel_chunk_size, || 赋值语句。
592 |         parallel_verbose=bool(args.parallel_verbose), || 赋值语句。
593 |         parallel_precheck=not bool(args.parallel_no_precheck), || 赋值语句。
594 |         parallel_strict=bool(args.parallel_strict), || 赋值语句。
595 |         parallel_problem_factory=factory, || 赋值语句。
596 |     ) || 执行语句。
597 |     if not bool(getattr(args, "no_run_logs", False)): || 条件分支。
598 |         repo_root = Path(__file__).resolve().parents[1] || 赋值语句。
599 |         run_dir = Path(args.run_dir) if getattr(args, "run_dir", None) else (repo_root / "runs" / "production_schedule") || 赋值语句。
600 |         run_id = str(args.run_id) if getattr(args, "run_id", None) else datetime.now().strftime("%Y%m%d_%H%M%S") || 赋值语句。
601 |         run_dir = run_dir.expanduser().resolve() || 赋值语句。
602 |         run_dir.mkdir(parents=True, exist_ok=True) || 赋值语句。
603 |         solver.add_plugin( || 执行语句。
604 |             BenchmarkHarnessPlugin( || 执行语句。
605 |                 config=BenchmarkHarnessConfig( || 赋值语句。
606 |                     output_dir=str(run_dir), || 赋值语句。
607 |                     run_id=str(run_id), || 赋值语句。
608 |                     seed=None if args.seed is None else int(args.seed), || 赋值语句。
609 |                     log_every=int(getattr(args, "log_every", 1) or 1), || 赋值语句。
610 |                     flush_every=10, || 赋值语句。
611 |                     overwrite=True, || 赋值语句。
612 |                 ) || 执行语句。
613 |             ) || 执行语句。
614 |         ) || 执行语句。
615 |         solver.add_plugin( || 执行语句。
616 |             ModuleReportPlugin( || 执行语句。
617 |                 config=ModuleReportConfig( || 赋值语句。
618 |                     output_dir=str(run_dir), || 赋值语句。
619 |                     run_id=str(run_id), || 赋值语句。
620 |                     write_bias_markdown=not bool(getattr(args, "no_bias_md", False)), || 赋值语句。
621 |                 ) || 执行语句。
622 |             ) || 执行语句。
623 |         ) || 执行语句。
624 |         if not bool(getattr(args, "no_profile", False)): || 条件分支。
625 |             solver.add_plugin( || 执行语句。
626 |                 ProfilerPlugin( || 执行语句。
627 |                     config=ProfilerConfig( || 赋值语句。
628 |                         output_dir=str(run_dir), || 赋值语句。
629 |                         run_id=str(run_id), || 赋值语句。
630 |                         overwrite=True, || 赋值语句。
631 |                         flush_every=0, || 赋值语句。
632 |                     ) || 执行语句。
633 |                 ) || 执行语句。
634 |             ) || 执行语句。
635 |         print(f"[run] logs_dir={run_dir} run_id={run_id}") || 赋值语句。
636 |     solver.add_plugin(ParetoArchivePlugin()) || 挂载 Pareto 档案插件。
637 |     solver.add_plugin(ConsoleProgressPlugin(report_every=args.report_every)) || 挂载进度输出插件。
638 |     solver.set_max_steps(int(args.generations)) || 执行语句。
639 |     return solver || 返回输出。
640 | 
641 | 
642 | def run_multi_agent(problem, args): || 执行多策略协同主流程。
643 |     """ || 文档字符串开始：说明模块或函数意图。
644 |     \"multi-agent\" in this repo is implemented as \"multi-strategy cooperation\": || 文档字符串内容。
645 |     multiple strategy adapters propose candidates in parallel, while the solver || 文档字符串内容。
646 |     evaluates them together. || 文档字符串内容。
647 |     """ || 文档字符串结束。
648 |     solver = build_multi_agent_solver(problem, args) || 赋值语句。
649 |     solver.run() || 执行语句。
650 | 
651 |     individuals, objectives = _extract_pareto(solver) || 赋值语句。
652 |     print(f"Pareto size: {0 if individuals is None else len(individuals)}") || 执行语句。
653 |     choices = _choose_pareto_solutions(problem, individuals, objectives) if individuals is not None else [] || 赋值语句。
654 |     if choices and (not bool(getattr(args, "no_export", False))): || 条件分支。
655 |         base_export = Path(args.export) if args.export else None || 赋值语句。
656 |         for label, chosen, obj in choices: || 循环遍历。
657 |             schedule = problem.decode_schedule(chosen) || 赋值语句。
658 |             summary = problem.summarize_schedule(schedule) || 赋值语句。
659 |             print(f"Best ({'lowest penalty' if label == 'penalty' else 'highest production'}):") || 执行语句。
660 |             print(f"  objectives: {obj}") || 执行语句。
661 |             for key, value in summary.items(): || 循环遍历。
662 |                 print(f"  {key}: {value:.4f}") || 执行语句。
663 |             export_path = _resolve_export_path(base_export, label) || 赋值语句。
664 |             _export_schedule(export_path, schedule) || 执行语句。
665 |             print(f"Saved schedule to: {export_path}") || 执行语句。
666 | 
667 |     if (not bool(getattr(args, "no_export", False))) and args.pareto_export != 0 and individuals is not None: || 条件分支。
668 |         base_export = Path(args.export) if args.export else None || 赋值语句。
669 |         exported = _export_pareto_batch( || 赋值语句。
670 |             problem, || 执行语句。
671 |             individuals, || 执行语句。
672 |             objectives, || 执行语句。
673 |             base_export, || 执行语句。
674 |             mode=args.pareto_export_mode, || 赋值语句。
675 |             limit=args.pareto_export, || 赋值语句。
676 |         ) || 执行语句。
677 |         if exported: || 条件分支。
678 |             print(f"Exported {exported} Pareto schedules.") || 执行语句。
679 | 
680 | 
681 | def build_parser() -> argparse.ArgumentParser: || 命令行参数定义入口。
682 |     parser = argparse.ArgumentParser(description="Refactored production scheduling (pipeline-first).") || 赋值语句。
683 |     parser.add_argument("--solver", choices=["multi-agent"], default="multi-agent") || 赋值语句。
684 |     parser.add_argument("--ui", action="store_true", help="Launch Run Inspector UI before running.") || 赋值语句。
685 |     parser.add_argument("--bom", type=str, default=None) || 赋值语句。
686 |     parser.add_argument("--supply", type=str, default=None) || 赋值语句。
687 |     parser.add_argument("--machines", type=int, default=22) || 赋值语句。
688 |     parser.add_argument("--materials", type=int, default=156) || 赋值语句。
689 |     parser.add_argument("--days", type=int, default=31) || 赋值语句。
690 |     parser.add_argument("--max-machines", type=int, default=8) || 赋值语句。
691 |     parser.add_argument("--min-machines", type=int, default=5) || 赋值语句。
692 |     parser.add_argument("--min-prod", type=int, default=50) || 赋值语句。
693 |     parser.add_argument("--max-prod", type=int, default=3000) || 赋值语句。
694 |     parser.add_argument("--shortage-unit-penalty", type=float, default=1.0) || 赋值语句。
695 |     parser.add_argument( || 执行语句。
696 |         "--penalty-objective", || 执行语句。
697 |         action="store_true", || 赋值语句。
698 |         help="Include scaled penalty as an objective (default: constraint-only).", || 赋值语句。
699 |     ) || 执行语句。
700 |     parser.add_argument( || 执行语句。
701 |         "--penalty-scale", || 执行语句。
702 |         type=float, || 赋值语句。
703 |         default=0.001, || 赋值语句。
704 |         help="Scale for penalty objective when enabled.", || 赋值语句。
705 |     ) || 执行语句。
706 |     parser.add_argument("--pop-size", type=int, default=200) || 赋值语句。
707 |     parser.add_argument("--generations", type=int, default=50) || 赋值语句。
708 |     parser.add_argument("--crossover-rate", type=float, default=0.85) || 赋值语句。
709 |     parser.add_argument("--mutation-rate", type=float, default=0.15) || 赋值语句。
710 |     parser.add_argument("--report-every", type=int, default=10) || 赋值语句。
711 |     parser.add_argument("--run-dir", type=str, default=None, help="Auto logs dir for benchmark/module reports.") || 赋值语句。
712 |     parser.add_argument("--run-id", type=str, default=None, help="Run id for reports (default: timestamp).") || 赋值语句。
713 |     parser.add_argument("--log-every", type=int, default=1, help="BenchmarkHarness CSV log frequency.") || 赋值语句。
714 |     parser.add_argument("--no-bias-md", action="store_true", help="Disable writing bias.md in module report.") || 赋值语句。
715 |     parser.add_argument("--no-run-logs", action="store_true", help="Disable automatic benchmark/module reports.") || 赋值语句。
716 |     parser.add_argument("--no-profile", action="store_true", help="Disable ProfilerPlugin output in run logs.") || 赋值语句。
717 |     parser.add_argument("--no-export", action="store_true", help="Disable exporting schedules (no Excel/CSV output).") || 赋值语句。
718 |     parser.add_argument("--comm-interval", type=int, default=5) || 赋值语句。
719 |     parser.add_argument("--adapt-interval", type=int, default=20) || 赋值语句。
720 |     parser.add_argument( || 执行语句。
721 |         "--explorer-adapter", || 执行语句。
722 |         choices=["moead", "random"], || 赋值语句。
723 |         default="moead", || 赋值语句。
724 |         help="Explorer role adapter: moead (default) or random search.", || 赋值语句。
725 |     ) || 执行语句。
726 |     parser.add_argument("--vns-batch-size", type=int, default=96, help="VNS candidates per step.") || 赋值语句。
727 |     parser.add_argument("--vns-k-max", type=int, default=4, help="VNS neighborhood depth.") || 赋值语句。
728 |     parser.add_argument("--vns-base-sigma", type=float, default=0.2, help="VNS initial mutation sigma.") || 赋值语句。
729 |     parser.add_argument( || 执行语句。
730 |         "--exploiter-adapter", || 执行语句。
731 |         choices=["vns", "local"], || 赋值语句。
732 |         default="vns", || 赋值语句。
733 |         help="Exploiter role adapter: vns (default) or local search.", || 赋值语句。
734 |     ) || 执行语句。
735 |     parser.add_argument("--moead-pop-size", type=int, default=96, help="MOEA/D subproblem population size.") || 赋值语句。
736 |     parser.add_argument("--moead-neighborhood", type=int, default=20, help="MOEA/D neighborhood size.") || 赋值语句。
737 |     parser.add_argument("--moead-delta", type=float, default=0.9, help="MOEA/D neighbor sampling probability.") || 赋值语句。
738 |     parser.add_argument("--moead-nr", type=int, default=2, help="MOEA/D max replacements per offspring.") || 赋值语句。
739 |     parser.add_argument("--parallel", action="store_true", help="Enable parallel evaluation (CPU).") || 赋值语句。
740 |     parser.add_argument( || 执行语句。
741 |         "--parallel-backend", || 执行语句。
742 |         choices=["auto", "process", "thread", "joblib", "ray"], || 赋值语句。
743 |         default="process", || 赋值语句。
744 |         help="Parallel backend (process recommended for heavy Python evaluation; ray is optional).", || 赋值语句。
745 |     ) || 执行语句。
746 |     parser.add_argument("--parallel-workers", type=int, default=None, help="Parallel worker count (default: auto).") || 赋值语句。
747 |     parser.add_argument("--parallel-chunk-size", type=int, default=None, help="Task chunk size (default: auto).") || 赋值语句。
748 |     parser.add_argument("--parallel-verbose", action="store_true", help="Verbose parallel evaluator logging.") || 赋值语句。
749 |     parser.add_argument( || 执行语句。
750 |         "--parallel-no-precheck", || 执行语句。
751 |         action="store_true", || 赋值语句。
752 |         help="Disable picklability precheck/fallback for process backend.", || 赋值语句。
753 |     ) || 执行语句。
754 |     parser.add_argument("--parallel-strict", action="store_true", help="Strict mode: do not fallback on parallel errors.") || 赋值语句。
755 |     parser.add_argument("--seed", type=int, default=42) || 赋值语句。
756 |     parser.add_argument("--no-bias", action="store_true") || 赋值语句。
757 |     parser.add_argument( || 执行语句。
758 |         "--no-pipeline", || 执行语句。
759 |         action="store_true", || 赋值语句。
760 |         help="Ablation: keep initializer+mutator, but disable repair/smoothing in the pipeline.", || 赋值语句。
761 |     ) || 执行语句。
762 |     parser.add_argument( || 执行语句。
763 |         "--material-cap-ratio", || 执行语句。
764 |         type=float, || 赋值语句。
765 |         default=2.0, || 赋值语句。
766 |         help="Daily material usage cap vs. average allocation (higher = higher output).", || 赋值语句。
767 |     ) || 执行语句。
768 |     parser.add_argument( || 执行语句。
769 |         "--daily-floor-ratio", || 执行语句。
770 |         type=float, || 赋值语句。
771 |         default=0.55, || 赋值语句。
772 |         help="Daily production floor vs. average allocation (higher = more stable output).", || 赋值语句。
773 |     ) || 执行语句。
774 |     parser.add_argument( || 执行语句。
775 |         "--donor-keep-ratio", || 执行语句。
776 |         type=float, || 赋值语句。
777 |         default=0.7, || 赋值语句。
778 |         help="Minimum fraction of a donor day's total kept during backfill.", || 赋值语句。
779 |     ) || 执行语句。
780 |     parser.add_argument( || 执行语句。
781 |         "--daily-cap-ratio", || 执行语句。
782 |         type=float, || 赋值语句。
783 |         default=2.2, || 赋值语句。
784 |         help="Daily production cap vs. average allocation (higher = higher output).", || 赋值语句。
785 |     ) || 执行语句。
786 |     parser.add_argument( || 执行语句。
787 |         "--budget-mode", || 执行语句。
788 |         choices=["average", "today"], || 赋值语句。
789 |         default="today", || 赋值语句。
790 |         help="Daily material budget mode (average = capped by remaining days, today = use current stock).", || 赋值语句。
791 |     ) || 执行语句。
792 |     parser.add_argument( || 执行语句。
793 |         "--smooth-strength", || 执行语句。
794 |         type=float, || 赋值语句。
795 |         default=0.6, || 赋值语句。
796 |         help="Forward smoothing strength for daily totals (0 = off).", || 赋值语句。
797 |     ) || 执行语句。
798 |     parser.add_argument( || 执行语句。
799 |         "--smooth-passes", || 执行语句。
800 |         type=int, || 赋值语句。
801 |         default=2, || 赋值语句。
802 |         help="Number of forward smoothing passes.", || 赋值语句。
803 |     ) || 执行语句。
804 |     parser.add_argument( || 执行语句。
805 |         "--reserve-ratio", || 执行语句。
806 |         type=float, || 赋值语句。
807 |         default=0.6, || 赋值语句。
808 |         help="Reserve ratio for next-day continuity (lower = higher output).", || 赋值语句。
809 |     ) || 执行语句。
810 |     parser.add_argument( || 执行语句。
811 |         "--pareto-export", || 执行语句。
812 |         type=int, || 赋值语句。
813 |         default=-1, || 赋值语句。
814 |         help="Export N Pareto schedules (-1 = all, 0 = off).", || 赋值语句。
815 |     ) || 执行语句。
816 |     parser.add_argument( || 执行语句。
817 |         "--pareto-export-mode", || 执行语句。
818 |         choices=["front", "crowding", "production"], || 赋值语句。
819 |         default="crowding", || 赋值语句。
820 |         help="How to pick Pareto schedules to export.", || 赋值语句。
821 |     ) || 执行语句。
822 |     parser.add_argument( || 执行语句。
823 |         "--coverage-bonus", || 执行语句。
824 |         type=float, || 赋值语句。
825 |         default=300.0, || 赋值语句。
826 |         help="Priority bonus for machines never produced yet (higher = richer coverage).", || 赋值语句。
827 |     ) || 执行语句。
828 |     parser.add_argument( || 执行语句。
829 |         "--coverage-reward", || 执行语句。
830 |         type=float, || 赋值语句。
831 |         default=0.03, || 赋值语句。
832 |         help="Bias reward for machine coverage ratio (higher = richer coverage).", || 赋值语句。
833 |     ) || 执行语句。
834 |     parser.add_argument( || 执行语句。
835 |         "--smoothness-penalty", || 执行语句。
836 |         type=float, || 赋值语句。
837 |         default=0.01, || 赋值语句。
838 |         help="Bias penalty weight for day-to-day changes (higher = smoother daily totals).", || 赋值语句。
839 |     ) || 执行语句。
840 |     parser.add_argument( || 执行语句。
841 |         "--variance-penalty", || 执行语句。
842 |         type=float, || 赋值语句。
843 |         default=0.03, || 赋值语句。
844 |         help="Bias penalty weight for daily production variance (higher = more stable daily totals).", || 赋值语句。
845 |     ) || 执行语句。
846 |     parser.add_argument( || 执行语句。
847 |         "--export", || 执行语句。
848 |         type=str, || 赋值语句。
849 |         default=None, || 赋值语句。
850 |         help="Save selected schedules; suffixes _penalty/_production will be appended.", || 赋值语句。
851 |     ) || 执行语句。
852 |     return parser || 返回输出。
853 | 
854 | 
855 | 
856 | def _build_solver_from_args(args) -> ComposableSolver: || 定义函数 `_build_solver_from_args`。
857 |     problem = _build_problem(args) || 赋值语句。
858 |     return build_multi_agent_solver(problem, args) || 返回输出。
859 | 
860 | 
861 | 
862 | def build_solver(argv: Optional[list] = None) -> ComposableSolver: || 定义函数 `build_solver`。
863 |     """ || 文档字符串开始：说明模块或函数意图。
864 |     Build solver for Run Inspector / programmatic launch. || 文档字符串内容。
865 | 
866 |     Usage: || 文档字符串内容。
867 |         python -m nsgablack run_inspector --entry working_integrated_optimizer.py:build_solver || 文档字符串内容。
868 |     """ || 文档字符串结束。
869 |     parser = build_parser() || 赋值语句。
870 |     args = parser.parse_args(argv if argv is not None else []) || 赋值语句。
871 |     if not getattr(args, "run_id", None): || 条件分支。
872 |         args.run_id = datetime.now().strftime("%Y%m%d_%H%M%S") || 赋值语句。
873 | 
874 |     random.seed(args.seed) || 执行语句。
875 |     np.random.seed(args.seed) || 执行语句。
876 | 
877 |     return _build_solver_from_args(args) || 返回输出。
878 | 
879 | 
880 | def main(args=None): || 定义函数 `main`。
881 |     if args is None: || 条件分支。
882 |         args = build_parser().parse_args() || 赋值语句。
883 |     # Defaults: this workload is evaluation-heavy (Python loops + constraints), || 注释：解释当前代码段用途或工程约束。
884 |     # so parallel evaluation is almost always beneficial on a high-core CPU. || 注释：解释当前代码段用途或工程约束。
885 |     if not getattr(args, "parallel", False): || 条件分支。
886 |         args.parallel = True || 赋值语句。
887 |     if not getattr(args, "parallel_backend", None): || 条件分支。
888 |         args.parallel_backend = "process" || 赋值语句。
889 |     if getattr(args, "parallel_backend", None) in ("process", "ray") and getattr(args, "parallel_workers", None) is None: || 条件分支。
890 |         cpu = int(os.cpu_count() or 8) || 赋值语句。
891 |         # Leave some cores for OS / IO; cap to avoid excessive memory pressure. || 注释：解释当前代码段用途或工程约束。
892 |         args.parallel_workers = max(4, min(cpu - 2, 12)) || 赋值语句。
893 | 
894 |     print( || 执行语句。
895 |         "[run] solver=multi-agent " || 赋值语句。
896 |         f"parallel={bool(args.parallel)} backend={args.parallel_backend} workers={args.parallel_workers} " || 赋值语句。
897 |         f"generations={args.generations} pop_size={args.pop_size}" || 赋值语句。
898 |     ) || 执行语句。
899 |     if bool(args.parallel) and args.parallel_backend == "process": || 条件分支。
900 |         print("[run] Note: first parallel step may be slow on Windows due to process spawn + warmup.") || 执行语句。
901 |     if bool(args.parallel) and args.parallel_backend == "ray": || 条件分支。
902 |         print("[run] Note: ray backend requires `pip install ray`; it will start a local runtime if not already running.") || 执行语句。
903 | 
904 |     random.seed(args.seed) || 执行语句。
905 |     np.random.seed(args.seed) || 执行语句。
906 | 
907 |     problem = _build_problem(args) || 赋值语句。
908 |     run_multi_agent(problem, args) || 执行多策略协同主流程。
909 | 
910 | 
911 | if __name__ == "__main__": || 条件分支。
912 |     args = build_parser().parse_args() || 赋值语句。
913 |     if args.ui: || 条件分支。
914 |         if not getattr(args, "run_id", None): || 条件分支。
915 |             args.run_id = datetime.now().strftime("%Y%m%d_%H%M%S") || 赋值语句。
916 |         launch_from_builder( || 通过 builder 启动 Run Inspector UI。
917 |             lambda: _build_solver_from_args(args), || 执行语句。
918 |             entry_label="working_integrated_optimizer.py:build_solver", || 赋值语句。
919 |         ) || 执行语句。
920 |         raise SystemExit(0) || 主动抛错。
921 |     main(args) || 执行语句。
922 | 
```
