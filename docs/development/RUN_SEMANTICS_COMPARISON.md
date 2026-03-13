# 运行循环语义对照表

## 概述

本文档对比 `SolverBase.run()` 和 `EvolutionSolver.run()` 的语义差异，确保生命周期钩子、终止条件、状态管理的一致性。

## 1. 方法签名差异

| 求解器 | 签名 | 返回类型 |
|--------|------|----------|
| `SolverBase` | `run(max_steps: Optional[int] = None)` | `Dict[str, Any]` |
| `EvolutionSolver` | `run(return_experiment: bool = False, return_dict: bool = False)` | `Union[Tuple, Dict, ExperimentResult]` |

**问题**:
- 返回类型不一致，违反 Liskov 替换原则
- `EvolutionSolver` 忽略 `max_steps` 参数（通过 `max_generations` 控制）

**推荐**: `EvolutionSolver.run()` 应接受 `max_steps` 并覆盖 `max_generations`

---

## 2. 生命周期钩子对比

### SolverBase.run() (委托给 solver_helpers.run_solver_loop)

```python
# 启动前
self.running = True
self.start_time = time.time()
self.plugin_manager.on_solver_init(self)

# 初始化
if self.generation == 0 and not plugin_init_handled:
    self.plugin_manager.on_population_init(self, self.population)

# 主循环
for step in range(max_steps):
    self.plugin_manager.on_generation_start(self.generation)
    self.step()
    self.plugin_manager.on_generation_end(self.generation)
    self.generation += 1
    if self.stop_requested:
        break

# 清理
result = {...}
self.plugin_manager.on_solver_finish(result)
self.running = False
```

### EvolutionSolver.run()

```python
# 启动前
self.running = True
self.start_time = time.time()
self.plugin_manager.on_solver_init(self)
resume_loaded = getattr(self, "_resume_loaded", False)

# 初始化
if not resume_loaded:
    self.initialize_population(...)
else:
    # 恢复逻辑
    start_generation = int(getattr(self, "_resume_cursor", 0))

# 准备
self.setup()

# 主循环
for gen in range(start_generation, max_generations):
    self.generation = int(gen)
    self.plugin_manager.on_generation_start(self.generation)
    self.plugin_manager.on_step(self, self.generation)
    
    # 自适应参数
    progress = float(gen) / float(max_g)
    self.mutation_range = ...
    
    self.step()
    
    self.generation = int(gen + 1)  # 注意：循环内递增
    self.plugin_manager.on_generation_end(self.generation)
    
    if self.stop_requested:
        break

# 清理
self.teardown()
self.running = False
self.run_count += 1
result = {...}
self.plugin_manager.on_solver_finish(result)
```

---

## 3. 关键差异点

### 3.1 插件钩子顺序

| 钩子 | SolverBase | EvolutionSolver | 一致性 |
|------|-----------|----------------|--------|
| `on_solver_init` | ✅ 启动前 | ✅ 启动前 | ✅ 一致 |
| `on_population_init` | ✅ 首次初始化 | ✅ `initialize_population` 内 | ✅ 一致 |
| `on_generation_start` | ✅ step 前 | ✅ step 前 | ✅ 一致 |
| `on_step` | ❌ 无 | ✅ step 前 | ⚠️ **不一致** |
| `on_generation_end` | ✅ step 后 | ✅ step 后 | ✅ 一致 |
| `on_solver_finish` | ✅ 循环后 | ✅ 循环后 | ✅ 一致 |

**问题**: `EvolutionSolver` 额外调用 `on_step(self, generation)`，`SolverBase` 无此钩子。

### 3.2 generation 计数器管理

| 操作 | SolverBase | EvolutionSolver |
|------|-----------|----------------|
| 循环变量 | `step` (独立计数) | `gen` (从 `start_generation` 开始) |
| `self.generation` 更新时机 | 循环后递增 | **循环内先设置 `gen`，step 后设置 `gen+1`** |
| 终止条件 | `step < max_steps` | `gen < max_generations` |

**问题**: `EvolutionSolver` 在同一循环内两次更新 `self.generation`，可能导致插件观察到不一致状态。

```python
# EvolutionSolver 循环内
self.generation = int(gen)            # 设置为当前代数
self.plugin_manager.on_generation_start(self.generation)
self.step()
self.generation = int(gen + 1)        # 设置为下一代数 ⚠️
self.plugin_manager.on_generation_end(self.generation)
```

### 3.3 终止条件检查

| 求解器 | 检查位置 | 行为 |
|--------|---------|------|
| `SolverBase` | 循环末尾 | `if self.stop_requested: break` |
| `EvolutionSolver` | 循环开头 | `if self.stop_requested: break` |

**差异**: 检查时机不同，但语义基本一致。

### 3.4 history 写入时机

| 求解器 | 时机 |
|--------|------|
| `SolverBase` | **不负责写入**（委托给 adapter/plugin） |
| `EvolutionSolver` | 每次 `step()` 后通过 `record_history()` 写入 |

**问题**: 职责不清晰，`SolverBase` 没有默认 history 管理。

### 3.5 异常处理

| 求解器 | 异常处理 |
|--------|---------|
| `SolverBase` | `run_solver_loop` 中有 `try-except`，调用 `report_soft_error` |
| `EvolutionSolver` | **无顶层异常处理**，异常会直接抛出 |

**问题**: 一致性缺失，`EvolutionSolver` 应统一异常策略。

---

## 4. 状态管理差异

### 4.1 运行计数器

| 字段 | SolverBase | EvolutionSolver |
|------|-----------|----------------|
| `run_count` | ❌ 无 | ✅ 每次 run 递增 |
| `last_result` | ✅ 有 | ✅ 有 |

### 4.2 自适应参数

| 字段 | SolverBase | EvolutionSolver |
|------|-----------|----------------|
| `mutation_range` | ❌ 无 | ✅ 基于 progress 衰减 |

---

## 5. 推荐改进方案

### 方案 A: 最小侵入（推荐）

1. **统一 `on_step` 钩子**:
   - 在 `SolverBase.run()` 中也调用 `on_step(self, step)`
   - 确保插件可以统一依赖此钩子

2. **修正 `generation` 更新语义**:
   ```python
   # EvolutionSolver.run() 修改为
   for gen in range(start_generation, max_generations):
       self.generation = int(gen)
       self.plugin_manager.on_generation_start(self.generation)
       self.plugin_manager.on_step(self, self.generation)
       self.step()
       # ❌ 删除: self.generation = int(gen + 1)
       self.plugin_manager.on_generation_end(self.generation)
       if self.stop_requested:
           break
   
   # 循环后统一递增
   self.generation = max_generations
   ```

3. **统一异常处理**:
   - `EvolutionSolver.run()` 包裹在 `try-except` 中
   - 调用 `report_soft_error` 记录失败

4. **兼容 `max_steps` 参数**:
   ```python
   def run(self, max_steps: Optional[int] = None, 
           return_experiment: bool = False, 
           return_dict: bool = False):
       if max_steps is not None:
           self.max_generations = int(max_steps)
           self.max_steps = int(max_steps)
       # ...
   ```

### 方案 B: 深度重构（长期）

1. **提取公共运行循环到基类**:
   ```python
   # SolverBase
   def _run_loop_core(self, start_step: int, max_steps: int):
       for step in range(start_step, max_steps):
           self.generation = step
           self.plugin_manager.on_generation_start(self.generation)
           self.plugin_manager.on_step(self, self.generation)
           
           self._before_step(step)  # 子类钩子
           self.step()
           self._after_step(step)   # 子类钩子
           
           self.plugin_manager.on_generation_end(self.generation)
           if self.stop_requested:
               break
   ```

2. **`EvolutionSolver` 只覆盖钩子**:
   ```python
   def _before_step(self, step: int):
       progress = float(step) / float(self.max_steps)
       self.mutation_range = ...
   
   def _after_step(self, step: int):
       self.update_pareto_solutions()
       self.record_history()
       self._refresh_best()
   ```

---

## 6. 回归测试要求

创建测试文件 `tests/test_run_semantics_unified.py`:

### 6.1 钩子顺序测试
```python
def test_plugin_hook_order_consistency():
    """确保 SolverBase 和 EvolutionSolver 钩子顺序一致"""
    hook_recorder = HookRecorderPlugin()
    
    for solver_cls in [SolverBase, EvolutionSolver]:
        solver = solver_cls(problem=SimpleProblem())
        solver.add_plugin(hook_recorder)
        solver.run(max_steps=3)
        
        expected_order = [
            'on_solver_init',
            'on_population_init',
            'on_generation_start', 'on_step', 'on_generation_end',  # gen 0
            'on_generation_start', 'on_step', 'on_generation_end',  # gen 1
            'on_generation_start', 'on_step', 'on_generation_end',  # gen 2
            'on_solver_finish',
        ]
        assert hook_recorder.order == expected_order
```

### 6.2 generation 计数器测试
```python
def test_generation_counter_consistency():
    """确保 generation 在插件钩子中观察到的值一致"""
    counter_checker = GenerationCounterPlugin()
    
    for solver_cls in [SolverBase, EvolutionSolver]:
        solver = solver_cls(problem=SimpleProblem())
        solver.add_plugin(counter_checker)
        solver.run(max_steps=5)
        
        # on_generation_start 和 on_generation_end 应看到同一个 generation
        assert counter_checker.all_consistent()
```

### 6.3 异常处理测试
```python
def test_exception_handling_consistency():
    """确保异常处理行为一致"""
    for solver_cls in [SolverBase, EvolutionSolver]:
        solver = solver_cls(problem=FaultyProblem())
        solver.plugin_strict = False
        
        result = solver.run(max_steps=3)
        
        # 软错误模式下应继续运行并返回结果
        assert result is not None
        assert 'error' not in result or result['error'] is None
```

---

## 7. 实施计划

### 阶段 1: 文档与测试（本阶段）
- [x] 创建本对照表
- [ ] 编写回归测试套件
- [ ] 在现有测试中验证钩子顺序

### 阶段 2: 最小修复（P0）
- [ ] 修正 `EvolutionSolver` 双重 `generation` 更新
- [ ] 添加顶层异常处理
- [ ] 统一 `on_step` 钩子

### 阶段 3: 增强兼容性（P1）
- [ ] `EvolutionSolver.run()` 接受 `max_steps`
- [ ] 统一返回类型（推荐返回 Dict）

### 阶段 4: 长期重构（P2）
- [ ] 提取公共循环逻辑
- [ ] 规范化子类扩展点

---

## 8. 向后兼容性声明

所有改动必须保持向后兼容:
- `EvolutionSolver.run(return_experiment=True)` 继续支持
- 现有插件不需要修改
- `generation` 计数器外部观察行为不变

---

## 附录: 相关文件

- `core/blank_solver.py::SolverBase.run` (Line 880)
- `core/evolution_solver.py::EvolutionSolver.run` (Line 629)
- `core/solver_helpers/run_loop.py::run_solver_loop`
- `plugins/base.py::PluginManager` 钩子定义
