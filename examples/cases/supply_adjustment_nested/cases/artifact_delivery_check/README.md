# 跨节点产物交付检查

这是一个标准数据验证 Case，不调用优化器，也不消耗求值预算。Project 必须通过 `input_artifacts` 向 `joint_plan` 绑定已封存的 `joint_summary`；`expected_node` 可指定 `risk`、`local` 或 `data`。

任务经 `case_runtime.artifact_publisher.read_verified()` 读取原始字节，核对发布者身份、候选 token、内层谱系、来源摘要格式、排程与三目标、今天和材料守恒声明，发布轻量 `delivery_receipt`。收据保存内容 SHA256、原绑定、消费节点和身份；不复制排程或供料矩阵，不重新打开生产节点的本地来源路径，也不重新求解。

注意：来源文件内容和业务可行性由生产 Case 验证；本 Case 只核验收到的封存结果及其内部一致性。只有实际在不同物理节点运行后，收据才能用作跨机交付证据。
