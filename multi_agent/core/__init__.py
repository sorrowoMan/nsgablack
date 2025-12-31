"""
多智能体核心模块
"""

from .role import (
    AgentRole,
    RoleRegistry,
    RoleCharacteristics,
    get_role_description,
    suggest_role_config
)

__all__ = [
    'AgentRole',
    'RoleRegistry',
    'RoleCharacteristics',
    'get_role_description',
    'suggest_role_config',
]