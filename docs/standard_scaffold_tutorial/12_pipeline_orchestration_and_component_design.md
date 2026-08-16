# 12. Pipeline 编排与组件设计（nsgablack 详细版）

本章是“设计规范 + 可运行习惯”的组合手册。

## 1. 目录粒度标准

Case 级只有一个 pipeline 主入口：

```text
pipeline/main.py
```

细粒度算子落到：

```text
pipeline/operators/<slot>/<operator>.py
```

推荐 slots（搜索语义向）：

- `init`
- `mutate`
- `repair`
- `encode`
- `decode`
- `custom`

---

## 2. 组件粒度标准（什么时候拆文件）

一个 operator 文件建议满足：

1. 单一职责
2. 输入输出稳定
3. 可独立单测
4. 可复用于多个 Case

应避免：

- 一个 `main.py` 写几百行 if/else 策略逻辑
- 同时混入数据准备、搜索策略、报告逻辑

---

## 3. 编排模式建议

### 3.1 serial：可解释优先

适合：

- 基线
- 需要严格顺序的处理链

### 3.2 parallel：多分支探索

适合：

- 多种变异/修复候选并行产生
- 需要融合不同策略输出

注意：

- 提前约定 merge 策略
- 提前统一分支输出 shape

### 3.3 router：按 context 路由

适合：

- 不同阶段（explore/exploit）
- 不同任务标签（task_kind）

注意：

- `selector_key` 明确
- route 完整
- strict/fallback 策略明确

---

## 4. 典型完整示例（可直接改造）

```python
pipeline_spec = {
    "key": "search_v1",
    "slots": (
        {"slot": "init", "mode": "serial", "operators": ("uniform_init",)},
        {"slot": "mutate", "mode": "router", "selector_key": "phase",
         "routes": {"explore": "wide_mutate", "exploit": "local_mutate"},
         "default_operator": "local_mutate"},
        {"slot": "repair", "mode": "serial", "operators": ("clip_repair", "project_repair")},
        {"slot": "encode", "mode": "serial", "operators": ("typed_encode",)},
        {"slot": "decode", "mode": "serial", "operators": ("typed_decode",)},
    ),
}
```

---

## 5. 与 Adapter / Problem 的边界协作

- pipeline：处理表示流转
- adapter：控制候选生成与反馈更新
- problem：定义 objective/constraint 语义

不要把：

- objective 逻辑塞进 pipeline
- mutate 策略塞进 problem
- 数据修复策略塞进 adapter 大杂烩

---

## 6. 运行与审计建议

每次调整 pipeline spec 后，建议输出：

- 生效 `pipeline_spec.key`
- 每个 slot 的 mode
- 每个 slot 的 operators 列表

如果开了 parallel/router，再额外输出：

- parallel merge 策略
- router selector_key 与命中 route

---

## 7. 快速检查清单

- [ ] Case 仅一个 pipeline 主入口
- [ ] 每个 slot 的 operator 都在 registry 可解析
- [ ] serial/parallel/router 参数完整
- [ ] strict/fallback 行为明确
- [ ] doctor 无新增错误
- [ ] `--check --build-check` 能通过
