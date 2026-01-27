# MIGRATION_GUIDE_TEMPLATE（迁移指南模板）

用途：当你做了弃用/移除/参数改名等变更时，用这份模板写最短迁移说明，保证用户能“复制替换就跑”。

## 背景

- 版本：从 `vX.Y.Z` 到 `vA.B.C`
- 影响范围：Stable / Provisional / Internal（标明）
- 变更动机：为什么要改（1-3 句，不讲故事，讲工程原因）

## 破坏性变更清单（Breaking）

1) ...

## 弃用清单（Deprecated）

1) ...

## 最小迁移（Copy/Paste）

### 1) 旧写法

```python
# old
```

### 2) 新写法

```python
# new
```

### 3) 迁移备注

- 旧参数 -> 新参数：...
- 旧输出字段 -> 新字段：...

## FAQ（可选）

- Q: ...
- A: ...

