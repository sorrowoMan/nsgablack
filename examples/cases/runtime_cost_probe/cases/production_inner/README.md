# 原生产内层 Case

`build_solver.py` 只转发原 `production_inner` canonical builder，不复制模型或修改 task。
父 Case 的正式请求在本 Project 下按同名 `production_inner` 解析，继续使用原任务校验、
进程隔离、五目标复核与 `production_summary` seal。独立入口 `run_solver.py` 仍需完整声明的 task
和调用输入；本诊断由父 Case 调用，不在此实现第二个求解循环。
