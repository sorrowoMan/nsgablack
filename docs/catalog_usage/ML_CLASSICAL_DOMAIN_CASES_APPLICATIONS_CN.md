# 现有业务 Case：先读实际程序，再决定怎样复用

以下三项保留为**迁移参考**。它们确实有正式Project/Case外壳，但不能因为目录齐全就宣称完整模型交付、时序验证或归因含义已经受验收。本轮只读源码、补用法，不读取业务数据、不拟合、不下载、不改原Case。本文把可接入的位置和当前不能越过的边界写出来。

## classical.example.etf

**什么时候用：** 了解现有ETF横截面特征、按日期walk-forward、多seed与组合报告的完整程序结构。一个FixedCandidate代表一次评估程序，不代表已经训练好的可随处推理的模型；不应直接把其指标当严格独立测试成绩。

**先准备什么：** 完整复制 `mlblack/examples/cases/etf_temporal_forecast/`，保留原L0和 `cases/etf_temporal_forecast/`。依赖本地pandas、NumPy、scikit-learn、parquet引擎；已有本地parquet含日期索引/日期列和多资产数值收益列。**名字dataset_url在当前实现实际是本地路径**：_load_returns用Path.resolve后pd.read_parquet，不会帮你下载URL。DEFAULT_DATASET_URL也已经是仓内runs/cache路径；config.py另一个缓存默认不保证被builder自动采用。

**放在哪：** 数据位置/模型族/seed/目标horizon归原Case build_solver的config；walkforward是builder的显式关键字，而不是任意塞入config便生效。不要把完整业务循环重新抄进新build_solver。下面是副本内可编辑包装的完整接线方式，尚未解除后述语义限制。

**接入步骤：** 将原 `cases/etf_temporal_forecast/build_solver.py` 重命名为同包 `assembly_original.py`，保持其实现原样；保存下面新的唯一薄builder。只在副本中做，原run_solver仍找到规范build_solver。

```python
# cases/etf_temporal_forecast/build_solver.py
import os
from pathlib import Path
from mlblack.integrations.etf_temporal_forecast import WalkForwardSpec
from .assembly_original import build_solver as build_original

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this reference uses explicit local settings")
    raw = os.environ.get("ETF_RETURNS_PARQUET", "")
    if not raw or "://" in raw:
        raise ValueError("set ETF_RETURNS_PARQUET to an existing local file")
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return build_original(config={"dataset_url": str(path),
        "models": ("ridge",), "seeds": (17,), "target_horizon": 1,
        "suite_id": "catalog_local_etf", "output_dir": "results/local_etf"},
        walkforward=WalkForwardSpec(min_train_size=80, test_size=20, step_size=20,
            mode="expanding", max_folds=2, max_train_panel_rows=1000,
            max_test_panel_rows=400), resource_context=resource_context)
```

这是明确请求“一种模型、最多两折”的程序：原pipeline构造momentum/volatility/market等9列；原Representation解码EtfTemporalCandidate；原EtfTemporalProblem调用run_etf_temporal_forecast_multi_seed；原FixedAdapter和BudgetController只执行一次外部送评。内层每折/每模型仍真实fit，不能把一次Evaluation Event等同一次fit。

**怎样判断接对：** 原feedback五目标为[RMSE,-rankIC,-SharpeProxy,绝对回撤,换手Proxy]，loss仅RMSE；metrics为etf.rmse/rank_ic/rank_ic_std/hit_rate/sharpe_proxy/max_drawdown_abs/turnover_proxy/fold_count。build_model_artifact返回的是程序候选+summary+output_dir字典，**不是每折已拟合模型权重**。最终ModelRef标识程序报告，内目录CSV/JSON与权威Artifact仍要分别核对。

当前应先处理三点再称严谨预测验收：特征panel先对全数据生成shift(-horizon)目标，walk-forward按特征date切train/test，没有显式按目标可知时间purge边界；默认多模型blend的inverse_rmse取自同一测试折model_metrics，会利用该折真实标签决定混合权重；最终模型报告依赖Problem.last_result，未提供其checkpoint只读恢复闭包。本包装只选ridge，消除了多模型权重依赖，**没有消除时间边界问题**。原EtfReportPlugin在on_fit_end写观察文件，也不等于finalization已成功。

**运行入口：** 在上述副本设置本地环境变量后，可先用原 `python run_project.py --check --build-check`核对装配；会调用builder但不拟合。本书不把随后的默认运行称已通过预测/恢复验收；解除上述问题后仍应经原Project运行、从正式Case输出TrainerResult与本次Artifact读取程序结果。缺parquet时应明确失败，不能自动联网换数据或捏造运行数值。

### 变体：从扩展训练窗改为有限滚动窗

**目的/改在哪里：** 包装中的WalkForwardSpec改为mode="rolling",train_window_size=80，其他配置不变。**行为变化：** 每折训练日期限制在最近80个已选日期；不是更改底层Pipeline目标定义。**限制：** rolling不会自动purge未来标签，也不会修复恢复/报告问题；不能只改模式便认定不存在信息泄漏。

## classical.example.traffic_arimax

**什么时候用：** 阅读已有交通指标的ARIMAX全样本拟合、删因子组AIC对比与标准化系数报告。当前是探索性诊断Case，不是严格因果归因，也不是经过留出验证的预测Case。

**先准备什么：** 完整复制 `mlblack/examples/cases/traffic_congestion/`。原Case硬绑定 `<project>/data/ci_interval_opt_table_no_flow_speed_occ_lag.csv`（builder的parents[2]/data）；parents[0]为Case目录、[1]为cases、[2]为Project，也没有读取config.csv_path。表需ci、因子组列，原pipeline按存在的因子组抽取列、删除含NaN行，再在全部保留数据上fit StandardScaler。需要pandas、scikit-learn和statsmodels；缺statsmodels会改用LinearRegression，不能当同一模型。

**放在哪：** 只在Project副本追加一个单Case组，避免默认诊断阶段同时启动其他Case。原业务代码仍位于cases/arimax_factor_attribution的pipeline/main.py和build_solver.py；后者当前还混有分析体，不能把这个历史形态当新增Case模板。

**接入步骤：** 在project_config.py末尾追加完整声明：

```python
STAGES.append({"name": "catalog_arimax", "cases": ["arimax_factor_attribution"],
    "resource_requests": {"arimax_factor_attribution": {"threads": 1, "device": "cpu", "backend": "local"}},
    "component_overrides": {"arimax_factor_attribution": {"config": {
        "ar_order": 1, "ma_order": 0, "diff": 0, "max_rows": 120}}}})
GROUPS["catalog_arimax"] = {"stages": ["catalog_arimax"]}
```

原builder通过build_diagnostic_solver→DiagnosticProblem→FixedAdapter调用一次diagnostic_runner；不必手写run循环。一次诊断内部包括完整模型和多个删组重拟合，不是一次数值求值。原runner返回status/exit_code，不返回详细系数/AIC到正式反馈，主要分析目前只打印控制台；默认DiagnosticRepresentation.decode=None，因此不能假定存在模型Artifact。

**怎样判断接对：** 当前只能确认诊断终态和exit_code，不能凭“status=ok”推断因子分析正确。源码用full_result.params[-n_exog:]取外生系数，statsmodels参数还包含AR/MA/方差等，尾切片不能可靠对应外生列；必须按真实param_names映射后才能解释组系数。max_factor_groups当前只裁报告组列表，没有对应裁X列，存在列偏移解释风险；本声明不启用该参数。全样本standardize/AIC不提供独立预测指标，更不证明某因子有因果影响。

**运行入口：** 复制数据与依赖后，原 `python run_project.py --group catalog_arimax --check --build-check`可核对装配；本节不建议把随后运行当科学结论验收。在修正系数命名对齐、失败传播与结构化Artifact报告之前，保留为迁移说明。更容易完整装配的算法接口示例可先用传统预测书的NumPy AR/SARX Case，目标不同，不冒充本业务归因。

### 变体：请求MA1

**目的/改在哪里：** 上述声明ma_order由0改1。**行为变化：** statsmodels完整ARIMA拟合增添MA项，删组分析成本可能增加。**限制：** 缺statsmodels的线性回退不会实现MA；尾切片系数归属问题也未消失。部分删组fit当前只打印FAIL继续，进程成功不能替代逐组完成证据。

## classical.example.traffic_xgb

**什么时候用：** 复用交通表上的XGBoost超参搜索Case结构。它当前是表格回归示例，不应因为date列存在就称时间序列留出预测。

**先准备什么：** 同项目的另一独立完整副本，以及与上一节相同的Project/data CSV。pipeline排除date/ci/Unnamed:0/test_fold_*，其余列转float；train_valid_split使用valid_ratio=.2、seed42的随机切分。需要本地XGBoost/scikit-learn/pandas依赖，缺后端应按实际错误处理，本书不会安装或自动回退。

**放在哪：** 原cases/xgboost_baseline的pipeline负责CSV→NumericDataView，build_solver通过assembly.build_trainer("xgboost")选tree_boosting_estimator_search preset，EstimatorSpecRepresentation与SupervisedEstimatorFitRegressionProblem负责每候选fit。插件/Artifact补齐仍应放正式Case，不把裸booster写到共享context。

**接入步骤：** 在独立Project副本的project_config.py末尾追加：

```python
STAGES.append({"name": "catalog_xgb", "cases": ["xgboost_baseline"],
    "resource_requests": {"xgboost_baseline": {"threads": 1, "device": "cpu", "backend": "local"}},
    "component_overrides": {"xgboost_baseline": {"config": {
        "population_size": 4, "mutation_scale": .1}}}})
GROUPS["catalog_xgb"] = {"stages": ["catalog_xgb"]}
```

只声明真实被builder消费的两个config参数；不是加一个max_steps键就会生效。需要明确搜索完成预算时，应由正式Solver配置/Controller约束，不能把四个种群成员误读为四次fit上限。Project传入的resource_context经原assembly绑定，CPU/GPU线程应以实际生效审计为准。

**怎样判断接对：** 回归feedback有train/valid指标和estimator生命周期，目标中的valid误差只是随机留出误差；不能据此推断时间外泛化。默认Problem的EstimatorStateArtifact包含活FittedEstimatorModel，摘要不等于完整booster读取器；当前安全序列化/只读恢复没有为此业务Case闭合。只看到搜索候选向量或train_loss，不表示已交付可推理booster。

**运行入口：** 原 `python run_project.py --group catalog_xgb --check --build-check`会真正读表装配，不拟合；数据缺失便会失败。明确训练预算、时间切分需求、booster原生安全保存/加载及无重拟合restore后，再通过同一正式Project运行并读取ModelRef，不能启用unsafe pickle后称已经补齐。当前可完整阅读的替代是岭估计器书的实际fit/反馈系数/JSON交付链，不承诺它具有XGBoost表达力。

### 变体：换一份数值特征表

**目的/改在哪里：** 先复制原CSV结构到独立项目data的同名文件，只改变实际可用数值列；不覆盖原业务数据。**行为变化：** pipeline自动选择除排除列表外的列，EstimatorSpec的超参布局并不等于特征布局。**限制：** 若新增未来信息、非数值字段或目标泄漏列，pipeline不会自动替用户判断合理性；需显式schema/时间验收，不能依赖文件名。原例的安全Artifact缺口仍然存在。

源码依据：三个原Case的build_solver/pipeline/project_config，以及mlblack `integrations/etf_temporal_forecast.py`、`integrations/nsgablack_diagnostic.py`、`core/diagnostic.py`、`presets/tree.py`、`problems/supervised.py`。
