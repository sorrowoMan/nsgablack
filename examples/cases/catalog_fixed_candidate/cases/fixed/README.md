# fixed Case

语义类型solver，框架nsgablack。唯一装配入口[build_solver.py](build_solver.py)，独立入口run_solver.py。建议使用[外层Project](../../README.md)运行，由Project发放1线程、0 GPU的resource_context；Case不自行申请全局授权。

候选shape=(2,)，每个坐标在[0,1]，原始目标x0²+x1²。直属FixedSeed默认给出[0.25,0.75]，ClipRepair保护问题边界，FixedCandidateAdapter只请求单候选评估。max_steps=1使默认运行只有一个逻辑提交和一次求值。

只读fixed_candidate_trace在on_solver_finish中打印精确池引用对应的候选和原始目标。默认可核对raw_objectives=[[0.625]]、raw_violations=[0.0]，不会再调用evaluate，不把Adapter的Unit当另一个候选编码。

config参数candidate可替换固定初值；use_pipeline_initializer=True改用问题管线UniformInitializer。问题定义、候选处理、算法决策和观察分别放在problem/、pipeline/、adapter/、plugins/，builder只装配。
