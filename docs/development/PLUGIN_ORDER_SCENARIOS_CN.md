# Plugin 顺序语义场景说明（中文）

配套演示文件：

- `tools/plugin_order_semantics_scenarios.ipynb`
- `tools/plugin_order_semantics_scenarios.py`

## 场景清单

1. `priority` 小值先执行
2. 未知组件引用即时报错
3. `priority` 方向冲突严格拒绝
4. 运行中直接改拓扑会报错
5. `request_plugin_order(...)` 在下一代边界生效
6. 嵌套 `solver` 的作用域隔离（父子各自调度）

## 场景 6 重点

场景 6 演示了三个关键点：

- 父 `solver` 只管理父层插件顺序。
- 子 `solver` 只管理子层插件顺序。
- 父层引用子层插件名（或反向）会被判定为未知组件并报错。

也就是：**跨作用域不做顺序依赖**，避免“组件内部再控制别的组件”导致全局拓扑不可验证。

## 运行方式

```powershell
python tools/plugin_order_semantics_scenarios.py
```

或直接在 Notebook 逐格执行。
