# 四个旧插件：先知道它没有接通什么

本文四个旧类均**未装配**，各记录标记为migration_reference。每节给出当前实际可用的替代Case接线或明确仍待实现的边界，不把“可导入”写成“功能已闭合”。没有运行算法、批量实验、GPU任务或外部服务。

## migration.plugin.diversity_init · 观察相似度不等于初始化拒绝采样

**什么时候用：** 旧装配认为add_plugin(DiversityInitPlugin(...))会自动筛掉相似初始个体，需要核对并迁移。

**先准备什么：** 阅读plugins/runtime/diversity_init.py与现有初始化调用。on_solver_init只在Solver已有use_diverse_init属性时把它置True，当前核心没有相应消费分支。on_population_init计算归一化两两距离并print；is_similar/should_accept虽存在，当前正式初始化并未自动调用它们。similarity_threshold/rejection_prob不是有效的默认初始候选筛选器。

**放在哪：** 从Case撤下旧diversity_init挂载。如果目的是运行时搜索偏好多样性，使用配套POPULATION_PREFERENCE_APPLICATIONS_CN的bias.unit_preference整套正式bias_gallery Case，实际绑定PopulationDiversityPreference到明确NSGA实例；旧Plugin不混进该builder。

**接入步骤：** 按配套完整Problem/Pipeline、UnitPreferenceBias.from_adapter、NSGA2、报告与Project L0接线。它只在评估反馈上施加新颖性软偏好，不谎称替代初始化的硬最小距离约束。若确实需要批量覆盖/最小间距初始化，必须新增拥有明确批量输入/输出、停止条件与恢复状态的初始化策略，再从Pipeline给母池播种；当前旧Plugin没有这个实现，本文也没有偷偷替内核补一个。

**怎样判断接对：** 新Case实际记录参考Unit身份、选择增量和群体多样性；原始目标和raw约束保留，偏好不拥有种群替换权。看到日志有initial_diversity不意味着should_accept被执行，不能拿日志当初始多样性保证。

**运行入口：** 配套完整bias_gallery副本按标准run_project.py运行，当前材料只静态核对，旧Plugin不执行。

### 变体一：只观察多样性，暂停软评分

**目的：** 把“看到了多样性”与“改变了选择偏好”明确分开。

**改在哪里：** 使用配套完整Case的“只观察群体多样性”变体，沿其make_query/挂载方式关闭增量，保留报告。

**行为变化：** raw与selection一致，群体多样性仍可观察。**限制：** 这仍不构成初始化拒绝采样；旧类未装配。

## migration.plugin.dynamic_switch · 回调不自动获得搜索事务

**什么时候用：** 旧DynamicSwitchPlugin回调中改策略、权重、mutator或重置算法，希望新Case具有明确调度和恢复语义。

**先准备什么：** 阅读utils/dynamic/switch.py。它在每次物理attempt开始检查逻辑generation；失败重试同一逻辑代可能再次检查。phase_id、last_switch_generation、signals、switch_events在普通Python字段，没有自己的get_state/set_state或步骤快照；回调任意修改的对象也没有自动注册事务。signal读取与build_context异常会被捕获为空字典。不能从“继承Plugin”推断回调的算法状态修改可回滚。

**放在哪：** 撤下旧DynamicSwitchPlugin。需要按逻辑代改变调用策略时，用配套ORCHESTRATION_ADAPTER_APPLICATIONS_CN的完整host与roles_events factory，将MODE改event_cases。旧类未挂载，所有实际搜索状态归各Adapter及事件控制器。

**接入步骤：** 使用完整工厂中EventCaseSpec的命名when函数，条件读取已提交generation。保留两个真实算法实例，按明确priority决定当前case；共享Problem/Pipeline/L0和repair/disposition路由不变。若要GA成员交给VNS而非独立初始化，再使用ORCHESTRATION_POOL_TASK_APPLICATIONS_CN的正式PoolTask输入，不把切换时机误当数据交接。若还需改变模型参数等业务逻辑，须另设计真正的状态所有者，不把任意callback当通用搜索事务。

**怎样判断接对：** runtime.event_shared.event_decision显示命中的case与selected_reason，未命中时可能fallback_current/first_enabled，并非硬停止门。事件控制器get_state保存实际调度状态，和旧Plugin私有phase字段是不同事实。未发生池交接时不声称精修了GA最佳。

**运行入口：** 配套完整catalog_recipes副本按标准两条host命令运行，旧动态插件未执行，不能因此宣称其checkpoint漏洞已修复。

### 变体一：将明确切换阈值提前

**目的：** 改一处真实调度条件，而不是依赖不透明软/硬callback副作用。

**改在哪里：** 在配套composition.py保留MODE=event_cases，完整替换同名函数。

```python
def local_phase(context):
    return int(context["generation"]) >= 2
```

**行为变化：** 到两个已提交逻辑步后local成为高优先case；没有额外建立VNS对象或重放setup。**限制：** 只改变调用时机，不改变候选来源；需要等待任务完成的有限编排用SearchPlanAdapter，不用这个阈值截断running任务。

## migration.plugin.gpu_eval_template · 声明能算后不能靠None降级

**什么时候用：** 旧Catalog推荐GpuEvaluationTemplateProviderPlugin为任意Problem提供“安全GPU回退”，需要识别其实际前提。

**先准备什么：** 阅读plugins/evaluation/gpu_evaluation_template.py与正式EvaluationMediator。模板can_handle只看backend可用和候选存在，没检查Problem.evaluate_gpu_batch；被选中后缺hook、返回None或内部异常且fallback_to_solver_eval=True会得到None。正式仲裁语义在dispatch前decline，被选中后None是交付失败，不会自动尝试低优先Provider或Problem。因此该开关不保证Catalog描述的安全回退。

另外_select_backend查询全局CUDA/CuPy可用性，device默认硬编码cuda:0，不据本Case的ResourceContext grant验证设备授权；约束路径还有捕获异常的evaluate_constraints_safe。不能为了让教学Case跑通就用GPU机器的存在掩盖L0、raw约束和decline边界。本文不装配旧模板，也不执行GPU探测。

**放在哪：** 先撤下旧Provider注册，让当前完整ORCHESTRATION_ADAPTER_APPLICATIONS_CN host走Problem CPU评估。它保留同一个Problem/repair/raw接纳与报告，这个替代只恢复合法评估路径，**没有实现GPU加速**。

**接入步骤：** 使用host完整builder，不add模板也不调用create_provider。若未来需要GPU：先定义Problem真实批量目标/约束API、逐候选shape与语义等价性；再由正式Provider在grant内绑定设备，can_handle在选择前验证全部前提，dispatch后严格交付或传播失败。可选CPU策略要在选择前decline或在同一个已声明等价Provider内部完成受控计算，不能用None当已选择调用的重路由信号。这些是待实现的组件边界，本文没有编造一个装上就能跑的GPU Provider。

**怎样判断接对：** 当前完整host成功时由Problem原始目标计算，结果与已评估成员引用一致；插件/Provider列表没有旧gpu模板。不出现gpu_backend指标不等于自动探测失败，因为这里根本不走GPU。不要将CPU结果或静态API核对写成GPU验证。

**运行入口：** 配套host标准Project入口，仅CPU；本轮未运行。GPU部署前还需要真实授权、后端依赖与行为验证。

### 变体一：只限制局部角色配额，保持CPU评估契约

**目的：** 让没有GPU的用户仍能观察组合与预算，避免无关后端阻塞学习。

**改在哪里：** 配套roles_events factory保留其它完整代码，只设置：

```python
MODE = "roles"
LOCAL_CAP = 1
```

**行为变化：** 每个本地角色调用最多保留一行提案；正式CPU评估、raw约束和索引处置不变。**限制：** 这不是GPU回退实现或GPU吞吐测试，旧模板仍未装配。

## migration.plugin.sensitivity_analysis · 批量试验必须经过Project

**什么时候用：** 旧run_study(build_solver)直接循环构造和solver.run，想迁移为可追溯的正式多次Case。

**先准备什么：** 阅读plugins/ops/sensitivity_analysis.py。它不是自动生命周期hook，必须主动调用run_study；依次单参数扫描，不做Cartesian积或重复统计。_set_attr_by_path直接setattr，文档示例adapter.cfg.base_sigma遇frozen dataclass会失败；直接改对象字段也不能代替构造期校验。更关键的是其run_study没有Project/CaseRuntime请求/各次L0发放，不能当完整多Case编排；默认metric还按旧dict结果找status/steps。

**放在哪：** 不挂载旧SensitivityAnalysisPlugin。使用ORCHESTRATION_ADAPTER_APPLICATIONS_CN的完整host副本，保留其Pipeline与OrchestrationReport；按本节完整替换builder与Project配置，再新增根报告入口。旧类未装配。

**接入步骤：** 这里的敏感参数是Gaussian候选扰动尺度，走工厂构造，不修改frozen config。两stage使用同一个Case，各次独立grant、identity与运行池；同seed不等于算法质量已有统计证据。

```python
# cases/composite/build_solver.py
from pathlib import Path
import numpy as np
from nsgablack.core import BlackBoxProblem, ComposableSolver, FeasibleEvaluationAcceptance
from nsgablack.adapters import GaussianSearchAdapter, GaussianSearchConfig
from nsgablack.project import apply_solver_component_overrides
from .pipeline.orchestration_pipeline import build_pipeline
from .plugins.orchestration_report import OrchestrationReport


class StudySphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="study_sphere", dimension=2,
            bounds=[(-2., 2.)] * 2, objectives=["cost"])

    def evaluate(self, x):
        a = np.asarray(x, dtype=float)
        return [float(np.sum((a-.8)**2))]


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = {"sigma": .02, "label": "small", **dict(config or {}),
        **dict(overrides.pop("config", {}))}
    if settings["label"] not in {"small", "large"}:
        raise ValueError("declared study label required")
    search = GaussianSearchAdapter(config=GaussianSearchConfig(population_size=2,
        mutation_scale=float(settings["sigma"]), random_seed=17, initialization="center"))
    solver = ComposableSolver(problem=StudySphere(), representation_pipeline=build_pipeline(),
        adapter=search, resource_context=resource_context,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(4)
    solver.add_plugin(OrchestrationReport(search, {"search": search},
        Path(__file__).resolve().parents[2] / "results" / f"{settings['label']}.json"))
    apply_solver_component_overrides(solver, overrides)
    return solver
```

```python
# project_config.py
PROJECT_NAME = "explicit_sigma_study"
L0 = {"namespace": "catalog.explicit_sigma_study",
    "offer": {"threads": 1, "gpus": 0, "backend": "local", "device_tokens": []},
    "policy": {"mode": "strict", "cpu_oversubscribe": False},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto", "execution_backend": "local"}
SMALL = .02
LARGE = .2
STAGES = [{"name": label, "cases": ["composite"], "policy": "serial",
    "resource_requests": {"composite": {"threads": 1, "gpus": 0, "backend": "local"}},
    "component_overrides": {"composite": {"config": {"sigma": sigma, "label": label}}}}
    for label, sigma in (("small", SMALL), ("large", LARGE))]
GROUPS = {"default": {"stages": ["small", "large"]}}
```

Project根保存结果入口；只调用正式execute_project一次：

```python
# run_study_and_report.py
import json
from pathlib import Path
from blackbase.types import SolverResult
from nsgablack.project.project_runner import execute_project


def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root)
    rows = []
    for case in run.case_results:
        case.raise_for_failure()
        result = SolverResult.from_dict(case.output)
        rows.append({"stage": case.request.stage_name,
            "case_identity": case.identity.as_dict(),
            "best_objectives": result.best_objectives.tolist(),
            "status": case.status})
    path = root / "results" / "sigma_study.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"run_id": run.run_id, "cases": rows},
        ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
```

**怎样判断接对：** sigma_study.json有small/large两个不同Case identity与各自正式目标；small.json/large.json是独立观察副本，不覆盖彼此。组件工厂确实读取sigma，L0在每stage发放，不通过私有build_solver闭包偷用同一个grant。正式结果不等于统计显著差异，4逻辑步/seed17只作装配示范。

**运行入口：** 副本根 `python run_project.py --check --build-check` 后 `python run_study_and_report.py`。旧run_study不调用，本轮没有执行任何多次运行。

### 变体一：保持较小尺度不变，只扩大另一组扰动

**目的：** 改受控的构造参数，避免路径字符串setattr绕过校验。

**改在哪里：** project_config.py在STAGES之前的常量位置修改：

```python
LARGE = .4
```

**行为变化：** large工厂创建mutation_scale=.4，small仍.02；派生点仍经同一ClipRepair与正式评估。**限制：** Clip可能使有效分布不同于未截断高斯，单种子结果不能证明更好；旧插件状态或报告不构成这次正式试验依据。
