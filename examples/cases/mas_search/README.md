# mas_search（Model-and-Search 适配器）

验证 MASAdapter——模型辅助搜索。

## 是否使用 mlblack

不使用。纯 nsgablack。

## 这个 case 验证什么

MAS 适配器的装配路径：
- 在搜索过程中维护内部模型
- 用模型信息指导后续搜索

## 搜索向量

| 变量 | 含义 | 范围 |
|---|---|---|
| x_i | 第 i 维 | [-5.0, 5.0] |

## 目标和指标

| 目标 | 方向 | 含义 |
|---|---|---|
| sphere | minimize | Σ x_i² |

## 组件组合

| 层 | 组件 | 来源 |
|---|---|---|
| Adapter | MASAdapter | 框架 adapters/mas |

## 运行

```powershell
cd C:\Users\hp\Desktop\nsgablack
python examples\cases\mas_search\run_solver.py --check
```
