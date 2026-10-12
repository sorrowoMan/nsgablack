# 符号 Beam Unit Case

将特征池搜索分为 problem（目标及残差/OMP 工具）、pipeline（稀疏候选修复与 Beam 结构构建）、
adapter（扩展、去重、排序和 Beam 截断）。build_solver 是唯一装配入口。

实际组件：JointBeamAdapter、BeamUnitBuilder、SparseBinaryInitializer、SparseBinaryMutation、SparseBinaryRepair。
Unit 保存特征索引、空掩码及当前 Beam 掩码；checkpoint 经 codec 恢复这些结构。

`python run_solver.py --check` 检查装配，`python run_solver.py` 运行。
旧 symbolic_joint_bundle_beam_demo.py 仍支持原有参数，内部转发到本 Case。
这个 Case 保留原有线性特征池目标，不代表新增了通用符号学习或 mlblack Trainer。
