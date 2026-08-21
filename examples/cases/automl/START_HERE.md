# 快速开始：automl

1. 先检查整个 Project 的装配契约：

~~~powershell
python examples/cases/automl/run_project.py --check
~~~

2. 再执行默认 smoke profile：

~~~powershell
python examples/cases/automl/run_project.py
~~~

3. 在输出中核对 Case、有效 **ResourceContext**、执行后端和运行命名空间。

Project 负责跨 Case 编排和 L0 授权；具体求解或训练语义留在 **cases/<case>/** 内。
