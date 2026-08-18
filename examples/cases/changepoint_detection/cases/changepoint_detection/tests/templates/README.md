# 组件测试矩阵

每个新增组件至少补充以下四类测试：

- smoke：能够按标准 Case 脚手架完成最小装配。
- contract：输入、输出、Context 与 Artifact 契约可验证。
- roundtrip：checkpoint/state/serialization 恢复后语义一致。
- fault：严格模式失败可见，soft-error 模式保留结构化审计。

