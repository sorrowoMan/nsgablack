# START_HERE

## 1) 这个 case 验证什么

`Supply Adjustment Nested` 验证 nsgablack 的嵌套编排能力。

- L1 调整 supply event dates。
- L2 通过 production scheduling scaffold 评估每个调整后的供应表。
- 可选 L0 搜索 material blacklists，用于控制 search-space 和 runtime cost。
- 当前 runtime path 不使用 mlblack。

更多目标、层级结构、Redis worker mode 和预期信号见 `README.md`。

## 2) 运行 L1/L2

```powershell
python solver/run_case.py --parallel --parallel-backend thread --parallel-workers 8
```

## 3) 运行 L0/L1/L2

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

## 4) 校验输入路径日志

运行时应看到：

- `[data] bom=...`
- `[data] supply=...`
- `[outer] adjustable_events=...`
- `[inner] mode=full_nested ...`

## 5) 关键指标

| 指标 | 含义 |
|---|---|
| `-total_output` | 生产质量目标；越低代表总产出越高。 |
| moved event count | L1 改动的供应事件数量。 |
| moved days | 总干预幅度。 |
| runtime / quality gap / blacklist size | L0 搜索空间设计权衡。 |
| supply audit | 供应守恒和 day-0 安全检查。 |

## 6) 输出

- `adjusted_supply_<run_id>.xlsx`
- `adjusted_supply_moves_<run_id>.csv`
- `adjusted_supply_audit_<run_id>.json`
- L0 runs 还会导出 `best_blacklist_<run_id>.json` 和最终 L1 adjustment tables。

## 7) 结构

| 路径 | 作用 |
|---|---|
| `solver/assembly.py` | L1/L2 formal assembly。 |
| `solver/blacklist_assembly.py` | L0/L1/L2 formal assembly。 |
| `solver/run_case.py` | L1/L2 CLI。 |
| `solver/run_blacklist_case.py` | L0/L1/L2 CLI。 |
| `problem/` | Supply event shift 和 blacklist design problems。 |
| `pipeline/` | L0 binary representation pipeline。 |
| `reporting/` | Supply movement 和 conservation audit。 |

`working_nested_optimizer.py` 和 `working_blacklist_optimizer.py` 是 compatibility shells。
