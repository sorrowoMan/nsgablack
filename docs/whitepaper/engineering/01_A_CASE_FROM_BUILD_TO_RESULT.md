# 第一章 从一个正式 Case 看完整求解过程

先看一个能找到全部组成部分的小系统。仓库的 [algorithm_units 项目](C:/Users/hp/Desktop/nsgablack/examples/cases/algorithm_units/README.md) 包含 candidate_search 与 symbolic_beam 两个 Case。本章只追踪 candidate_search：在两个取值范围为 -5 到 5 的变量中，寻找平方和更小的点。这个任务足够简单，可以把精力用于理解各组件怎样接起来。

这个 Case 的主要文件为：

```text
examples/cases/algorithm_units/
  project_config.py
  run_project.py
  cases/candidate_search/
    build_solver.py
    run_solver.py
    problem/sphere.py
    pipeline/main.py
    adapter/composable_solver_fusion_demo.py
```

完整 Scaffold 还包含配置与其他标准目录，这里列出参与本次解释的文件。Project 入口负责按项目配置运行 Case；Case 的 build_solver 负责装配一个求解对象；其他目录分别提供被装配的组件。目录位置让使用者能够先判断责任，再进入实现。

[问题文件](C:/Users/hp/Desktop/nsgablack/examples/cases/algorithm_units/cases/candidate_search/problem/sphere.py) 中的核心代码是：

```python
class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=2,
                         bounds={"x0": (-5, 5), "x1": (-5, 5)})

    def evaluate(self, candidate):
        return np.array([np.sum(np.asarray(candidate) ** 2)])
```

这里的两个变量就是问题未知量。返回数组长度为一，表示单目标评价。输入 `[2, -1]` 时目标值为 5；输入 `[0.5, 0.5]` 时目标值为 0.5。Problem 只说明怎样评价当前候选，没有规定从哪个点出发、每次产生几个点或怎样使用历史信息。

[问题管线](C:/Users/hp/Desktop/nsgablack/examples/cases/algorithm_units/cases/candidate_search/pipeline/main.py) 装配 UniformInitializer、GaussianMutation 和 ClipRepair。初始化器能在给定范围内产生点，变异器能扰动已有点，修复器把越界数值拉回范围。它们是供策略使用的操作能力。装配了 GaussianMutation，并不代表每一种 Adapter 都会调用它；实际运行行为还要看 propose 的实现。

这个 Case 使用的 RandomProbeAdapter 恰好只执行初始化采样。其核心路径是：

```python
def propose(self, control, context):
    return self.build_candidate_units(
        [control.init_candidate(context) for _ in range(self.samples)],
        context,
    )

def update(self, control, candidates, feedback, context):
    _ = (control, candidates, feedback, context)
```

这段代码有两个具体含义。第一，它每次从初始化器获得 samples 个候选，而不是围绕上次最优点逐步移动。第二，它没有根据反馈调整自己的抽样策略。Solver 仍然会评价与维护运行结果，但不能据此把这个 Adapter 说成具有自适应学习或局部收敛机制。判断一个组件启用了什么能力，需要看到实际调用。

生成数值点以后，build_candidate_units 通过 UnitBinding 创建 CandidateUnit，再投影为候选交回 Solver。算法管线的任务由此出现：它建立算法操作结构，提供结构身份，并为后续保存恢复准备编码路径。此处的结构很轻，主要价值是展示正式接口；后面的节点、参考种群和参数槽位会更充分地体现这个接口的作用。

[build_solver.py](C:/Users/hp/Desktop/nsgablack/examples/cases/algorithm_units/cases/candidate_search/build_solver.py) 把这些组件连接起来。实际装配包括创建 RandomProbeAdapter、用 build_unit_binding 绑定构建器、把 Sphere 与 RepresentationPipeline 交给 ComposableSolver、设置最大步数、消费组件覆盖并注入 ResourceContext。默认 samples 为 4，默认 max_steps 为 3。它们来自配置，而不是写进 Sphere 的目标公式。

需要特别看清两条管线的连接位置。representation_pipeline 被挂在 Solver 上，供候选初始化、变异、repair 等公共入口使用；算法构建绑定被交给 Adapter，由 Adapter 在需要结构时发起构建请求。它们都可以由 Case 的 pipeline 模块提供，但调用方与输入输出不同。这一差别会影响故障定位：候选数值越界看问题管线，算法结构缺字段则看 Unit 构建绑定。

可以用四个指定点演算一次评价：`[2,-1]、[1,1]、[0.5,0.5]、[-3,0]` 的平方和依次为 `5、2、0.5、9`。这是假设输入，用来解释数据形状，不是运行日志。批量目标矩阵是四行一列，约束违背向量有四个元素。没有额外约束时，它们为零。控制面为候选保留对应身份，使第三行的评价能绑定回第三个候选。

当一次步骤被正式提交，Solver 才把它计为逻辑进展。RandomProbeAdapter 的 update 不保留种群选择，但统一控制面仍负责评价事件、运行进度与结果记录。这也说明“某个 Adapter 不维护完整种群”是合法结构，不能为了统一外观就给它伪造一个种群快照。它的最近提案、整个运行的最佳结果和进化算法的环境选择种群，是三种不同对象。

阅读正式入口以后，可以按以下命令检查装配。工作目录为 nsgablack 根目录：

```powershell
python examples/cases/algorithm_units/run_project.py --check --build-check
python -m nsgablack project doctor --path examples/cases/algorithm_units/cases/candidate_search --strict --build --format problem
```

第一条检查项目配置与实际构建，第二条对该 Case 做严格构建诊断。需要执行求解时，使用同一个 Project 入口并去掉检查选项：

```powershell
python examples/cases/algorithm_units/run_project.py
```

该命令会按项目配置执行两个 Case，不是只跑本章的 candidate_search。只检查某一 Case，可以使用前面的精确 Doctor 路径；独立 Case 也拥有自己的 run_solver.py 入口。执行时需使用已安装三仓依赖的开发环境，不能把某个文件能被编辑器打开当作包已经正确安装。

检查输出时，先确认实际 Adapter 是 random_probe，算法绑定名是 `algorithm_units.candidate/v1`，再确认资源上下文来自当前 Project。若 README 写的是 VNS 而构建结果仍是 RandomProbeAdapter，问题就在装配或文档，不需要先怀疑求解器。若修改了 samples 却看不出变化，要追踪配置是否进入 build_solver，不能仅凭配置文件内容判断运行事实。

扩展这个 Case 有清楚的方向。换目标函数，主要修改 Problem；换采样与修复方式，修改问题管线；让每次提案围绕最佳点生成，修改 Adapter；给候选结构增加需要保存的字段，修改 Unit 和构建器；加入日志与 checkpoint，使用相应 Plugin；把多个 Case 串并联，修改 Project。一个功能放到哪里，取决于它改变了哪一段行为。

**理解整个框架的第一步，是能够从正式 builder 追到一次评价，再追到状态提交。** 后续章节会把这条路径中的各个对象拆得更细，复杂系统也仍然以这条路径为基本组成单元。
