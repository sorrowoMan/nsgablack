import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from typing import Callable, List, Dict, Any, Tuple, Union
from sklearn.feature_selection import mutual_info_regression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA, KernelPCA
from sklearn.cross_decomposition import PLSRegression
from sklearn.linear_model import Ridge
import warnings

class BlackBoxOptimizer(ABC):
    """黑箱优化器抽象基类"""
    
    @abstractmethod
    def optimize(self, objective_func: Callable, bounds: List[Tuple], 
                 n_calls: int, **kwargs) -> Dict:
        """执行优化"""
        pass
    
    @abstractmethod
    def get_evaluation_history(self) -> Tuple[np.ndarray, np.ndarray]:
        """获取评估历史 (X, y)"""
        pass


class SimpleEvolutionaryOptimizer(BlackBoxOptimizer):
    """简单的进化策略优化器 - 不依赖外部库"""
    
    def __init__(self, population_size=50, mutation_rate=0.1, random_state=42):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.random_state = random_state
        self.X_history_ = []
        self.y_history_ = []
        np.random.seed(random_state)
        
    def optimize(self, objective_func: Callable, bounds: List[Tuple], 
                 n_calls: int, **kwargs) -> Dict:
        """
        使用简单进化策略进行优化
        """
        n_dims = len(bounds)
        self.X_history_ = []
        self.y_history_ = []
        
        # 初始化种群
        population = self._initialize_population(n_dims, bounds)
        
        best_solution = None
        best_fitness = float('inf')
        
        for iteration in range(n_calls // self.population_size):
            # 评估种群
            fitness = []
            for individual in population:
                fit = objective_func(individual)
                fitness.append(fit)
                self.X_history_.append(individual)
                self.y_history_.append(fit)
                
                # 更新最优解
                if fit < best_fitness:
                    best_fitness = fit
                    best_solution = individual.copy()
            
            # 选择、交叉、变异
            population = self._evolve(population, fitness, bounds)
            
            if iteration % 10 == 0:
                print(f"迭代 {iteration}, 最优值: {best_fitness:.6f}")
        
        return {
            'x': best_solution,
            'fun': best_fitness,
            'success': True,
            'history': (np.array(self.X_history_), np.array(self.y_history_))
        }
    
    def _initialize_population(self, n_dims: int, bounds: List[Tuple]) -> np.ndarray:
        """初始化种群"""
        population = np.zeros((self.population_size, n_dims))
        for i in range(n_dims):
            low, high = bounds[i]
            population[:, i] = np.random.uniform(low, high, self.population_size)
        return population
    
    def _evolve(self, population: np.ndarray, fitness: List[float], 
                bounds: List[Tuple]) -> np.ndarray:
        """进化操作"""
        # 选择 - 锦标赛选择
        new_population = []
        for _ in range(self.population_size):
            # 随机选择两个个体
            idx1, idx2 = np.random.choice(len(population), 2, replace=False)
            if fitness[idx1] < fitness[idx2]:
                winner = population[idx1].copy()
            else:
                winner = population[idx2].copy()
            new_population.append(winner)
        
        # 交叉 - 均匀交叉
        for i in range(0, self.population_size, 2):
            if i + 1 < self.population_size:
                parent1 = new_population[i]
                parent2 = new_population[i + 1]
                
                # 均匀交叉
                crossover_mask = np.random.random(len(parent1)) > 0.5
                child1 = parent1.copy()
                child2 = parent2.copy()
                child1[crossover_mask] = parent2[crossover_mask]
                child2[crossover_mask] = parent1[crossover_mask]
                
                new_population[i] = child1
                new_population[i + 1] = child2
        
        # 变异 - 高斯变异
        for i in range(self.population_size):
            if np.random.random() < self.mutation_rate:
                n_dims = len(population[i])
                mutation_strength = 0.1  # 变异强度
                for j in range(n_dims):
                    low, high = bounds[j]
                    range_val = high - low
                    mutation = np.random.normal(0, mutation_strength * range_val)
                    new_population[i][j] += mutation
                    # 边界处理
                    
                    new_population[i][j] = np.clip(new_population[i][j], low, high)
        
        return np.array(new_population)
    
    def get_evaluation_history(self) -> Tuple[np.ndarray, np.ndarray]:
        return np.array(self.X_history_), np.array(self.y_history_)


class UniversalFeatureSelector:
    """
    通用特征选择器 - 支持智能降维
    """
    
    def __init__(self, optimizer: BlackBoxOptimizer = None, feature_names: List[str] = None):
        self.optimizer = optimizer
        self.feature_names = feature_names
        self.scaler = StandardScaler()
        self.feature_importance_ = None
        self.selected_features_ = None
        self.history_ = {}
        self.reduction_info_ = {}  # 存储降维信息
        
    def set_optimizer(self, optimizer: BlackBoxOptimizer):
        """设置优化器"""
        self.optimizer = optimizer
        
    def collect_data(self, objective_func: Callable, bounds: List[Tuple], 
                    initial_samples: int = 100, method: str = 'lhs') -> Tuple[np.ndarray, np.ndarray]:
        """收集初始数据用于特征分析"""
        n_dims = len(bounds)
        
        if method == 'lhs':
            samples = self._latin_hypercube_sampling(n_dims, initial_samples, bounds)
        elif method == 'random':
            samples = self._random_sampling(n_dims, initial_samples, bounds)
        else:
            raise ValueError(f"不支持的采样方法: {method}")
        
        # 评估样本
        print(f"正在评估 {len(samples)} 个初始样本...")
        y = np.array([objective_func(sample) for sample in samples])
        
        return samples, y
    
    def analyze_features(self, X: np.ndarray, y: np.ndarray, 
                        methods: List[str] = None) -> Dict:
        """综合特征分析"""
        if methods is None:
            methods = ['mutual_info', 'random_forest', 'correlation', 'variance']
            
        n_dims = X.shape[1]
        if self.feature_names is None:
            self.feature_names = [f'x{i}' for i in range(n_dims)]
            
        results = {}
        
        if 'mutual_info' in methods:
            print("进行互信息分析...")
            results['mutual_info'] = self._mutual_info_analysis(X, y)
            
        if 'random_forest' in methods:
            print("进行随机森林分析...")
            results['random_forest'] = self._random_forest_analysis(X, y)
            
        if 'correlation' in methods:
            print("进行相关性分析...")
            results['correlation'] = self._correlation_analysis(X, y)
            
        if 'variance' in methods:
            print("进行方差分析...")
            results['variance'] = self._variance_analysis(X)
        
        self.history_['feature_analysis'] = results
        return results
    
    def smart_feature_selection(self, X: np.ndarray, y: np.ndarray, 
                               strategy: str = 'composite',
                               reduction_method: str = 'cumulative',
                               threshold: float = 0.95,
                               min_features: int = 1,
                               max_features: int = None) -> List[int]:
        """
        智能特征选择 - 自动确定降维维度
        
        参数:
        - reduction_method: 降维方法 ('cumulative', 'elbow', 'significant')
        - threshold: 累计重要性阈值 (0-1)
        - min_features: 最少保留特征数
        - max_features: 最多保留特征数
        """
        n_dims = X.shape[1]
        if max_features is None:
            max_features = n_dims
            
        analysis_results = self.analyze_features(X, y)
        composite_scores = self._compute_composite_scores(analysis_results)
        
        # 根据选择的降维方法确定特征数量
        if reduction_method == 'cumulative':
            n_selected = self._cumulative_threshold_selection(composite_scores, threshold, min_features, max_features)
        elif reduction_method == 'elbow':
            n_selected = self._elbow_method_selection(composite_scores, min_features, max_features)
        elif reduction_method == 'significant':
            n_selected = self._significant_feature_selection(composite_scores, min_features, max_features)
        else:
            raise ValueError(f"不支持的降维方法: {reduction_method}")
        
        # 选择特征
        selected = self._top_k_selection(composite_scores, n_selected)
        self.selected_features_ = selected
        
        # 保存降维信息
        self.reduction_info_ = {
            'original_dims': n_dims,
            'reduced_dims': n_selected,
            'reduction_ratio': 1 - n_selected / n_dims,
            'method': reduction_method,
            'composite_scores': composite_scores
        }
        
        # 打印选择结果
        self._print_selection_summary(selected, composite_scores)
            
        return selected
    
    def select_features(self, X: np.ndarray, y: np.ndarray, 
                       strategy: str = 'composite', 
                       n_features: int = None,
                       **kwargs) -> List[int]:
        """
        特征选择主函数 - 兼容旧接口，支持智能降维
        """
        if n_features is not None:
            # 使用固定维度选择
            return self._fixed_dimension_selection(X, y, strategy, n_features)
        else:
            # 使用智能降维
            return self.smart_feature_selection(X, y, strategy, **kwargs)
    
    def _fixed_dimension_selection(self, X: np.ndarray, y: np.ndarray,
                                 strategy: str, n_features: int) -> List[int]:
        """固定维度特征选择"""
        analysis_results = self.analyze_features(X, y)
        
        if strategy == 'composite':
            composite_scores = self._compute_composite_scores(analysis_results)
            selected = self._top_k_selection(composite_scores, n_features)
        elif strategy == 'mutual_info':
            selected = self._top_k_selection(analysis_results['mutual_info'], n_features)
        elif strategy == 'random_forest':
            selected = self._top_k_selection(analysis_results['random_forest'], n_features)
        else:
            raise ValueError(f"未知策略: {strategy}")
            
        self.selected_features_ = selected
        return selected
    
    def create_reduced_problem(self, original_func: Callable, 
                             selected_features: List[int],
                             bounds: List[Tuple] = None,
                             fill: str = 'midpoint',
                             fill_value: float = 0.5) -> Callable:
        """创建降维后的优化问题
        
        参数:
        - bounds: 原问题各维的边界，用于计算未选特征的填充值
        - fill: 未选特征填充策略: 'midpoint' 使用每维边界中点; 'value' 使用 fill_value
        - fill_value: 当 fill='value' 时使用的常数填充值
        """
        if bounds is not None:
            n_dims_original = len(bounds)
        else:
            n_dims_original = len(self.feature_names) if self.feature_names else max(selected_features) + 1

        if bounds is not None and fill == 'midpoint':
            base_vector = np.array([(low + high) / 2.0 for (low, high) in bounds], dtype=float)
        else:
            base_vector = np.full(n_dims_original, fill_value, dtype=float)
        
        def reduced_objective(reduced_params):
            full_params = base_vector.copy()
            full_params[selected_features] = reduced_params
            return original_func(full_params)
        
        return reduced_objective

    def create_reduced_problem_bundle(self, original_func: Callable,
                                     selected_features: List[int],
                                     bounds: List[Tuple] = None,
                                     fill: str = 'midpoint',
                                     fill_value: float = 0.5) -> Tuple[Callable, Callable]:
        """创建降维问题与映射函数的打包返回
        返回:
        - reduced_objective(reduced_params)
        - expand_to_full(reduced_params) -> full_params
        """
        if bounds is not None:
            n_dims_original = len(bounds)
        else:
            n_dims_original = len(self.feature_names) if self.feature_names else max(selected_features) + 1

        if bounds is not None and fill == 'midpoint':
            base_vector = np.array([(low + high) / 2.0 for (low, high) in bounds], dtype=float)
        else:
            base_vector = np.full(n_dims_original, fill_value, dtype=float)

        def reduced_objective(reduced_params):
            full_params = base_vector.copy()
            full_params[selected_features] = reduced_params
            return original_func(full_params)

        def expand_to_full(reduced_params):
            full_params = base_vector.copy()
            full_params[selected_features] = reduced_params
            return full_params

        return reduced_objective, expand_to_full

    def prepare_reduced_problem(self, objective_func: Callable,
                               bounds: List[Tuple],
                               selection_strategy: str = 'composite',
                               n_features: int = None,
                               sampling_method: str = 'lhs',
                               initial_samples: int = 50,
                               fill: str = 'midpoint',
                               fill_value: float = 0.5,
                               **smart_selection_kwargs) -> Dict[str, Any]:
        """一站式导出降维优化问题，便于外部GA直接调用
        返回字典包含:
        - reduced_objective, reduced_bounds, selected_features
        - expand_to_full 映射函数
        - reduction_info, feature_analysis, initial_samples
        """
        # 数据收集与特征选择
        X, y = self.collect_data(objective_func, bounds, initial_samples, sampling_method)
        if n_features is not None:
            selected = self.select_features(X, y, selection_strategy, n_features=n_features)
        else:
            selected = self.smart_feature_selection(X, y, selection_strategy, **smart_selection_kwargs)

        reduced_bounds = [bounds[i] for i in selected]
        reduced_objective, expand_to_full = self.create_reduced_problem_bundle(
            objective_func, selected, bounds=bounds, fill=fill, fill_value=fill_value
        )

        return {
            'reduced_objective': reduced_objective,
            'reduced_bounds': reduced_bounds,
            'selected_features': selected,
            'expand_to_full': expand_to_full,
            'reduction_info': self.reduction_info_,
            'feature_analysis': self.history_.get('feature_analysis', {}),
            'initial_samples': (X, y),
        }
    
    def optimize_with_feature_selection(self, objective_func: Callable,
                                      bounds: List[Tuple], 
                                      n_calls: int = 200,
                                      initial_samples: int = 50,
                                      selection_strategy: str = 'composite',
                                      n_features: int = None,
                                      sampling_method: str = 'lhs',
                                      **smart_selection_kwargs) -> Dict:
        """带特征选择的完整优化流程"""
        if self.optimizer is None:
            self.optimizer = SimpleEvolutionaryOptimizer()
            print("使用默认进化策略优化器")
        
        # 阶段1: 数据收集和特征分析
        print("=" * 50)
        print("阶段1: 数据收集和特征分析")
        print("=" * 50)
        X, y = self.collect_data(objective_func, bounds, initial_samples, sampling_method)
        
        # 阶段2: 特征选择
        print("\n" + "=" * 50)
        print("阶段2: 特征选择")
        print("=" * 50)
        
        if n_features is not None:
            selected_features = self.select_features(X, y, selection_strategy, n_features)
            reduction_type = "固定维度"
        else:
            selected_features = self.smart_feature_selection(X, y, selection_strategy, **smart_selection_kwargs)
            reduction_type = "智能降维"
            
        print(f"降维方式: {reduction_type}")
        print(f"降维信息: {self.reduction_info_}")
        
        # 创建降维后的问题
        reduced_bounds = [bounds[i] for i in selected_features]
        reduced_objective = self.create_reduced_problem(
            original_func=objective_func,
            selected_features=selected_features,
            bounds=bounds,
            fill='midpoint'
        )
        
        # 阶段3: 降维空间优化
        print("\n" + "=" * 50)
        print("阶段3: 在降维空间优化")
        print("=" * 50)
        result = self.optimizer.optimize(reduced_objective, reduced_bounds, 
                                       n_calls - initial_samples)
        
        # 阶段4: 映射回原始空间
        print("\n" + "=" * 50)
        print("阶段4: 结果映射")
        print("=" * 50)
        best_params_reduced = result['x']
        # 使用各维边界中点作为未选特征的默认填充值
        midpoint = np.array([(low + high) / 2.0 for (low, high) in bounds], dtype=float)
        best_params_full = midpoint
        best_params_full[selected_features] = best_params_reduced
        
        result['x_full'] = best_params_full
        result['selected_features'] = selected_features
        result['feature_analysis'] = self.history_['feature_analysis']
        result['reduction_info'] = self.reduction_info_
        result['initial_samples'] = (X, y)
        
        print(f"优化完成!")
        print(f"原始最优解: {best_params_full}")
        print(f"原始最优值: {result['fun']}")
        
        return result
    
    # ========== 智能降维方法 ==========
    
    def _compute_composite_scores(self, analysis_results: Dict) -> np.ndarray:
        """计算综合特征评分"""
        n_dims = len(next(iter(analysis_results.values())))
        composite_scores = np.zeros(n_dims)
        
        # 加权综合评分
        weights = {
            'mutual_info': 1.5,  # 互信息权重更高
            'random_forest': 1.2,
            'correlation': 1.0,
            'variance': 0.8
        }
        
        for method, scores in analysis_results.items():
            weight = weights.get(method, 1.0)
            composite_scores += weight * scores
        
        # 归一化
        if np.max(composite_scores) > 0:
            composite_scores /= np.max(composite_scores)
            
        self.feature_importance_ = composite_scores
        return composite_scores
    
    def _cumulative_threshold_selection(self, scores: np.ndarray, threshold: float,
                                      min_features: int, max_features: int) -> int:
        """累计重要性阈值方法"""
        sorted_scores = np.sort(scores)[::-1]  # 降序排列
        cumulative_scores = np.cumsum(sorted_scores)
        total_importance = cumulative_scores[-1]
        
        # 找到达到阈值所需的最小特征数
        n_selected = np.argmax(cumulative_scores >= threshold * total_importance) + 1
        n_selected = max(min_features, min(n_selected, max_features))
        
        print(f"累计重要性方法: 达到{threshold*100}%重要性需要 {n_selected} 个特征")
        return n_selected
    
    def _elbow_method_selection(self, scores: np.ndarray, 
                              min_features: int, max_features: int) -> int:
        """肘部法则选择"""
        sorted_scores = np.sort(scores)[::-1]
        n_features_range = range(1, len(scores) + 1)
        
        # 计算每个k对应的累计重要性
        cumulative_importance = [np.sum(sorted_scores[:k]) for k in n_features_range]
        
        # 计算二阶差分找到"肘部"
        first_diff = np.diff(cumulative_importance)
        second_diff = np.diff(first_diff)
        
        # 找到变化率最大的点
        if len(second_diff) > 0:
            elbow_point = np.argmin(second_diff) + 2  # +2 因为二阶差分
        else:
            elbow_point = len(scores) // 2
            
        n_selected = max(min_features, min(elbow_point, max_features))
        print(f"肘部法则方法: 选择 {n_selected} 个特征")
        return n_selected
    
    def _significant_feature_selection(self, scores: np.ndarray,
                                    min_features: int, max_features: int) -> int:
        """显著性特征选择"""
        # 计算平均重要性
        mean_score = np.mean(scores)
        std_score = np.std(scores)
        
        # 选择高于平均值一个标准差的特征
        significant_mask = scores > (mean_score + 0.5 * std_score)
        n_selected = max(min_features, min(np.sum(significant_mask), max_features))
        
        print(f"显著性方法: 选择 {n_selected} 个特征 (阈值: {mean_score + 0.5*std_score:.3f})")
        return n_selected
    
    def _print_selection_summary(self, selected: List[int], scores: np.ndarray):
        """打印选择摘要"""
        n_dims = len(scores)
        n_selected = len(selected)
        
        print(f"智能降维结果:")
        print(f"  原始维度: {n_dims}")
        print(f"  降维后维度: {n_selected}")
        print(f"  降维比例: {(1 - n_selected/n_dims)*100:.1f}%")
        print(f"  选定特征索引: {selected}")
        
        if self.feature_names:
            selected_names = [self.feature_names[i] for i in selected]
            print(f"  选定特征名称: {selected_names}")
            
        # 打印特征重要性排名
        print("\n特征重要性排名:")
        sorted_indices = np.argsort(scores)[::-1]
        for i, idx in enumerate(sorted_indices):
            importance = scores[idx]
            feature_name = self.feature_names[idx] if self.feature_names else f'x{idx}'
            selection_flag = "✓" if idx in selected else " "
            print(f"  {i+1:2d}. [{selection_flag}] {feature_name}: {importance:.4f}")
    
    # ========== 基础方法 ==========
    
    def _latin_hypercube_sampling(self, n_dims: int, n_samples: int, 
                                bounds: List[Tuple]) -> np.ndarray:
        """拉丁超立方采样"""
        samples = np.zeros((n_samples, n_dims))
        for i in range(n_dims):
            samples[:, i] = np.random.permutation(n_samples) + np.random.uniform(0, 1, n_samples)
            samples[:, i] = samples[:, i] / n_samples
            
        # 缩放到实际边界
        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)
            
        return samples
    
    def _random_sampling(self, n_dims: int, n_samples: int, 
                       bounds: List[Tuple]) -> np.ndarray:
        """随机采样"""
        samples = np.random.uniform(0, 1, (n_samples, n_dims))
        
        # 缩放到实际边界
        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)
            
        return samples
    
    def _mutual_info_analysis(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """互信息分析"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mi_scores = mutual_info_regression(X, y, random_state=42)
        return mi_scores / (np.max(mi_scores) + 1e-10)  # 归一化
    
    def _random_forest_analysis(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """随机森林特征重要性"""
        rf = RandomForestRegressor(n_estimators=100, random_state=42)
        rf.fit(X, y)
        importance = rf.feature_importances_
        return importance / (np.max(importance) + 1e-10)  # 归一化
    
    def _correlation_analysis(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """相关性分析"""
        corr_scores = np.array([np.abs(np.corrcoef(X[:, i], y)[0, 1]) 
                              for i in range(X.shape[1])])
        corr_scores = np.nan_to_num(corr_scores, nan=0.0)
        return corr_scores / (np.max(corr_scores) + 1e-10)  # 归一化
    
    def _variance_analysis(self, X: np.ndarray) -> np.ndarray:
        """方差分析"""
        variances = np.var(X, axis=0)
        return variances / (np.max(variances) + 1e-10)  # 归一化
    
    def _top_k_selection(self, scores: np.ndarray, n_features: int) -> List[int]:
        """选择Top-K特征"""
        return np.argsort(scores)[-n_features:].tolist()
    
    def plot_feature_importance(self, save_path: str = None):
        """可视化特征重要性"""
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
            
            if 'feature_analysis' not in self.history_:
                print("请先运行特征分析")
                return
                
            analysis = self.history_['feature_analysis']
            n_methods = len(analysis)
            
            fig, axes = plt.subplots(1, n_methods + 1, figsize=(5*(n_methods + 1), 6))
            
            if n_methods == 1:
                axes = [axes[0], axes[1]]
            elif n_methods == 0:
                axes = [axes]
                
            # 绘制各方法的重要性
            for idx, (method, scores) in enumerate(analysis.items()):
                if idx >= len(axes) - 1:
                    break
                ax = axes[idx]
                colors = ['red' if i in self.selected_features_ else 'skyblue' 
                         for i in range(len(scores))]
                
                y_pos = np.arange(len(scores))
                ax.barh(y_pos, scores, color=colors)
                ax.set_yticks(y_pos)
                ax.set_yticklabels(self.feature_names)
                ax.set_title(f'{method.upper()}')
                ax.set_xlabel('Importance Score')
            
            # 绘制综合重要性
            if hasattr(self, 'feature_importance_') and self.feature_importance_ is not None:
                ax_composite = axes[-1]
                colors = ['red' if i in self.selected_features_ else 'skyblue' 
                         for i in range(len(self.feature_importance_))]
                
                y_pos = np.arange(len(self.feature_importance_))
                ax_composite.barh(y_pos, self.feature_importance_, color=colors)
                ax_composite.set_yticks(y_pos)
                ax_composite.set_yticklabels(self.feature_names)
                ax_composite.set_title('COMPOSITE')
                ax_composite.set_xlabel('Importance Score')
            
            plt.tight_layout()
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.show()
            
        except ImportError:
            print("请安装matplotlib和seaborn来使用可视化功能")


# ========== 无监督降维：PCA 适配器 ==========
class PCAReducer:
    """基于 PCA 的线性嵌入：在降维空间优化，再解码回原空间"""
    def __init__(self, n_components: int, scale: bool = True):
        self.n_components = n_components
        self.scale = scale
        self.scaler = StandardScaler() if scale else None
        self.pca = PCA(n_components=n_components, random_state=42)
        self.fitted_ = False
        self.bounds_ = None  # 原空间 bounds

    def fit(self, X: np.ndarray, bounds: List[Tuple]):
        self.bounds_ = bounds
        X_proc = X
        if self.scaler is not None:
            X_proc = self.scaler.fit_transform(X_proc)
        self.pca.fit(X_proc)
        self.fitted_ = True
        return self

    def encode(self, X: np.ndarray) -> np.ndarray:
        assert self.fitted_, "PCAReducer 未拟合"
        X_proc = X
        if self.scaler is not None:
            X_proc = self.scaler.transform(X_proc)
        return self.pca.transform(X_proc)

    def decode(self, Z: np.ndarray) -> np.ndarray:
        assert self.fitted_, "PCAReducer 未拟合"
        X_proc = self.pca.inverse_transform(Z)
        if self.scaler is not None:
            X = self.scaler.inverse_transform(X_proc)
        else:
            X = X_proc
        # 裁剪回原始边界
        X_clipped = np.empty_like(X)
        for i, (low, high) in enumerate(self.bounds_):
            X_clipped[:, i] = np.clip(X[:, i], low, high)
        return X_clipped


def prepare_pca_reduced_problem(objective_func: Callable,
                               bounds: List[Tuple],
                               n_components: int,
                               initial_samples: int = 200,
                               sampling_method: str = 'lhs',
                               scale: bool = True,
                               pad_ratio: float = 0.10) -> Dict[str, Any]:
    """使用 PCA 构造无监督降维优化问题。
    步骤：在原边界内采样→拟合(可选标准化)+PCA→用编码后的样本确定降维边界→
         在降维空间优化，解码回原空间评估目标。

    返回:
    - reduced_objective(z): 在降维空间评估目标
    - reduced_bounds: 降维变量边界
    - expand_to_full(z): 将降维解映射回全维
    - pca_model: PCAReducer 实例
    - samples_info: (X, Z) 采样与编码的缓存
    """
    n_dims = len(bounds)
    # 采样
    if sampling_method == 'lhs':
        samples = np.zeros((initial_samples, n_dims))
        for i in range(n_dims):
            samples[:, i] = np.random.permutation(initial_samples) + np.random.uniform(0, 1, initial_samples)
            samples[:, i] = samples[:, i] / initial_samples
        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)
    elif sampling_method == 'random':
        samples = np.random.uniform(0, 1, (initial_samples, n_dims))
        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)
    else:
        raise ValueError(f"不支持的采样方法: {sampling_method}")

    # 拟合 PCA
    reducer = PCAReducer(n_components=n_components, scale=scale).fit(samples, bounds)
    Z = reducer.encode(samples)

    # 用编码样本确定降维边界（加少量边际）
    reduced_bounds = []
    for j in range(n_components):
        z_min, z_max = float(np.min(Z[:, j])), float(np.max(Z[:, j]))
        span = z_max - z_min
        pad = max(1e-6, pad_ratio * span)
        reduced_bounds.append((z_min - pad, z_max + pad))

    def reduced_objective(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return float(objective_func(X[0]))

    def expand_to_full(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return X[0]

    return {
        'reduced_objective': reduced_objective,
        'reduced_bounds': reduced_bounds,
        'expand_to_full': expand_to_full,
        'pca_model': reducer,
        'samples_info': {'X': samples, 'Z': Z}
    }


# ========== 无监督降维：Kernel PCA（带回归解码器预像逼近） ==========
class KernelPCAReducer:
    """基于 Kernel PCA 的非线性嵌入。为实现解码（pre-image），使用多输出回归器从 Z→X 拟合近似解码器。"""
    def __init__(self, n_components: int, kernel: str = 'rbf', scale: bool = True, **kernel_kwargs):
        self.n_components = n_components
        self.kernel = kernel
        self.kernel_kwargs = kernel_kwargs
        self.scale = scale
        self.scaler = StandardScaler() if scale else None
        self.kpca = KernelPCA(n_components=n_components, kernel=kernel, fit_inverse_transform=False, **kernel_kwargs)
        self.decoder = Ridge(alpha=1.0)  # 多输出回归器（Ridge 可直接处理多目标）
        self.fitted_ = False
        self.bounds_ = None

    def fit(self, X: np.ndarray, bounds: List[Tuple]):
        self.bounds_ = bounds
        Xp = X
        if self.scaler is not None:
            Xp = self.scaler.fit_transform(Xp)
        Z = self.kpca.fit_transform(Xp)
        # 训练解码器：Z -> 原始 X（未缩放空间）
        self.decoder.fit(Z, X)
        self.fitted_ = True
        return self

    def encode(self, X: np.ndarray) -> np.ndarray:
        assert self.fitted_, 'KernelPCAReducer 未拟合'
        Xp = X
        if self.scaler is not None:
            Xp = self.scaler.transform(Xp)
        return self.kpca.transform(Xp)

    def decode(self, Z: np.ndarray) -> np.ndarray:
        assert self.fitted_, 'KernelPCAReducer 未拟合'
        X_hat = self.decoder.predict(Z)
        # 裁剪回原始边界
        Xc = np.empty_like(X_hat)
        for i, (low, high) in enumerate(self.bounds_):
            Xc[:, i] = np.clip(X_hat[:, i], low, high)
        return Xc


def prepare_kpca_reduced_problem(objective_func: Callable,
                                bounds: List[Tuple],
                                n_components: int,
                                initial_samples: int = 300,
                                sampling_method: str = 'lhs',
                                kernel: str = 'rbf',
                                scale: bool = True,
                                decoder_alpha: float = 1.0,
                                pad_ratio: float = 0.10,
                                **kernel_kwargs) -> Dict[str, Any]:
    n_dims = len(bounds)
    # 采样
    if sampling_method == 'lhs':
        samples = np.zeros((initial_samples, n_dims))
        for i in range(n_dims):
            samples[:, i] = np.random.permutation(initial_samples) + np.random.uniform(0, 1, initial_samples)
            samples[:, i] = samples[:, i] / initial_samples
        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)
    elif sampling_method == 'random':
        samples = np.random.uniform(0, 1, (initial_samples, n_dims))
        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)
    else:
        raise ValueError('不支持的采样方法')

    reducer = KernelPCAReducer(n_components=n_components, kernel=kernel, scale=scale, **kernel_kwargs)
    reducer.decoder = Ridge(alpha=decoder_alpha)
    reducer.fit(samples, bounds)
    Z = reducer.encode(samples)

    reduced_bounds = []
    for j in range(n_components):
        z_min, z_max = float(np.min(Z[:, j])), float(np.max(Z[:, j]))
        span = z_max - z_min
        pad = max(1e-6, pad_ratio * span)
        reduced_bounds.append((z_min - pad, z_max + pad))

    def reduced_objective(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return float(objective_func(X[0]))

    def expand_to_full(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return X[0]

    return {
        'reduced_objective': reduced_objective,
        'reduced_bounds': reduced_bounds,
        'expand_to_full': expand_to_full,
        'kpca_model': reducer,
        'samples_info': {'X': samples, 'Z': Z}
    }


# ========== 监督式降维：PLS（部分最小二乘） ==========
class PLSReducer:
    """PLS 监督式线性嵌入：使用目标 y 引导子空间；解码用线性重构 X≈T P^T。"""
    def __init__(self, n_components: int, scale: bool = True):
        self.n_components = n_components
        self.scale = scale
        self.x_scaler = StandardScaler() if scale else None
        self.pls = PLSRegression(n_components=n_components)
        self.x_mean_ = None
        self.fitted_ = False
        self.bounds_ = None

    def fit(self, X: np.ndarray, y: np.ndarray, bounds: List[Tuple]):
        self.bounds_ = bounds
        Xp = X
        if self.x_scaler is not None:
            Xp = self.x_scaler.fit_transform(Xp)
        self.pls.fit(Xp, y.reshape(-1, 1))
        # 记录均值用于解码偏移
        self.x_mean_ = np.mean(X, axis=0)
        self.fitted_ = True
        return self

    def encode(self, X: np.ndarray) -> np.ndarray:
        assert self.fitted_, 'PLSReducer 未拟合'
        Xp = X
        if self.x_scaler is not None:
            Xp = self.x_scaler.transform(Xp)
        T = self.pls.transform(Xp)  # X_scores
        return T

    def decode(self, Z: np.ndarray) -> np.ndarray:
        assert self.fitted_, 'PLSReducer 未拟合'
        # 线性近似：X ≈ T P^T + mean，P 为 x_loadings_
        P = self.pls.x_loadings_
        X_hat = Z @ P.T
        if self.x_scaler is not None:
            # 逆标准化近似：用输入 X 的均值和方差恢复尺度
            # 简化处理：使用拟合时 X 的均值（已记录 x_mean_），方差影响忽略
            X_hat = X_hat + self.x_scaler.mean_
        else:
            X_hat = X_hat + self.x_mean_
        # 裁剪到 bounds
        Xc = np.empty_like(X_hat)
        for i, (low, high) in enumerate(self.bounds_):
            Xc[:, i] = np.clip(X_hat[:, i], low, high)
        return Xc


def prepare_pls_reduced_problem(objective_func: Callable,
                               bounds: List[Tuple],
                               n_components: int,
                               initial_samples: int = 200,
                               sampling_method: str = 'lhs',
                               scale: bool = True,
                               pad_ratio: float = 0.10) -> Dict[str, Any]:
    n_dims = len(bounds)
    # 采样
    if sampling_method == 'lhs':
        samples = np.zeros((initial_samples, n_dims))
        for i in range(n_dims):
            samples[:, i] = np.random.permutation(initial_samples) + np.random.uniform(0, 1, initial_samples)
            samples[:, i] = samples[:, i] / initial_samples
        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)
    elif sampling_method == 'random':
        samples = np.random.uniform(0, 1, (initial_samples, n_dims))
        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)
    else:
        raise ValueError('不支持的采样方法')

    y = np.array([objective_func(x) for x in samples], dtype=float)

    reducer = PLSReducer(n_components=n_components, scale=scale).fit(samples, y, bounds)
    Z = reducer.encode(samples)

    reduced_bounds = []
    for j in range(n_components):
        z_min, z_max = float(np.min(Z[:, j])), float(np.max(Z[:, j]))
        span = z_max - z_min
        pad = max(1e-6, pad_ratio * span)
        reduced_bounds.append((z_min - pad, z_max + pad))

    def reduced_objective(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return float(objective_func(X[0]))

    def expand_to_full(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return X[0]

    return {
        'reduced_objective': reduced_objective,
        'reduced_bounds': reduced_bounds,
        'expand_to_full': expand_to_full,
        'pls_model': reducer,
        'samples_info': {'X': samples, 'Z': Z, 'y': y}
    }


# ========== 监督式降维：Active Subspace（有限差分近似梯度） ==========
def prepare_active_subspace_reduced_problem(objective_func: Callable,
                                            bounds: List[Tuple],
                                            n_components: int,
                                            initial_samples: int = 200,
                                            sampling_method: str = 'lhs',
                                            gradient_eps: float = 1e-4,
                                            scale: bool = True,
                                            pad_ratio: float = 0.10) -> Dict[str, Any]:
    n_dims = len(bounds)
    # 采样
    if sampling_method == 'lhs':
        samples = np.zeros((initial_samples, n_dims))
        for i in range(n_dims):
            samples[:, i] = np.random.permutation(initial_samples) + np.random.uniform(0, 1, initial_samples)
            samples[:, i] = samples[:, i] / initial_samples
        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)
    elif sampling_method == 'random':
        samples = np.random.uniform(0, 1, (initial_samples, n_dims))
        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)
    else:
        raise ValueError('不支持的采样方法')

    # 可选标准化用于数值稳定
    X = samples.copy()
    if scale:
        scaler = StandardScaler()
        Xp = scaler.fit_transform(X)
    else:
        scaler = None
        Xp = X

    # 有限差分近似梯度，计算 C = E[g g^T]
    def finite_diff_grad(x):
        g = np.zeros(n_dims)
        fx = objective_func(x)
        for i in range(n_dims):
            h = gradient_eps * (bounds[i][1] - bounds[i][0] + 1e-12)
            xh = x.copy()
            xh[i] = np.clip(xh[i] + h, bounds[i][0], bounds[i][1])
            g[i] = (objective_func(xh) - fx) / (h + 1e-12)
        return g

    grads = np.array([finite_diff_grad(x) for x in X], dtype=float)
    C = (grads.T @ grads) / max(1, grads.shape[0])
    # 特征分解
    evals, evecs = np.linalg.eigh(C)
    idx = np.argsort(evals)[::-1]
    W = evecs[:, idx[:n_components]]  # 取主导子空间

    x0 = np.mean(Xp, axis=0)  # 参考点

    def encode_points(Xin):
        Xp_in = scaler.transform(Xin) if scaler is not None else Xin
        Z = (Xp_in - x0) @ W
        return Z

    def decode_points(Zin):
        Xp_rec = x0 + Zin @ W.T
        Xrec = scaler.inverse_transform(Xp_rec) if scaler is not None else Xp_rec
        # 裁剪回边界
        Xc = np.empty_like(Xrec)
        for i, (low, high) in enumerate(bounds):
            Xc[:, i] = np.clip(Xrec[:, i], low, high)
        return Xc

    Z = encode_points(X)

    reduced_bounds = []
    for j in range(n_components):
        z_min, z_max = float(np.min(Z[:, j])), float(np.max(Z[:, j]))
        span = z_max - z_min
        pad = max(1e-6, pad_ratio * span)
        reduced_bounds.append((z_min - pad, z_max + pad))

    def reduced_objective(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        Xfull = decode_points(z)
        return float(objective_func(Xfull[0]))

    def expand_to_full(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        Xfull = decode_points(z)
        return Xfull[0]

    return {
        'reduced_objective': reduced_objective,
        'reduced_bounds': reduced_bounds,
        'expand_to_full': expand_to_full,
        'active_subspace': {'W': W, 'x0': x0, 'scaler': scaler},
        'samples_info': {'X': X, 'Z': Z, 'grads': grads, 'evals': evals[idx]}
    }


# ========== 非线性自编码器（可选 TensorFlow 依赖） ==========
class AutoencoderReducer:
    """基于 Keras 的 MLP 自编码器。需要安装 tensorflow。"""
    def __init__(self, n_components: int, hidden_ratio: float = 2.0, scale: bool = True,
                 epochs: int = 100, batch_size: int = 64, learning_rate: float = 1e-3):
        self.n_components = n_components
        self.hidden_ratio = hidden_ratio
        self.scale = scale
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.scaler = StandardScaler() if scale else None
        self.model = None
        self.encoder = None
        self.decoder = None
        self.fitted_ = False
        self.bounds_ = None

    def _build(self, input_dim):
        try:
            import tensorflow as tf
            keras = tf.keras
            layers = tf.keras.layers
        except Exception as e:
            raise ImportError(f"需要 tensorflow 才能使用 AutoencoderReducer: {e}")
        inputs = keras.Input(shape=(input_dim,))
        h = layers.Dense(int(self.hidden_ratio * self.n_components), activation='relu')(inputs)
        z = layers.Dense(self.n_components, activation=None, name='latent')(h)
        h2 = layers.Dense(int(self.hidden_ratio * self.n_components), activation='relu')(z)
        outputs = layers.Dense(input_dim, activation=None)(h2)
        model = keras.Model(inputs, outputs)
        model.compile(optimizer=keras.optimizers.Adam(self.learning_rate), loss='mse')

        # 单独的编码器/解码器
        encoder = keras.Model(inputs, z)
        latent_inputs = keras.Input(shape=(self.n_components,))
        d = model.layers[-2](latent_inputs)
        decoded = model.layers[-1](d)
        decoder = keras.Model(latent_inputs, decoded)
        return model, encoder, decoder

    def fit(self, X: np.ndarray, bounds: List[Tuple]):
        self.bounds_ = bounds
        Xp = X
        if self.scaler is not None:
            Xp = self.scaler.fit_transform(Xp)
        self.model, self.encoder, self.decoder = self._build(Xp.shape[1])
        self.model.fit(Xp, Xp, epochs=self.epochs, batch_size=self.batch_size, verbose=0)
        self.fitted_ = True
        return self

    def encode(self, X: np.ndarray) -> np.ndarray:
        assert self.fitted_, 'AutoencoderReducer 未拟合'
        Xp = X
        if self.scaler is not None:
            Xp = self.scaler.transform(Xp)
        z = self.encoder.predict(Xp, verbose=0)
        return z

    def decode(self, Z: np.ndarray) -> np.ndarray:
        assert self.fitted_, 'AutoencoderReducer 未拟合'
        Xp_hat = self.decoder.predict(Z, verbose=0)
        X_hat = self.scaler.inverse_transform(Xp_hat) if self.scaler is not None else Xp_hat
        # 裁剪到边界
        Xc = np.empty_like(X_hat)
        for i, (low, high) in enumerate(self.bounds_):
            Xc[:, i] = np.clip(X_hat[:, i], low, high)
        return Xc


def prepare_autoencoder_reduced_problem(objective_func: Callable,
                                        bounds: List[Tuple],
                                        n_components: int,
                                        initial_samples: int = 500,
                                        sampling_method: str = 'lhs',
                                        scale: bool = True,
                                        epochs: int = 150,
                                        batch_size: int = 64,
                                        pad_ratio: float = 0.10) -> Dict[str, Any]:
    n_dims = len(bounds)
    # 采样
    if sampling_method == 'lhs':
        samples = np.zeros((initial_samples, n_dims))
        for i in range(n_dims):
            samples[:, i] = np.random.permutation(initial_samples) + np.random.uniform(0, 1, initial_samples)
            samples[:, i] = samples[:, i] / initial_samples
        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)
    elif sampling_method == 'random':
        samples = np.random.uniform(0, 1, (initial_samples, n_dims))
        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)
    else:
        raise ValueError('不支持的采样方法')

    reducer = AutoencoderReducer(n_components=n_components, scale=scale, epochs=epochs, batch_size=batch_size)
    reducer.fit(samples, bounds)
    Z = reducer.encode(samples)

    reduced_bounds = []
    for j in range(n_components):
        z_min, z_max = float(np.min(Z[:, j])), float(np.max(Z[:, j]))
        span = z_max - z_min
        pad = max(1e-6, pad_ratio * span)
        reduced_bounds.append((z_min - pad, z_max + pad))

    def reduced_objective(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return float(objective_func(X[0]))

    def expand_to_full(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return X[0]

    return {
        'reduced_objective': reduced_objective,
        'reduced_bounds': reduced_bounds,
        'expand_to_full': expand_to_full,
        'autoencoder': reducer,
        'samples_info': {'X': samples, 'Z': Z}
    }
# 示例：智能降维优化
def complex_black_box(x):
    """8维复杂目标函数示例 - 其中只有3个特征真正重要"""
    important_features = [x[1], x[3], x[6]]  # 真正重要的特征
    noise_features = [x[i] for i in [0, 2, 4, 5, 7]]  # 噪声特征
    return sum(f**2 for f in important_features) + 0.1 * sum(f**2 for f in noise_features)

# 定义搜索空间
bounds = [(-5.0, 5.0) for _ in range(8)]
feature_names = [f'feature_{i}' for i in range(8)]

def main_example():
    # 创建特征选择器和优化器
    optimizer = SimpleEvolutionaryOptimizer(population_size=30, mutation_rate=0.15)
    feature_selector = UniversalFeatureSelector(optimizer, feature_names)
    # 方法1: 累计重要性阈值方法（推荐）
    print("方法1: 累计重要性阈值方法")
    result1 = feature_selector.optimize_with_feature_selection(
        objective_func=complex_black_box,
        bounds=bounds,
        n_calls=200,
        initial_samples=40,
        selection_strategy='composite',
        # 不指定n_features，使用智能降维
        reduction_method='cumulative',
        threshold=0.90,  # 保留90%的重要性
        min_features=2,
        max_features=6
    )

    # 方法2: 肘部法则方法
    print("\n方法2: 肘部法则方法")
    result2 = feature_selector.optimize_with_feature_selection(
        objective_func=complex_black_box,
        bounds=bounds,
        n_calls=200,
        initial_samples=40,
        selection_strategy='composite',
        reduction_method='elbow',
        min_features=2,
        max_features=6
    )

    # 方法3: 显著性特征方法
    print("\n方法3: 显著性特征方法")
    result3 = feature_selector.optimize_with_feature_selection(
        objective_func=complex_black_box,
        bounds=bounds,
        n_calls=200,
        initial_samples=40,
        selection_strategy='composite',
        reduction_method='significant',
        min_features=2,
        max_features=6
    )

    # 可视化特征重要性
    feature_selector.plot_feature_importance()

    # 比较结果
    print("\n=== 结果比较 ===")
    results = [result1, result2, result3]
    methods = ['累计重要性', '肘部法则', '显著性特征']

    for method, result in zip(methods, results):
        reduction_info = result['reduction_info']
        print(f"{method}:")
        print(f"  降维: {reduction_info['original_dims']} -> {reduction_info['reduced_dims']} "
              f"({reduction_info['reduction_ratio']*100:.1f}% 减少)")
        print(f"  最优值: {result['fun']:.6f}")
        print(f"  选定特征: {result['selected_features']}")

if __name__ == "__main__":
    main_example()