"""
NSGABlack多智能体优化系统

一个基于偏置驱动的协同进化框架
"""

# 核心组件
from .core.role import (
    AgentRole,
    RoleRegistry,
    RoleCharacteristics,
    get_role_description,
    suggest_role_config
)

# 版本信息
__version__ = '1.0.0'
__author__ = 'NSGABlack Team'

# 导出的公共接口
__all__ = [
    # 核心类
    'AgentRole',
    'RoleRegistry',
    'RoleCharacteristics',
    'get_role_description',
    'suggest_role_config',
]

# 快速创建函数
def create_multi_agent_optimizer(problem, config=None):
    """
    快速创建多智能体优化器的便捷函数

    Args:
        problem: 优化问题实例
        config: 配置字典

    Returns:
        MultiAgentOptimizer: 配置好的优化器实例
    """
    return MultiAgentOptimizer(problem, config)

def get_available_roles():
    """获取所有可用的智能体角色"""
    return list(AgentRole)

def get_default_config():
    """获取默认配置"""
    return {
        'total_population': 200,
        'max_generations': 100,
        'communication_interval': 5,
        'adaptation_interval': 20,
        'agent_config': {
            AgentRole.EXPLORER: {
                'ratio': 0.25,
                'bias_profile': 'default_explorer'
            },
            AgentRole.EXPLOITER: {
                'ratio': 0.35,
                'bias_profile': 'default_exploiter'
            },
            AgentRole.WAITER: {
                'ratio': 0.15,
                'bias_profile': 'default_waiter'
            },
            AgentRole.ADVISOR: {
                'ratio': 0.15,
                'bias_profile': 'default_advisor'
            },
            AgentRole.COORDINATOR: {
                'ratio': 0.10,
                'bias_profile': 'default_coordinator'
            }
        },
        'bias_system': {
            'enabled': True,
            'dynamic_adjustment': True,
            'learning_enabled': True
        },
        'communication': {
            'enabled': True,
            'knowledge_sharing': True,
            'elite_migration': True
        },
        'visualization': {
            'enabled': True,
            'real_time': False,
            'save_plots': True
        },
        'advisory': {
            'method': 'statistical',  # 'statistical', 'bayesian', 'ml'
            'update_interval': 5
        }
    }