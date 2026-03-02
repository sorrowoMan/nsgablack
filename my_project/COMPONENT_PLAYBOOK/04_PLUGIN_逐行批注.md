# Plugin 组件（逐行批注版）

目标：把“工程能力”做成可插拔模块（日志、审计、缓存、容错、统计）。

---

## 文件位置
`plugins/my_plugin.py`

## 直接可复制模板（每行解释）
```python
from __future__ import annotations  # 现代注解

import json  # 导出报告
from pathlib import Path  # 文件路径处理
from time import time  # 计时

from nsgablack.plugins.base import Plugin  # 插件基类
from nsgablack.utils.context.context_keys import KEY_BEST_OBJECTIVE  # 统一 key


class MyRunSummaryPlugin(Plugin):  # 示例插件：记录每代摘要并落盘
    name = "my_run_summary"  # 插件名

    context_requires = ()  # 不强依赖字段
    context_provides = ()  # 不提供字段
    context_mutates = ()  # 不修改共享字段
    context_cache = ()  # 不缓存
    context_notes = ("Collect generation summary and export json on run end.",)  # 说明

    def __init__(self, out_dir: str = "runs/plugin_reports") -> None:  # 初始化参数
        super().__init__()  # 父类初始化
        self.out_dir = Path(out_dir)  # 输出目录
        self.records = []  # 代际记录
        self.started_at = None  # 起始时间

    def on_run_start(self, solver):  # 运行开始钩子
        _ = solver  # 当前示例不直接使用 solver
        self.started_at = time()  # 记录启动时间
        self.records.clear()  # 清空上次记录

    def on_generation_end(self, solver, generation, population, objectives, context=None):  # 每代结束钩子
        _ = solver  # 当前示例不直接使用 solver
        _ = context  # 当前示例不用 context
        if objectives is None:  # 防御：没有目标就跳过
            return
        best_obj0 = float(min(row[0] for row in objectives))  # 示例：第一目标最小值
        self.records.append(  # 记录本代摘要
            {
                "generation": int(generation),  # 代号
                "best_obj0": best_obj0,  # 最佳 obj0
                "pop_size": int(len(population)),  # 种群规模
            }
        )

    def on_run_end(self, solver):  # 运行结束钩子
        elapsed = None if self.started_at is None else time() - self.started_at  # 总耗时
        projection = solver.get_runtime_context_projection() or {}  # 读取运行态 context 快照
        best_obj = projection.get(KEY_BEST_OBJECTIVE, None)  # 读取 best objective
        payload = {  # 导出结构
            "plugin": self.name,  # 插件名
            "elapsed_sec": elapsed,  # 耗时
            "best_objective": best_obj,  # 运行最佳目标
            "history": self.records,  # 全部代际记录
        }
        self.out_dir.mkdir(parents=True, exist_ok=True)  # 确保目录存在
        out_file = self.out_dir / f"{self.name}_summary.json"  # 输出文件名
        out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")  # 写 json
```

---

## build_solver 接线
```python
from plugins.my_plugin import MyRunSummaryPlugin  # 导入插件

solver.plugin_manager.register(MyRunSummaryPlugin(out_dir="runs/plugin_reports"))  # 注册插件
```

---

## 插件硬规则
- 插件是工程增强，不是算法主流程
- 运行态读取尽量走 `solver.get_runtime_context_projection()`
- 不要直接写 `solver.population/objectives/constraint_violations`
- 读写大对象走 `solver.read_snapshot()` / `Plugin.resolve_population_snapshot()` / `Plugin.commit_population_snapshot()`
- 失败要有可读信息，不要裸 `except: pass`
