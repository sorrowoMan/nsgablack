# 组件契约卡模板

每个 Case 本地 Adapter、Pipeline、Bias 与 Plugin 都应按本模板记录正式边界。

## 1. 身份

- 组件 key：
- 类型：
- 源码路径：
- 维护者：

## 2. 职责

- 必须完成：
- 禁止承担：

## 3. 输入输出

- 输入类型与形状：
- 输出类型与形状：
- 副作用：

## 4. Context 契约

- `context_requires`：
- `context_provides`：
- `context_mutates`：
- `context_cache`：
- `context_notes`：

## 5. 恢复与终止

- `get_state/set_state`：是/否
- 恢复级别：L0/L1/L2
- 恢复边界：
- 明确停止或短路行为：

## 6. 模式边界

- 可证明模式：
- 启发式模式：
