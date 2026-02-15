# Run Inspector 使用说明（可视化先验 / 运行前审查）

Run Inspector 是 NSGABlack 的“结构审计”界面。
它不是画曲线的 UI，而是让你在运行前就看见 **算法结构、组件搭配、缺失伙伴、实验快照**。

> 适用场景：
> - 多算法/多偏置/多插件组合时，避免“跑完才发现漏配”
> - 实验对比时，快速确认两次实验的结构差异
> - 运行后复盘：看清楚“当时到底勾选了什么”

---

## 1. 启动方式

```bash
python utils/viz/visualizer_tk.py --entry examples/dynamic_multi_strategy_demo.py:build_solver
```

- `--entry` 指向你的 `build_solver()` 函数。
- 运行后，会读取当前 solver wiring，并展示可开关的组件。

空启动模式（先用 Catalog 搜索，再 Load 文件）：

```bash
python -m nsgablack run_inspector --empty --workspace .
```

在 UI 顶部可直接：
- `Load`：选择/输入 `*.py` + 函数名（默认 `build_solver`）后加载
- `Refresh`：代码改动后重新读取当前 entry

---

## 2. 界面总览（你会看到什么）

左侧：**结构清单（wiring）**
- Solver / Adapter / Pipeline / Bias / Plugin
- 每个条目可勾选启用/禁用（固定项会灰显）

中间：**History（实验记录）**
- 每次 Run 会写入一条记录
- 自动显示 run_id、状态、结果、结构 hash

右侧：**功能面板（Tabs）**
- Details：单个组件详情 + Health
- Run：运行控制 + Run ID
- Contribution：模块贡献、对比、结构 hash 图谱
- Trajectory：策略权重轨迹（dynamic_switch）
- Catalog：组件搜索入口

---

## 3. 结构清单（wiring）怎么用

### 3.1 勾选 / 取消勾选
- Bias、Pipeline、Plugin 通常可开关
- Adapter 本体通常固定（灰显）
- 多策略协同会显示 `strategy: xxx`

### 3.2 缺失伙伴提示
- 缺失伙伴不会污染列表文本
- 进入 Details 时会显示 **Health: WARN**
- Health 仅在 Details 面板显示（避免噪音）

> 例：Signal-driven bias 没有挂评估插件时，会提示 WARN

---

## 4. 运行与快照

### 4.1 Run ID
- 默认：时间戳
- 也可手动输入，用于区分实验

### 4.2 Snapshot（结构快照）
每次运行会写入：
```
runs/visualizer/<run_id>.json
```
包含：
- adapter / pipeline / bias / plugins
- enabled 状态
- strategies / weights
- structure_hash（结构哈希）

---

## 5. Delta-first 对比（核心功能）

在 Contribution 页 → Compare：
1. 选择两个 run_id
2. 点击 Diff
3. 左侧列表会 **高亮差异项**（淡蓝底）
4. Diff 面板会显示具体差异

这可以直接回答：
> “这两次实验到底差在哪？”

---

## 6. 结构哈希图谱（Structure Hash Map）

Contribution 页新增：
- 按结构 hash 分组
- 快速判断哪些 run 是 **结构等价** 的

用途：
- 发现“重复实验”
- 找出结构相同但结果不同的 run

---

## 7. Bias 贡献与趋势

Contribution 页还会显示：
- 每个 bias 的 total / count / avg
- 点击 bias 可查看 per-call / per-generation 细节

这用于回答：
> “是哪个偏置主导了结果？”

---

## 8. 策略权重轨迹（Trajectory）

如果启用了 `dynamic_switch`：
- Trajectory 页会绘制权重变化曲线
- 支持多策略自动扩展

用途：
- 观察策略切换是否合理
- 验证动态协同逻辑

---

## 9. Catalog 搜索（可发现性）

Catalog 页：
- 支持关键词搜索
- 可过滤 kind（suite / bias / adapter / example 等）
- `Scope` 支持 `all / project / framework`（全部 / 本地项目组件 / 框架内组件）
- 选中条目会显示 `How to Use`（适用场景、最小接线、必配组件、配置键、示例入口）
- 选中条目会显示 `Context Contract`（requires/provides/mutates/cache/notes；为空也会显示 `(none)`）

用于快速回答：
> “这个功能到底有没有？”

---

## 10. 常见问题

**Q1：为什么结构哈希为空？**
- 旧快照可能没有 `structure_hash`，现在会自动计算

**Q2：我禁用了某策略，但动态权重还在变？**
- dynamic_switch 输出的是“运行中权重轨迹”
- 如果禁用了 strategy，权重应显示为 off / 0

**Q3：为什么提示 missing suite？**
- Suite 是权威组合入口
- 如果插件本体已启用，不会再提示 suite 缺失

---

## 11. 最重要的正确理解

Run Inspector 不是“好看 UI”，而是：

> **优化实验的结构审计与差异解释系统**

如果你能在运行前确认结构正确，运行后确认结构差异，
你的实验就不再是“凭感觉调参”，而是 **可解释的结构实验**。
