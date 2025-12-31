#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模型评估和可视化工具

提供全面的模型评估和可视化功能，包括：
- 性能指标计算
- 学习曲线分析
- 残差分析
- 特征重要性可视化
- 模型比较
- 预测结果可视化
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple, Optional, Any, Union
from sklearn.metrics import (mean_squared_error, r2_score, mean_absolute_error,
                           mean_absolute_percentage_error, explained_variance_score)
from sklearn.model_selection import learning_curve, validation_curve
from sklearn.inspection import permutation_importance
import warnings


# 设置中文字体和样式
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")


class ModelEvaluator:
    """模型评估器

    提供全面的模型性能评估和可视化功能
    """

    def __init__(self, figsize: Tuple[int, int] = (10, 6)):
        """
        初始化模型评估器

        Args:
            figsize: 图形大小
        """
        self.figsize = figsize
        self.evaluation_results = {}
        self.comparison_results = {}

    def calculate_metrics(self, y_true, y_pred, metrics: Optional[List[str]] = None) -> Dict[str, float]:
        """
        计算各种评估指标

        Args:
            y_true: 真实值
            y_pred: 预测值
            metrics: 要计算的指标列表

        Returns:
            指标字典
        """
        if metrics is None:
            metrics = ['mse', 'rmse', 'mae', 'mape', 'r2', 'explained_variance']

        result = {}

        if 'mse' in metrics:
            result['mse'] = mean_squared_error(y_true, y_pred)

        if 'rmse' in metrics:
            result['rmse'] = np.sqrt(mean_squared_error(y_true, y_pred))

        if 'mae' in metrics:
            result['mae'] = mean_absolute_error(y_true, y_pred)

        if 'mape' in metrics:
            # 避免除零错误
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result['mape'] = mean_absolute_percentage_error(y_true, y_pred)

        if 'r2' in metrics:
            result['r2'] = r2_score(y_true, y_pred)

        if 'explained_variance' in metrics:
            result['explained_variance'] = explained_variance_score(y_true, y_pred)

        # 额外的自定义指标
        if 'max_error' in metrics:
            result['max_error'] = np.max(np.abs(y_true - y_pred))

        if 'mean_error' in metrics:
            result['mean_error'] = np.mean(y_true - y_pred)

        if 'std_error' in metrics:
            result['std_error'] = np.std(y_true - y_pred)

        return result

    def plot_prediction_vs_actual(self, y_true, y_pred, model_name: str = "Model",
                                 save_path: Optional[str] = None):
        """
        绘制预测值与真实值对比图

        Args:
            y_true: 真实值
            y_pred: 预测值
            model_name: 模型名称
            save_path: 保存路径
        """
        plt.figure(figsize=self.figsize)

        # 散点图
        plt.scatter(y_true, y_pred, alpha=0.6, s=30, label='预测点')

        # 理想预测线
        min_val = min(np.min(y_true), np.min(y_pred))
        max_val = max(np.max(y_true), np.max(y_pred))
        plt.plot([min_val, max_val], [min_val, max_val], 'r--', lw=2, label='理想预测')

        # 计算R²
        r2 = r2_score(y_true, y_pred)

        plt.xlabel('真实值')
        plt.ylabel('预测值')
        plt.title(f'{model_name} - 预测值 vs 真实值 (R² = {r2:.4f})')
        plt.legend()
        plt.grid(True, alpha=0.3)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

    def plot_residuals(self, y_true, y_pred, model_name: str = "Model",
                      save_path: Optional[str] = None):
        """
        绘制残差图

        Args:
            y_true: 真实值
            y_pred: 预测值
            model_name: 模型名称
            save_path: 保存路径
        """
        residuals = y_true - y_pred

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))

        # 残差 vs 预测值
        ax1.scatter(y_pred, residuals, alpha=0.6)
        ax1.axhline(y=0, color='r', linestyle='--')
        ax1.set_xlabel('预测值')
        ax1.set_ylabel('残差')
        ax1.set_title(f'{model_name} - 残差 vs 预测值')
        ax1.grid(True, alpha=0.3)

        # 残差直方图
        ax2.hist(residuals, bins=30, alpha=0.7, edgecolor='black')
        ax2.set_xlabel('残差')
        ax2.set_ylabel('频数')
        ax2.set_title(f'{model_name} - 残差分布')
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

    def plot_learning_curve(self, estimator, X, y, cv: int = 5,
                           train_sizes: Optional[np.ndarray] = None,
                           model_name: str = "Model", save_path: Optional[str] = None):
        """
        绘制学习曲线

        Args:
            estimator: 评估器
            X: 特征数据
            y: 目标数据
            cv: 交叉验证折数
            train_sizes: 训练集大小
            model_name: 模型名称
            save_path: 保存路径
        """
        if train_sizes is None:
            train_sizes = np.linspace(0.1, 1.0, 10)

        train_sizes, train_scores, val_scores = learning_curve(
            estimator, X, y, cv=cv, train_sizes=train_sizes,
            scoring='neg_mean_squared_error', n_jobs=-1
        )

        # 转换为RMSE
        train_rmse = np.sqrt(-train_scores)
        val_rmse = np.sqrt(-val_scores)

        plt.figure(figsize=self.figsize)

        plt.plot(train_sizes, np.mean(train_rmse, axis=1), 'o-', color='blue',
                label='训练集')
        plt.plot(train_sizes, np.mean(val_rmse, axis=1), 'o-', color='red',
                label='验证集')

        plt.fill_between(train_sizes,
                        np.mean(train_rmse, axis=1) - np.std(train_rmse, axis=1),
                        np.mean(train_rmse, axis=1) + np.std(train_rmse, axis=1),
                        alpha=0.1, color='blue')
        plt.fill_between(train_sizes,
                        np.mean(val_rmse, axis=1) - np.std(val_rmse, axis=1),
                        np.mean(val_rmse, axis=1) + np.std(val_rmse, axis=1),
                        alpha=0.1, color='red')

        plt.xlabel('训练样本数')
        plt.ylabel('RMSE')
        plt.title(f'{model_name} - 学习曲线')
        plt.legend()
        plt.grid(True, alpha=0.3)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

    def plot_validation_curve(self, estimator, X, y, param_name: str,
                             param_range: List, cv: int = 5,
                             model_name: str = "Model", save_path: Optional[str] = None):
        """
        绘制验证曲线

        Args:
            estimator: 评估器
            X: 特征数据
            y: 目标数据
            param_name: 参数名称
            param_range: 参数范围
            cv: 交叉验证折数
            model_name: 模型名称
            save_path: 保存路径
        """
        train_scores, val_scores = validation_curve(
            estimator, X, y, param_name=param_name, param_range=param_range,
            cv=cv, scoring='neg_mean_squared_error', n_jobs=-1
        )

        # 转换为R²
        train_scores = -train_scores
        val_scores = -val_scores

        plt.figure(figsize=self.figsize)

        plt.plot(param_range, np.mean(train_scores, axis=1), 'o-', color='blue',
                label='训练集')
        plt.plot(param_range, np.mean(val_scores, axis=1), 'o-', color='red',
                label='验证集')

        plt.fill_between(param_range,
                        np.mean(train_scores, axis=1) - np.std(train_scores, axis=1),
                        np.mean(train_scores, axis=1) + np.std(train_scores, axis=1),
                        alpha=0.1, color='blue')
        plt.fill_between(param_range,
                        np.mean(val_scores, axis=1) - np.std(val_scores, axis=1),
                        np.mean(val_scores, axis=1) + np.std(val_scores, axis=1),
                        alpha=0.1, color='red')

        plt.xlabel(param_name)
        plt.ylabel('MSE')
        plt.title(f'{model_name} - 验证曲线 ({param_name})')
        plt.legend()
        plt.grid(True, alpha=0.3)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

    def plot_feature_importance(self, importance_scores, feature_names: Optional[List[str]] = None,
                               top_n: int = 20, model_name: str = "Model",
                               save_path: Optional[str] = None):
        """
        绘制特征重要性图

        Args:
            importance_scores: 重要性分数
            feature_names: 特征名称
            top_n: 显示前N个重要特征
            model_name: 模型名称
            save_path: 保存路径
        """
        if feature_names is None:
            feature_names = [f'Feature_{i}' for i in range(len(importance_scores))]

        # 创建DataFrame并排序
        feature_importance = pd.DataFrame({
            'feature': feature_names,
            'importance': importance_scores
        }).sort_values('importance', ascending=False)

        # 选择前N个特征
        top_features = feature_importance.head(top_n)

        plt.figure(figsize=(10, max(6, top_n * 0.3)))

        sns.barplot(data=top_features, x='importance', y='feature', palette='viridis')
        plt.xlabel('重要性分数')
        plt.ylabel('特征名称')
        plt.title(f'{model_name} - 特征重要性 (Top {top_n})')
        plt.grid(True, alpha=0.3)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

    def compare_models(self, model_results: Dict[str, Dict],
                       metrics: List[str] = ['r2', 'rmse', 'mae'],
                       save_path: Optional[str] = None):
        """
        比较多个模型的性能

        Args:
            model_results: 模型结果字典 {model_name: {metric: value}}
            metrics: 要比较的指标
            save_path: 保存路径
        """
        # 创建比较DataFrame
        comparison_df = pd.DataFrame(model_results).T
        comparison_df = comparison_df[metrics]

        # 绘制比较图
        fig, axes = plt.subplots(1, len(metrics), figsize=(5 * len(metrics), 6))
        if len(metrics) == 1:
            axes = [axes]

        for i, metric in enumerate(metrics):
            comparison_df[metric].plot(kind='bar', ax=axes[i], color='skyblue')
            axes[i].set_title(f'{metric.upper()} 比较')
            axes[i].set_ylabel(metric.upper())
            axes[i].tick_params(axis='x', rotation=45)
            axes[i].grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

        # 保存比较结果
        self.comparison_results = comparison_df.to_dict()
        return comparison_df

    def plot_prediction_distribution(self, y_true, y_pred, model_name: str = "Model",
                                   save_path: Optional[str] = None):
        """
        绘制预测值分布图

        Args:
            y_true: 真实值
            y_pred: 预测值
            model_name: 模型名称
            save_path: 保存路径
        """
        plt.figure(figsize=self.figsize)

        # 绘制分布
        sns.kdeplot(y_true, label='真实值', shade=True, alpha=0.5)
        sns.kdeplot(y_pred, label='预测值', shade=True, alpha=0.5)

        plt.xlabel('值')
        plt.ylabel('密度')
        plt.title(f'{model_name} - 预测值分布 vs 真实值分布')
        plt.legend()
        plt.grid(True, alpha=0.3)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

    def plot_error_by_value_range(self, y_true, y_pred, bins: int = 10,
                                 model_name: str = "Model", save_path: Optional[str] = None):
        """
        按值范围分析误差

        Args:
            y_true: 真实值
            y_pred: 预测值
            bins: 分箱数量
            model_name: 模型名称
            save_path: 保存路径
        """
        # 计算绝对误差
        abs_errors = np.abs(y_true - y_pred)

        # 分箱
        y_bins = pd.cut(y_true, bins=bins)
        error_by_bin = pd.DataFrame({
            'y_true': y_true,
            'abs_error': abs_errors
        }).groupby(y_bins).agg({
            'y_true': 'mean',
            'abs_error': ['mean', 'std', 'count']
        }).reset_index()

        plt.figure(figsize=self.figsize)

        # 绘制误差随值的变化
        plt.errorbar(error_by_bin[('y_true', 'mean')],
                    error_by_bin[('abs_error', 'mean')],
                    yerr=error_by_bin[('abs_error', 'std')],
                    fmt='o-', capsize=5, capthick=2)

        plt.xlabel('真实值（平均值）')
        plt.ylabel('绝对误差（平均值）')
        plt.title(f'{model_name} - 误差随值范围的变化')
        plt.grid(True, alpha=0.3)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

    def generate_evaluation_report(self, y_true, y_pred, model_name: str = "Model",
                                  feature_names: Optional[List[str]] = None,
                                  feature_importance: Optional[np.ndarray] = None) -> Dict:
        """
        生成完整的评估报告

        Args:
            y_true: 真实值
            y_pred: 预测值
            model_name: 模型名称
            feature_names: 特征名称
            feature_importance: 特征重要性

        Returns:
            评估报告字典
        """
        # 计算指标
        metrics = self.calculate_metrics(y_true, y_pred)

        # 创建报告
        report = {
            'model_name': model_name,
            'metrics': metrics,
            'sample_count': len(y_true),
            'evaluation_time': pd.Timestamp.now().isoformat()
        }

        # 添加特征重要性信息
        if feature_importance is not None and feature_names is not None:
            feature_imp_df = pd.DataFrame({
                'feature': feature_names,
                'importance': feature_importance
            }).sort_values('importance', ascending=False)

            report['feature_importance'] = feature_imp_df.to_dict('records')
            report['top_features'] = feature_imp_df.head(10)['feature'].tolist()

        # 保存评估结果
        self.evaluation_results[model_name] = report

        return report

    def export_report_to_html(self, report: Dict, save_path: str):
        """
        将评估报告导出为HTML

        Args:
            report: 评估报告
            save_path: 保存路径
        """
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>模型评估报告 - {report['model_name']}</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                h2 {{ color: #666; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .metric {{ margin: 10px 0; }}
            </style>
        </head>
        <body>
            <h1>模型评估报告</h1>
            <h2>{report['model_name']}</h2>

            <h3>基本信息</h3>
            <div class="metric">评估时间: {report['evaluation_time']}</div>
            <div class="metric">样本数量: {report['sample_count']:,}</div>

            <h3>性能指标</h3>
            <table>
                <tr><th>指标</th><th>值</th></tr>
        """

        for metric, value in report['metrics'].items():
            html_content += f"<tr><td>{metric.upper()}</td><td>{value:.4f}</td></tr>"

        if 'feature_importance' in report:
            html_content += """
            </table>
            <h3>特征重要性 (Top 10)</h3>
            <table>
                <tr><th>特征名称</th><th>重要性</th></tr>
            """
            for feat in report['feature_importance'][:10]:
                html_content += f"<tr><td>{feat['feature']}</td><td>{feat['importance']:.4f}</td></tr>"

        html_content += """
            </table>
        </body>
        </html>
        """

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"评估报告已保存到: {save_path}")

    def plot_correlation_heatmap(self, X, feature_names: Optional[List[str]] = None,
                               save_path: Optional[str] = None):
        """
        绘制特征相关性热图

        Args:
            X: 特征数据
            feature_names: 特征名称
            save_path: 保存路径
        """
        if feature_names is None:
            feature_names = [f'Feature_{i}' for i in range(X.shape[1])]

        # 计算相关性矩阵
        corr_matrix = np.corrcoef(X.T)
        corr_df = pd.DataFrame(corr_matrix, index=feature_names, columns=feature_names)

        plt.figure(figsize=(12, 10))

        sns.heatmap(corr_df, annot=True, cmap='coolwarm', center=0,
                   square=True, fmt='.2f', cbar_kws={'label': '相关系数'})

        plt.title('特征相关性热图')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()