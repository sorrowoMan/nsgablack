# Supply Adjustment Nested（嵌套供应调整）

`Supply Adjustment Nested` 验证 nsgablack 的嵌套编排能力，用于运筹规划场景。

这个 case 直接优化 `production_scheduling/SUPPLY.xlsx` 中的供应事件时序。

## 这个 case 验证什么

- L1 搜索 supply-event date shifts（供应事件提前天数）。
- L2 调用 production scheduling scaffold，在调整后的供应表上评估生产排程。
- 可选 L0 搜索 material blacklist，用于控制内层搜索空间。
- 分布式 Redis workers 可以独立评估 nested outer candidates。
- 当前 runtime path 不使用 mlblack；这是 nsgablack-to-nsgablack 的嵌套运筹 case。

## 是否使用 mlblack

不使用。该 case 验证 nested nsgablack orchestration 和 L0 resource/design control。

## 层级（Layers）

| 层 | 作用 |
|---|---|
| L0 | 物料可调域设计，搜索 material blacklist。 |
| L1 | 供应事件调整，每个可调事件选择提前多少天。 |
| L2 | 在调整后的供应表上做 production scheduling evaluation。 |

## 规则（Rules）

- Day 0 supply 固定，不能调整。
- 事件只能提前，不能延后。
- 一个供应事件整体移动，不拆分。
- `--max-moved-events` 限制最大干预事件数。
- Export audit 检查 supply conservation、day-0 pollution、daily supply deltas 和 movement strength。

## 目标和指标（Objectives / Metrics）

| 指标 | 含义 |
|---|---|
| `-total_output` | L1/L2 生产质量目标；最小化它等价于最大化总产出。 |
| moved event count | 干预事件数量，越少越好。 |
| moved days | 总移动天数，越少越好。 |
| L0 runtime | 选中 material blacklist design 的运行成本。 |
| L0 quality gap | 缩小搜索空间造成的内层生产质量损失。 |
| blacklist size | L0 设计层的域大小控制信号。 |
| supply audit | 导出供应表的守恒与 day-0 安全检查。 |

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `solver/assembly.py` | L1/L2 正式 nested assembly。 |
| `solver/blacklist_assembly.py` | L0/L1/L2 正式 design assembly。 |
| `solver/run_case.py` | L1/L2 CLI。 |
| `solver/run_blacklist_case.py` | L0/L1/L2 CLI。 |
| `solver/run_nested_worker.py` | Redis worker，用于分布式 nested evaluation。 |
| `problem/` | Supply event shift 和 blacklist design problems。 |
| `pipeline/` | L0 binary representation pipeline。 |
| `plugins/` | Export 和 runtime plugin wiring。 |
| `reporting/` | Supply movement 和 conservation audit。 |
| `config/` | 可复现实验 presets。 |
| `SCENARIO_MATRIX.md` | Layer semantics、metrics 和 comparison protocol。 |

`working_nested_optimizer.py` 和 `working_blacklist_optimizer.py` 是 legacy compatibility shells。

## 运行 L1/L2

```powershell
python solver/run_case.py --parallel --parallel-backend thread --parallel-workers 8
```

本地 nested 推荐显式拆分 outer/inner 后端：

```powershell
python solver/run_case.py `
  --parallel `
  --outer-parallel-backend thread --outer-parallel-workers 8 `
  --inner-parallel-backend thread --inner-parallel-workers 4 `
  --nested-task-timeout-seconds 180
```

## 运行 Redis 分布式 L1/L2

先启动一个或多个 worker：

```powershell
python solver/run_nested_worker.py `
  --parallel `
  --inner-parallel-backend thread --inner-parallel-workers 4 `
  --redis-url redis://localhost:6379/0 `
  --redis-namespace nsgablack:supply_adjustment_nested `
  --worker-id worker-1
```

再启动 outer solver：

```powershell
python solver/run_case.py `
  --parallel `
  --outer-parallel-backend redis `
  --inner-parallel-backend thread `
  --redis-url redis://localhost:6379/0 `
  --redis-namespace nsgablack:supply_adjustment_nested `
  --redis-timeout-seconds 3600
```

## 运行 L0/L1/L2

```powershell
python solver/run_blacklist_case.py `
  --no-baseline `
  --max-moved-events 120 `
  --l0-pop-size 12 --l0-generations 8 `
  --l1-pop-size 10 --l1-generations 6 `
  --final-l1-pop-size 24 --final-l1-generations 16 `
  --parallel --parallel-backend thread --parallel-workers 8 `
  --parallel-thread-bias-isolation disable_cache
```

## 输出（Output）

- `runs/supply_adjustment_nested/adjusted_supply_<run_id>.xlsx`
- `runs/supply_adjustment_nested/adjusted_supply_moves_<run_id>.csv`
- `runs/supply_adjustment_nested/adjusted_supply_audit_<run_id>.json`
- L0 runs 还会导出 `best_blacklist_<run_id>.json` 和最终 L1 adjustment tables。

## 预期信号（Expected signal）

有效运行应该通过移动少量供应事件提升生产产出，保持 day-0 和 conservation audit 干净，并展示 L0 blacklist design 是否能在较小 quality gap 下减少 runtime。
