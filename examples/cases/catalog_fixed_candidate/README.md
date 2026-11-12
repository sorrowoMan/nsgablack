# 固定候选：完整的一次问题评估

这个标准Project只运行fixed Case，演示FixedCandidateAdapter最小而完整的用途：把确定的二维参数交给正式问题管线和Problem评估，读取同一次接纳的精确候选版本。没有ML训练、变异、后台服务或模型API调用。

## 先运行，再看文件

从nsgablack仓库根目录执行：

```powershell
python examples/cases/catalog_fixed_candidate/run_project.py --check --build-check
python examples/cases/catalog_fixed_candidate/run_project.py --no-record
```

check/build-check输出应显示FixedPointProblem、RepresentationPipeline、ClipRepair、FixedCandidateAdapter及fixed_candidate_trace；有效资源是Project L0发放的1个CPU线程、0 GPU。构造和检查不会提前求值或建立候选Unit。

真正运行后，终端的这一行是只读Plugin从本次接纳的池引用读取的结果：

```text
fixed-candidate-result {"accepted_refs": 1, "candidates": [[0.25, 0.75]], "evaluations": 1, "raw_objectives": [[0.625]], "raw_violations": [0.0], "steps": 1}
```

原始目标0.625来自0.25²+0.75²，不是预测或偏好分数。打印不会再次调用evaluate。`--no-record`关闭Project运行清单持久化；共享底座仍可维护自己的资源控制和Artifact文件。保留正常正式入口执行，不能把网页代码改成第二个搜索循环。

## 每部分负责什么

- [problem/__init__.py](cases/fixed/problem/__init__.py)：二维候选、[0,1]边界和平方和原始目标。
- [pipeline/main.py](cases/fixed/pipeline/main.py)：UniformInitializer默认初值、ClipRepair问题修复；本例不需要mutator。
- [adapter/main.py](cases/fixed/adapter/main.py)：FixedSeed直属初值和FixedCandidateAdapter。返回候选，不自己修复或求值。
- [plugins/trace.py](cases/fixed/plugins/trace.py)：运行结束时只读精确池引用、候选和raw feedback，并打印JSON。
- [build_solver.py](cases/fixed/build_solver.py)：薄装配入口，接收Project传入的resource_context，设置随机种子17、max_steps=1。
- [project_config.py](project_config.py)：默认组只含fixed Case，1线程本地CPU授权。

完整逐文件代码、两个初始化变体、行为和边界见[组件用法](../../../docs/catalog_usage/NSGABLACK_COMPONENT_USAGE_CN.md#adapterfixed_candidate--fixedcandidateadapter)。这里使用现成标准脚手架的config/入口/公共支持，未复制另一套框架实现。

## 两个小改动

在Case的build_solver.py中，将默认candidate从(0.25,0.75)改成(0.25,1.5)。仍用同一入口运行：问题管线应先把候选修成[0.25,1.0]，原始目标应为1.0625，求值数仍是1。

把同一build_adapter调用中的use_pipeline_initializer改成True，会移除直属FixedSeed，改用共享Pipeline的随机初值。仍只评一行，应核对目标等于实际候选平方和；不再保证0.625。

FixedCandidate每步请求新初值，max_steps=1才表达这里只评一次。若增加步数且用随机初始化，每步可能得到新点；fixed不是自动冻结随机点的缓存。ML语义候选需自己的Representation和LearningProblem，不能把此二维数组直接塞进ClosedFormDataPipeline。

## 验证范围

本例经过正式Project check/build-check和实际CPU运行。tests/test_catalog_fixed_candidate.py检查默认Project结果、修复后候选/原始反馈一致、共享Pipeline初始化，以及装配期Unit未创建。它验证接线与一次求值语义，不证明算法效果或收敛。
