# Context 契约（requires / provides / mutates）

本页定义**context 使用契约**的最小规范。目标是：  
让组件在组合时“显式说明读写字段”，避免隐式耦合。

---

## 1) 契约字段

每个组件可以声明以下字段（均为可选）：

- `requires`：读取哪些字段  
- `provides`：写入哪些字段  
- `mutates`：可能覆盖哪些已有字段  
- `cache`：仅为性能缓存的字段（不可重放）  

这些字段不会强制中断现有逻辑，默认是**兼容式**。

---

## 2) 如何声明

以 Plugin 为例：

```python
class MyPlugin(Plugin):
    context_requires = ("constraints", "generation")
    context_provides = ("my_metric",)
    context_mutates = ()
    context_cache = ("_tmp_cache",)
```

Adapter / Bias / RepresentationPipeline 也可以同样声明。

---

## 3) 运行期校验（软约束）

`BoundaryGuardPlugin` 会在运行中检查：

- 是否存在 “requires 缺失”  
- 是否包含不可重放字段  

默认只警告，不会中断。

---

## 4) 设计原则

- **先声明，再使用**  
- **缓存字段必须标记**  
- **不破坏向后兼容**  

---

## 5) 相关实现

- `utils/context/context_contracts.py`  
- `plugins/system/boundary_guard.py`  
