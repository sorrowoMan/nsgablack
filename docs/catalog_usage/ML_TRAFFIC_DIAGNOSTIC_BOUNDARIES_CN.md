# 三个交通分析 Case：怎样找到入口，以及当前不能据此下什么结论

以下是旧业务Case的实际读法与迁移材料，不是三份经过验证的科学教程。本轮没有拟合模型、执行统计检验或运行Project。它们能沿统一诊断生命周期进入，但默认输出与统计接受条件尚不足以承担名字暗示的完整结论；因此目录明确标“迁移说明”。不要把旧stdout或成功退出视作已验证模型。

## mlblack.example.traffic_gam_linearity · GAM样条检查

**什么时候用：** 阅读“线性基线与样条回归如何在Case中比较”的旧实现，确认需要补哪些验证。它可以作探索性训练集拟合诊断，不能证明线性模型泛化假设成立，也不是可直接复用的GAM模型Provider。

**先准备什么：** 独立复制完整 `mlblack/examples/cases/traffic_congestion/`，保留data与Case包；数据文件是Project/data/ci_interval_opt_table_no_flow_speed_occ_lag.csv。依赖NumPy/pandas/scikit-learn，目标列ci；date/ci/Unnamed:0和test_fold_*不作特征，其余列必须可转换成数值。pipeline对整份X先StandardScaler.fit_transform，再由runner按max_rows取尾部；这不是严格训练/验证隔离。

**放在哪：** 原Case为cases/gam_linearity_check；build_solver接收config、resource_context及component_overrides，后者仅支持config和diagnostic_runner。为了只检查此Case，把副本project_config.py的STAGES/GROUPS替换为下列完整片段，原PROJECT_NAME/L0保留：

```python
STAGES = [{"name": "gam_only", "cases": ["gam_linearity_check"],
    "resource_requests": {"gam_linearity_check": {"threads": 1, "device": "cpu", "backend": "local"}},
    "component_overrides": {"gam_linearity_check": {
        "config": {"n_knots": 4, "degree": 2, "top_k": 4, "max_rows": 160}}}}]
GROUPS = {"default": {"stages": ["gam_only"]}}
```

**接入步骤：** 原builder调用build_diagnostic_solver，FixedCandidateAdapter触发runner，runner调用本Case的_run_analysis。实际流程是整数据标准化、LinearRegression拟合、逐连续列SplineTransformer、拼接样条后RidgeCV；离散唯一值≤3的列仍保持线性。最后打印两模型的训练集RMSE和部分响应范围，返回0；不是封存这些模型为模型Artifact。

原n_knots/degree控制样条；max_rows发生在pipeline标准化之后；top_k当前并未用于截断显示结果，不应给它编效果。所有候选特征均需先核对生成时点，移除当天不可知字段、同源目标或未来列。

**怎样判断接对：** 真正执行后应看到实际样本数、两种训练RMSE、逐列范围；确认stdout属于本次run_id。正式Feedback通常只携带status/exit_code，objective默认0；Detailed RMSE没有自动进入正式反馈。默认DiagnosticRepresentation.decode=None，无模型Artifact。源码结尾的“GAM RMSE >> Linear RMSE说明非线性”方向也与前面的改善率含义不一致；不要照这句作结论。训练样本上更灵活的模型拟合更好，不构成验证集证据。

**运行入口：** 只做结构检查可在副本根执行`python run_project.py --check --build-check`。真实分析入口为`python run_project.py`，会拟合模型，本轮没有执行。迁移到可信教程前，需按时间切分、只在训练部分fit预处理/样条、独立验证比较、明确失败条件，并通过正式结果/Artifact记录指标与模型；本书没有替它宣称完成这些改造。

### 变体：减少样条阶数

**目的：** 检查拟合自由度变化。**改在哪里：** 上述Project配置degree从2改为1，保留其他参数。

```python
# 对本次配置值的修改，不创建另一个私有Case运行循环。
STAGES[0]["component_overrides"]["gam_linearity_check"]["config"]["degree"] = 1
```

**行为变化：** 样条基阶数改变，仍然是同一训练集诊断。**限制：** 不能将这一变体视作已控制泛化误差的算法实验。

## mlblack.example.traffic_granger_causality · 时序预测关系检查

**什么时候用：** 追踪原Case如何读因子、构造滞后检验与打印结果；不是给交通因果关系提供已验收证据。Granger预测关系不自动等同干预因果。

**先准备什么：** 另一份完整traffic_congestion副本和同一个CSV。依赖NumPy/pandas/statsmodels；缺statsmodels时旧代码会改走SciPy互相关，这不是同一种检验。pipeline没有主动按date排序或检查采样间隔，必须先确认输入确为规则时间顺序。

**放在哪：** 原Case cases/granger_causality_check；保留原L0，将Project的STAGES/GROUPS换为：

```python
STAGES = [{"name": "granger_only", "cases": ["granger_causality_check"],
    "resource_requests": {"granger_causality_check": {"threads": 1, "device": "cpu", "backend": "local"}},
    "component_overrides": {"granger_causality_check": {
        "config": {"maxlag": 2, "alpha": .05, "max_rows": 160, "max_factors": 3}}}}]
GROUPS = {"default": {"stages": ["granger_only"]}}
```

**接入步骤：** 正式builder仍经DiagnosticProblem与FixedAdapter只触发一次分析；pipeline返回frame与固定候选因子列表，runner取尾部max_rows并限制max_factors。statsmodels输入按[y,x]排列检查x能否预测y，随后反向，再尝试VAR。取多个lag中的最小p用于打印。文件顶部CAUSALITY_PAIRS常量当前并非实际循环的来源，不能靠修改它改变运行因子列表。

**怎样判断接对：** 核对实际输入顺序、样本数、最大lag与实际列名，再检查stdout是否真的执行statsmodels；不能把fallback互相关的输出当F检验。ADF异常会被替成p=0，且没有实际统一平稳化；某对检验失败会跳过；VAR失败只打印skipped。当前又在多因子/多滞后里取最小p，没有校正的alpha不能直接解释成全家族错误率。正式成功退出不证明各对检验都有效，也没有结构化逐对证据Artifact。

**运行入口：** 副本根`python run_project.py --check --build-check`只检查构造；`python run_project.py`才执行分析。若要将其升级为有效组件用法，需明确频率/缺失/平稳化和样本不足行为、固定或校正多重检验、记录实际检验类型/失败/参数/每对结果，并拒绝未声明的算法fallback；这些不是本书已完成的实现。

### 变体：只检查一个明确因子

**目的：** 缩小排查范围。**改在哪里：** max_factors从3改为1。

```python
STAGES[0]["component_overrides"]["granger_causality_check"]["config"]["max_factors"] = 1
```

**行为变化：** 按CSV实际列顺序只取匹配列表中的首因子，非固定wind。**限制：** 若要指定业务因子，需要修改Case pipeline的明确选择，不能误以为max_factors是因子ID。

## mlblack.example.traffic_shap_consistency · 特征贡献的旧对照分析

**什么时候用：** 阅读线性系数、XGBoost重要度、SHAP与置换重要度的旧对照流程；不是已经定义了可验证的一致性准则，也不是可直接接到优化准入门的Bias。

**先准备什么：** 另一份完整traffic_congestion副本；同一CSV和NumPy/pandas/scikit-learn。完整对照额外需要xgboost/shap/scipy；当前缺依赖会改变参与的方法而继续打印。XGBoost构造硬编码n_jobs=-1，未按传入threads限制，所以在收敛资源面前不应直接把原实现作为规范运行配方。

**放在哪：** 原Case cases/shap_contribution_check。只读定位与构造检查可用下列Project选择；不要因为写了1线程request就认为原第三方库已经服从授权。

```python
STAGES = [{"name": "shap_only", "cases": ["shap_contribution_check"],
    "resource_requests": {"shap_contribution_check": {"threads": 1, "device": "cpu", "backend": "local"}},
    "component_overrides": {"shap_contribution_check": {
        "config": {"n_estimators": 20, "top_k": 5, "max_rows": 160}}}}]
GROUPS = {"default": {"stages": ["shap_only"]}}
```

**接入步骤：** 原builder经统一诊断工厂。pipeline全数据标准化，runner取尾部后同一批X/y拟合线性与可选XGBoost；以绝对线性系数、树内重要度、mean|SHAP|和训练样本置换重要度对照。不是把SHAP值转换成了候选目标，也没有自动创建输出模型Artifact。

**怎样判断接对：** 核对真实可用的方法数量、样本和各方法的定义；top_k显示原始特征顺序前k行，不是统一贡献排序。Agreement标签以硬编码4/4等表示，缺方法时分母仍有误导；置换在训练样本上进行，相关特征还会改变解释。旧代码只是打印对照，正式Feedback多为status/exit_code且默认目标0，不能凭成功退出宣布解释一致。当前资源违约、条件方法集合与无结构化验收必须先补齐。

**运行入口：** 副本根`python run_project.py --check --build-check`可检查规范接线；真实分析原入口仍是run_project.py，但本书不把资源面未闭合的旧分析标成可直接照跑的合规主例，本轮没有执行。若要实际使用，先让后端线程来自有效grant，固定对照方法与数据切分，再定义一致性统计和失败标准，将完整结果交正式Artifact；不应只改Catalog文案假装这些已实现。

### 变体：缩小待读配置

**目的：** 定位更小的旧实验设置。**改在哪里：** n_estimators从20改为10。

```python
STAGES[0]["component_overrides"]["shap_contribution_check"]["config"]["n_estimators"] = 10
```

**行为变化：** 仅减少原XGBoost树数。**限制：** 不修复线程授权、方法缺失、训练集偏差或结果发布，不能拿它替代上述迁移。

三例源码均位于mlblack/examples/cases/traffic_congestion/cases/各Case的build_solver.py和pipeline/main.py。可复用的正式诊断接线另见ML_DIAGNOSTIC_SCHEMA_APPLICATIONS_CN.md；那份例子没有声称实现这三种科学检验。
