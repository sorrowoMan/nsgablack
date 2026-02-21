# Case B（TSP）- Problem 逐行批注

参考实现：`my_project/problem/tsp_problem.py`

```python
class EuclideanTSPProblem(BlackBoxProblem):  # 欧式 TSP 问题
    cities: np.ndarray  # 输入城市坐标
    name: str = "EuclideanTSP"  # 问题名

    def __post_init__(self) -> None:  # dataclass 初始化后执行
        cities = np.asarray(self.cities, dtype=float)  # 强制成 float 矩阵
        if cities.ndim != 2 or cities.shape[1] != 2:  # 检查 shape=(n,2)
            raise ValueError("cities must be shape (n,2)")  # 非法就报错
        self.cities = cities  # 写回标准格式
        n = int(cities.shape[0])  # 城市数量
        bounds = {f"x{i}": [0, n - 1] for i in range(n)}  # 每个位置存城市索引
        super().__init__(name=self.name, dimension=n, bounds=bounds, objectives=["tour_length"])  # 注册问题元信息
        diff = cities[:, None, :] - cities[None, :, :]  # 两两坐标差
        self.distance_matrix = np.linalg.norm(diff, axis=2)  # 预计算距离矩阵

    def evaluate(self, x: np.ndarray) -> np.ndarray:  # 目标函数：路径长度
        perm = np.asarray(x, dtype=int).reshape(-1)  # 强制排列向量
        n = self.dimension  # 城市数
        if perm.size != n:  # 长度不对，直接给大罚值
            return np.array([1e12], dtype=float)
        if len(set(int(v) for v in perm.tolist())) != n:  # 不是合法排列（有重复）
            return np.array([1e12], dtype=float)
        total = 0.0  # 总路径长度
        for i in range(n):  # 逐边累加
            j = (i + 1) % n  # 下一站（闭环）
            total += float(self.distance_matrix[perm[i], perm[j]])  # 加边长
        return np.array([total], dtype=float)  # 单目标输出

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:  # 约束接口
        _ = x  # 这里不靠约束函数判可行
        return np.zeros(0, dtype=float)  # 可行性由 pipeline repair 保证
```

## 重点
- TSP 可行性（排列合法）放在 repair，不放在 constraints。
- objective 里有“安全网”：遇到非法排列给大罚值，避免异常中断。
