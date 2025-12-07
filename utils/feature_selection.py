import numpy as np
from typing import Callable, List, Dict, Tuple
from sklearn.feature_selection import mutual_info_regression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import warnings


class UniversalFeatureSelector:
    """通用特征选择器 - 支持智能降维"""

    def __init__(self, feature_names: List[str] = None):
        self.feature_names = feature_names
        self.scaler = StandardScaler()
        self.feature_importance_ = None
        self.selected_features_ = None
        self.history_ = {}
        self.reduction_info_ = {}

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
            results['mutual_info'] = self._mutual_info_analysis(X, y)
        if 'random_forest' in methods:
            results['random_forest'] = self._random_forest_analysis(X, y)
        if 'correlation' in methods:
            results['correlation'] = self._correlation_analysis(X, y)
        if 'variance' in methods:
            results['variance'] = self._variance_analysis(X)

        self.history_['feature_analysis'] = results
        return results

    def smart_feature_selection(self, X: np.ndarray, y: np.ndarray,
                               strategy: str = 'composite',
                               reduction_method: str = 'cumulative',
                               threshold: float = 0.95,
                               min_features: int = 1,
                               max_features: int = None) -> List[int]:
        """智能特征选择 - 自动确定降维维度"""
        n_dims = X.shape[1]
        if max_features is None:
            max_features = n_dims

        analysis_results = self.analyze_features(X, y)
        composite_scores = self._compute_composite_scores(analysis_results)

        if reduction_method == 'cumulative':
            n_selected = self._cumulative_threshold_selection(composite_scores, threshold, min_features, max_features)
        elif reduction_method == 'elbow':
            n_selected = self._elbow_method_selection(composite_scores, min_features, max_features)
        elif reduction_method == 'significant':
            n_selected = self._significant_feature_selection(composite_scores, min_features, max_features)
        else:
            raise ValueError(f"不支持的降维方法: {reduction_method}")

        selected = self._top_k_selection(composite_scores, n_selected)
        self.selected_features_ = selected

        self.reduction_info_ = {
            'original_dims': n_dims,
            'reduced_dims': n_selected,
            'reduction_ratio': 1 - n_selected / n_dims,
            'method': reduction_method,
            'composite_scores': composite_scores
        }

        return selected

    def select_features(self, X: np.ndarray, y: np.ndarray,
                       strategy: str = 'composite',
                       n_features: int = None,
                       **kwargs) -> List[int]:
        """特征选择主函数"""
        if n_features is not None:
            return self._fixed_dimension_selection(X, y, strategy, n_features)
        else:
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
        """创建降维后的优化问题"""
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
        """创建降维问题与映射函数"""
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
                               **smart_selection_kwargs) -> Dict:
        """一站式导出降维优化问题"""
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

    def _compute_composite_scores(self, analysis_results: Dict) -> np.ndarray:
        """计算综合特征评分"""
        n_dims = len(next(iter(analysis_results.values())))
        composite_scores = np.zeros(n_dims)

        weights = {
            'mutual_info': 1.5,
            'random_forest': 1.2,
            'correlation': 1.0,
            'variance': 0.8
        }

        for method, scores in analysis_results.items():
            weight = weights.get(method, 1.0)
            composite_scores += weight * scores

        if np.max(composite_scores) > 0:
            composite_scores /= np.max(composite_scores)

        self.feature_importance_ = composite_scores
        return composite_scores

    def _cumulative_threshold_selection(self, scores: np.ndarray, threshold: float,
                                      min_features: int, max_features: int) -> int:
        """累计重要性阈值方法"""
        sorted_scores = np.sort(scores)[::-1]
        cumulative_scores = np.cumsum(sorted_scores)
        total_importance = cumulative_scores[-1]

        n_selected = np.argmax(cumulative_scores >= threshold * total_importance) + 1
        n_selected = max(min_features, min(n_selected, max_features))
        return n_selected

    def _elbow_method_selection(self, scores: np.ndarray,
                              min_features: int, max_features: int) -> int:
        """肘部法则选择"""
        sorted_scores = np.sort(scores)[::-1]
        n_features_range = range(1, len(scores) + 1)

        cumulative_importance = [np.sum(sorted_scores[:k]) for k in n_features_range]
        first_diff = np.diff(cumulative_importance)
        second_diff = np.diff(first_diff)

        if len(second_diff) > 0:
            elbow_point = np.argmin(second_diff) + 2
        else:
            elbow_point = len(scores) // 2

        n_selected = max(min_features, min(elbow_point, max_features))
        return n_selected

    def _significant_feature_selection(self, scores: np.ndarray,
                                    min_features: int, max_features: int) -> int:
        """显著性特征选择"""
        mean_score = np.mean(scores)
        std_score = np.std(scores)

        significant_mask = scores > (mean_score + 0.5 * std_score)
        n_selected = max(min_features, min(np.sum(significant_mask), max_features))
        return n_selected

    def _latin_hypercube_sampling(self, n_dims: int, n_samples: int,
                                bounds: List[Tuple]) -> np.ndarray:
        """拉丁超立方采样"""
        samples = np.zeros((n_samples, n_dims))
        for i in range(n_dims):
            samples[:, i] = np.random.permutation(n_samples) + np.random.uniform(0, 1, n_samples)
            samples[:, i] = samples[:, i] / n_samples

        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)

        return samples

    def _random_sampling(self, n_dims: int, n_samples: int,
                       bounds: List[Tuple]) -> np.ndarray:
        """随机采样"""
        samples = np.random.uniform(0, 1, (n_samples, n_dims))

        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)

        return samples

    def _mutual_info_analysis(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """互信息分析"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mi_scores = mutual_info_regression(X, y, random_state=42)
        return mi_scores / (np.max(mi_scores) + 1e-10)

    def _random_forest_analysis(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """随机森林特征重要性"""
        rf = RandomForestRegressor(n_estimators=100, random_state=42)
        rf.fit(X, y)
        importance = rf.feature_importances_
        return importance / (np.max(importance) + 1e-10)

    def _correlation_analysis(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """相关性分析"""
        corr_scores = np.array([np.abs(np.corrcoef(X[:, i], y)[0, 1])
                              for i in range(X.shape[1])])
        corr_scores = np.nan_to_num(corr_scores, nan=0.0)
        return corr_scores / (np.max(corr_scores) + 1e-10)

    def _variance_analysis(self, X: np.ndarray) -> np.ndarray:
        """方差分析"""
        variances = np.var(X, axis=0)
        return variances / (np.max(variances) + 1e-10)

    def _top_k_selection(self, scores: np.ndarray, n_features: int) -> List[int]:
        """选择Top-K特征"""
        return np.argsort(scores)[-n_features:].tolist()
