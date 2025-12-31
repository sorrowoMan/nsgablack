#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据预处理和特征工程工具

提供全面的数据处理功能，包括：
- 数据清洗和预处理
- 特征选择和工程
- 数据变换和归一化
- 缺失值处理
- 异常值检测和处理
- 特征重要性分析
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Union
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler, PowerTransformer
from sklearn.feature_selection import SelectKBest, SelectPercentile, RFE, RFECV
from sklearn.feature_selection import f_regression, mutual_info_regression
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.impute import SimpleImputer, KNNImputer
import warnings


class DataProcessor:
    """数据预处理器

    统一管理数据预处理流程，支持多种数据变换和特征工程方法
    """

    def __init__(self):
        self.scalers = {}
        self.transformers = {}
        self.feature_selectors = {}
        self.imputers = {}
        self.feature_names = []
        self.target_names = []
        self.processing_history = []

    def fit_scaler(self, X, method: str = 'standard', feature_names: Optional[List[str]] = None):
        """
        拟合数据缩放器

        Args:
            X: 特征数据
            method: 缩放方法 ('standard', 'minmax', 'robust', 'power')
            feature_names: 特征名称列表
        """
        if method == 'standard':
            scaler = StandardScaler()
        elif method == 'minmax':
            scaler = MinMaxScaler()
        elif method == 'robust':
            scaler = RobustScaler()
        elif method == 'power':
            scaler = PowerTransformer(method='yeo-johnson')
        else:
            raise ValueError(f"不支持的缩放方法: {method}")

        scaler.fit(X)
        self.scalers[method] = scaler

        if feature_names is not None:
            self.feature_names = feature_names

        self.processing_history.append({
            'operation': 'fit_scaler',
            'method': method,
            'features': len(X[0]) if hasattr(X[0], '__len__') else 1,
            'timestamp': pd.Timestamp.now().isoformat()
        })

        return scaler

    def transform_scaler(self, X, method: str = 'standard'):
        """
        应用数据缩放

        Args:
            X: 特征数据
            method: 缩放方法

        Returns:
            缩放后的数据
        """
        if method not in self.scalers:
            raise ValueError(f"缩放器尚未拟合: {method}")

        return self.scalers[method].transform(X)

    def inverse_transform_scaler(self, X, method: str = 'standard'):
        """
        反向缩放数据

        Args:
            X: 缩放后的数据
            method: 缩放方法

        Returns:
            原始尺度数据
        """
        if method not in self.scalers:
            raise ValueError(f"缩放器尚未拟合: {method}")

        return self.scalers[method].inverse_transform(X)

    def handle_missing_values(self, X, strategy: str = 'mean', method: str = 'simple'):
        """
        处理缺失值

        Args:
            X: 含缺失值的数据
            strategy: 填充策略 ('mean', 'median', 'most_frequent', 'constant')
            method: 填充方法 ('simple', 'knn')

        Returns:
            填充后的数据
        """
        if method == 'simple':
            imputer = SimpleImputer(strategy=strategy)
        elif method == 'knn':
            imputer = KNNImputer(n_neighbors=5)
        else:
            raise ValueError(f"不支持的填充方法: {method}")

        X_filled = imputer.fit_transform(X)
        self.imputers[method] = imputer

        return X_filled

    def detect_outliers(self, X, method: str = 'isolation', contamination: float = 0.1):
        """
        检测异常值

        Args:
            X: 数据
            method: 检测方法 ('isolation', 'iqr', 'zscore')
            contamination: 异常值比例

        Returns:
            异常值掩码（True为异常值）
        """
        if method == 'isolation':
            clf = IsolationForest(contamination=contamination, random_state=42)
            outlier_mask = clf.fit_predict(X) == -1
        elif method == 'iqr':
            Q1 = np.percentile(X, 25, axis=0)
            Q3 = np.percentile(X, 75, axis=0)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            outlier_mask = np.logical_or(X < lower_bound, X > upper_bound).any(axis=1)
        elif method == 'zscore':
            z_scores = np.abs((X - np.mean(X, axis=0)) / np.std(X, axis=0))
            outlier_mask = (z_scores > 3).any(axis=1)
        else:
            raise ValueError(f"不支持的异常值检测方法: {method}")

        return outlier_mask

    def remove_outliers(self, X, y=None, method: str = 'isolation', contamination: float = 0.1):
        """
        移除异常值

        Args:
            X: 特征数据
            y: 目标数据（可选）
            method: 检测方法
            contamination: 异常值比例

        Returns:
            清理后的数据和标签
        """
        outlier_mask = self.detect_outliers(X, method, contamination)
        X_clean = X[~outlier_mask]
        y_clean = y[~outlier_mask] if y is not None else None

        self.processing_history.append({
            'operation': 'remove_outliers',
            'method': method,
            'removed_count': np.sum(outlier_mask),
            'timestamp': pd.Timestamp.now().isoformat()
        })

        return X_clean, y_clean

    def select_features_univariate(self, X, y, k: int = 10, score_func: str = 'f_regression'):
        """
        单变量特征选择

        Args:
            X: 特征数据
            y: 目标数据
            k: 选择的特征数量
            score_func: 评分函数 ('f_regression', 'mutual_info')

        Returns:
            选择后的数据和选中的特征索引
        """
        if score_func == 'f_regression':
            selector = SelectKBest(score_func=f_regression, k=k)
        elif score_func == 'mutual_info':
            selector = SelectKBest(score_func=mutual_info_regression, k=k)
        else:
            raise ValueError(f"不支持的评分函数: {score_func}")

        X_selected = selector.fit_transform(X, y)
        selected_features = selector.get_support(indices=True)

        self.feature_selectors[f'univariate_{score_func}'] = selector

        return X_selected, selected_features

    def select_features_rfe(self, X, y, estimator=None, n_features_to_select: int = 10):
        """
        递归特征消除

        Args:
            X: 特征数据
            y: 目标数据
            estimator: 估计器（默认使用随机森林）
            n_features_to_select: 选择的特征数量

        Returns:
            选择后的数据和特征排名
        """
        if estimator is None:
            estimator = RandomForestRegressor(n_estimators=100, random_state=42)

        selector = RFE(estimator=estimator, n_features_to_select=n_features_to_select)
        X_selected = selector.fit_transform(X, y)

        self.feature_selectors['rfe'] = selector

        return X_selected, selector.ranking_

    def select_features_percentile(self, X, y, percentile: int = 50):
        """
        基于百分位数的特征选择

        Args:
            X: 特征数据
            y: 目标数据
            percentile: 保留的特征百分位数

        Returns:
            选择后的数据和选中的特征索引
        """
        selector = SelectPercentile(score_func=f_regression, percentile=percentile)
        X_selected = selector.fit_transform(X, y)
        selected_features = selector.get_support(indices=True)

        self.feature_selectors['percentile'] = selector

        return X_selected, selected_features

    def create_polynomial_features(self, X, degree: int = 2, interaction_only: bool = False):
        """
        创建多项式特征

        Args:
            X: 特征数据
            degree: 多项式度数
            interaction_only: 是否仅创建交互项

        Returns:
            多项式特征数据
        """
        from sklearn.preprocessing import PolynomialFeatures

        poly = PolynomialFeatures(degree=degree, interaction_only=interaction_only, include_bias=False)
        X_poly = poly.fit_transform(X)

        self.transformers['polynomial'] = poly

        return X_poly

    def create_interaction_features(self, X, feature_pairs: Optional[List[Tuple[int, int]]] = None):
        """
        创建交互特征

        Args:
            X: 特征数据
            feature_pairs: 特征对列表（可选）

        Returns:
            包含交互特征的数据
        """
        n_features = X.shape[1]

        if feature_pairs is None:
            # 创建所有可能的交互项
            feature_pairs = [(i, j) for i in range(n_features) for j in range(i+1, n_features)]

        interaction_features = []
        for i, j in feature_pairs:
            interaction_features.append((X[:, i] * X[:, j]).reshape(-1, 1))

        if interaction_features:
            X_interaction = np.hstack(interaction_features)
            X_with_interaction = np.hstack([X, X_interaction])
        else:
            X_with_interaction = X

        return X_with_interaction

    def extract_statistical_features(self, X, window_sizes: List[int] = [3, 5]):
        """
        提取统计特征（适用于时序数据）

        Args:
            X: 时序数据
            window_sizes: 滑动窗口大小列表

        Returns:
            统计特征数据
        """
        statistical_features = []

        for window_size in window_sizes:
            if len(X.shape) == 1:
                X_reshaped = X.reshape(-1, 1)
            else:
                X_reshaped = X

            for i in range(X_reshaped.shape[1]):
                series = X_reshaped[:, i]

                # 滑动窗口统计
                for ws in window_sizes:
                    if len(series) >= ws:
                        # 移动平均
                        ma = pd.Series(series).rolling(window=ws).mean().fillna(0).values
                        statistical_features.append(ma.reshape(-1, 1))

                        # 移动标准差
                        ms = pd.Series(series).rolling(window=ws).std().fillna(0).values
                        statistical_features.append(ms.reshape(-1, 1))

        if statistical_features:
            X_statistical = np.hstack(statistical_features)
            X_with_stats = np.hstack([X, X_statistical])
        else:
            X_with_stats = X

        return X_with_stats

    def reduce_dimensionality_pca(self, X, n_components: int = 2, variance_ratio: float = 0.95):
        """
        PCA降维

        Args:
            X: 特征数据
            n_components: 降维后的维度
            variance_ratio: 保留的方差比例

        Returns:
            降维后的数据和PCA对象
        """
        if variance_ratio < 1.0:
            pca = PCA(n_components=variance_ratio, svd_solver='full')
        else:
            pca = PCA(n_components=n_components)

        X_pca = pca.fit_transform(X)

        self.transformers['pca'] = pca

        return X_pca, pca

    def calculate_feature_importance(self, X, y, method: str = 'rf'):
        """
        计算特征重要性

        Args:
            X: 特征数据
            y: 目标数据
            method: 计算方法 ('rf', 'mutual_info', 'correlation')

        Returns:
            特征重要性分数
        """
        if method == 'rf':
            rf = RandomForestRegressor(n_estimators=100, random_state=42)
            rf.fit(X, y)
            importance = rf.feature_importances_
        elif method == 'mutual_info':
            importance = mutual_info_regression(X, y)
        elif method == 'correlation':
            importance = np.abs(np.corrcoef(X.T, y.T)[-1, :-1])
        else:
            raise ValueError(f"不支持的特征重要性计算方法: {method}")

        return importance

    def get_processing_summary(self) -> pd.DataFrame:
        """
        获取数据处理历史摘要

        Returns:
            处理历史DataFrame
        """
        return pd.DataFrame(self.processing_history)

    def save_processor(self, filepath: str):
        """
        保存数据处理器状态

        Args:
            filepath: 保存路径
        """
        import pickle

        processor_state = {
            'scalers': self.scalers,
            'transformers': self.transformers,
            'feature_selectors': self.feature_selectors,
            'imputers': self.imputers,
            'feature_names': self.feature_names,
            'target_names': self.target_names,
            'processing_history': self.processing_history
        }

        with open(filepath, 'wb') as f:
            pickle.dump(processor_state, f)

    def load_processor(self, filepath: str):
        """
        加载数据处理器状态

        Args:
            filepath: 加载路径
        """
        import pickle

        with open(filepath, 'rb') as f:
            processor_state = pickle.load(f)

        self.scalers = processor_state['scalers']
        self.transformers = processor_state['transformers']
        self.feature_selectors = processor_state['feature_selectors']
        self.imputers = processor_state['imputers']
        self.feature_names = processor_state['feature_names']
        self.target_names = processor_state['target_names']
        self.processing_history = processor_state['processing_history']


class FeatureEngineer:
    """特征工程器

    专门负责特征创建和变换的高级功能
    """

    def __init__(self):
        self.feature_transformations = {}
        self.created_features = []

    def create_ratio_features(self, X, feature_pairs: List[Tuple[int, int]]):
        """
        创建比率特征

        Args:
            X: 特征数据
            feature_pairs: 特征对列表，表示要计算比率的特征索引

        Returns:
            包含比率特征的数据
        """
        ratio_features = []
        feature_names = []

        for i, j in feature_pairs:
            # 避免除零错误
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ratio = np.divide(X[:, i], X[:, j],
                                 out=np.zeros_like(X[:, i]),
                                 where=X[:, j] != 0)
            ratio_features.append(ratio.reshape(-1, 1))
            feature_names.append(f"feature_{i}_ratio_{j}")

        if ratio_features:
            X_ratios = np.hstack(ratio_features)
            X_with_ratios = np.hstack([X, X_ratios])
            self.created_features.extend(feature_names)
        else:
            X_with_ratios = X

        return X_with_ratios

    def create_difference_features(self, X, feature_pairs: List[Tuple[int, int]]):
        """
        创建差值特征

        Args:
            X: 特征数据
            feature_pairs: 特征对列表

        Returns:
            包含差值特征的数据
        """
        diff_features = []
        feature_names = []

        for i, j in feature_pairs:
            diff = X[:, i] - X[:, j]
            diff_features.append(diff.reshape(-1, 1))
            feature_names.append(f"feature_{i}_diff_{j}")

        if diff_features:
            X_diffs = np.hstack(diff_features)
            X_with_diffs = np.hstack([X, X_diffs])
            self.created_features.extend(feature_names)
        else:
            X_with_diffs = X

        return X_with_diffs

    def create_bin_features(self, X, feature_indices: List[int], n_bins: int = 5):
        """
        创建分箱特征

        Args:
            X: 特征数据
            feature_indices: 要分箱的特征索引
            n_bins: 分箱数量

        Returns:
            包含分箱特征的数据
        """
        bin_features = []
        feature_names = []

        for idx in feature_indices:
            # 使用等频分箱
            _, bin_edges = pd.cut(X[:, idx], bins=n_bins, retbins=True, labels=False, duplicates='drop')
            bin_features.append(bin_edges[X[:, idx]].reshape(-1, 1))
            feature_names.append(f"feature_{idx}_binned")

        if bin_features:
            X_binned = np.hstack(bin_features)
            X_with_bins = np.hstack([X, X_binned])
            self.created_features.extend(feature_names)
        else:
            X_with_bins = X

        return X_with_bins

    def create_log_features(self, X, feature_indices: List[int], offset: float = 1e-6):
        """
        创建对数变换特征

        Args:
            X: 特征数据
            feature_indices: 要变换的特征索引
            offset: 偏移量（避免log(0)）

        Returns:
            包含对数特征的数据
        """
        log_features = []
        feature_names = []

        for idx in feature_indices:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                log_feat = np.log(X[:, idx] + offset)
            log_features.append(log_feat.reshape(-1, 1))
            feature_names.append(f"feature_{idx}_log")

        if log_features:
            X_logs = np.hstack(log_features)
            X_with_logs = np.hstack([X, X_logs])
            self.created_features.extend(feature_names)
        else:
            X_with_logs = X

        return X_with_logs

    def get_created_feature_names(self) -> List[str]:
        """
        获取创建的特征名称列表

        Returns:
            特征名称列表
        """
        return self.created_features.copy()