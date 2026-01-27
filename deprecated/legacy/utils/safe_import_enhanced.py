"""
改进的导入模块 - 提供安全的、可验证的导入机制

这个模块提供了安全的导入工具，确保导入的是正确的模块
"""

import sys
import os
from typing import Any, Optional, Tuple
import warnings


class SafeImportError(Exception):
    """安全导入失败异常"""
    pass


def verify_module(module: Any, expected_attributes: list, module_name: str) -> bool:
    """
    验证导入的模块是否具有预期的属性

    Args:
        module: 导入的模块对象
        expected_attributes: 期望的属性列表
        module_name: 模块名称（用于错误信息）

    Returns:
        bool: 如果验证通过返回 True

    Raises:
        SafeImportError: 如果验证失败
    """
    missing_attrs = []
    for attr in expected_attributes:
        if not hasattr(module, attr):
            missing_attrs.append(attr)

    if missing_attrs:
        raise SafeImportError(
            f"模块验证失败: {module_name}\n"
            f"缺少属性: {missing_attrs}\n"
            f"模块来源: {getattr(module, '__file__', '未知')}"
        )

    return True


def safe_import_with_fallback(
    import_paths: list,
    expected_attributes: list,
    module_description: str,
    strict: bool = False
) -> Tuple[Any, str]:
    """
    安全导入，支持多个路径回退，并验证模块正确性

    Args:
        import_paths: 导入路径列表，按优先级排序
            每个路径是元组 (module_path, import_type)
            import_type: 'relative', 'absolute', 'path'
        expected_attributes: 期望模块具有的属性列表
        module_description: 模块描述（用于错误信息）
        strict: 是否严格模式（遇到非预期的导入路径时报错）

    Returns:
        Tuple[module, used_path]: 导入的模块和实际使用的路径

    Raises:
        SafeImportError: 如果所有导入路径都失败或验证失败
    """
    last_error = None

    for i, (import_path, import_type) in enumerate(import_paths):
        try:
            if import_type == 'relative':
                # 相对导入
                module = __import__(import_path, fromlist=['*'])
            elif import_type == 'absolute':
                # 绝对导入
                parts = import_path.split('.')
                module = __import__(import_path)
                for part in parts[1:]:
                    module = getattr(module, part)
            elif import_type == 'path':
                # 路径导入（已添加到 sys.path）
                module = __import__(import_path)
            else:
                raise ValueError(f"未知的导入类型: {import_type}")

            # 验证模块
            verify_module(module, expected_attributes, module_description)

            # 获取实际导入来源
            module_file = getattr(module, '__file__', '未知')
            module_origin = getattr(module, '__package__', '未知')

            # 如果不是首选路径，发出警告
            if i > 0:
                warnings.warn(
                    f"{module_description}: 使用了备用导入路径 '{import_path}'\n"
                    f"  首选路径: {import_paths[0][0]}\n"
                    f"  实际来源: {module_file}\n"
                    f"  包名: {module_origin}",
                    ImportWarning,
                    stacklevel=2
                )

            # 严格模式：如果不是首选路径，报错
            if strict and i > 0:
                raise SafeImportError(
                    f"{module_description}: 严格模式下不允许使用备用导入路径\n"
                    f"  首选路径: {import_paths[0][0]}\n"
                    f"  实际使用: {import_path}\n"
                    f"  模块来源: {module_file}"
                )

            return module, import_path

        except (ImportError, AttributeError) as e:
            last_error = e
            continue
        except SafeImportError as e:
            # 验证失败，直接抛出
            raise e
        except Exception as e:
            last_error = e
            continue

    # 所有路径都失败
    error_paths = [path for path, _ in import_paths]
    raise SafeImportError(
        f"{module_description} 导入失败\n"
        f"尝试的路径:\n  " + "\n  ".join(error_paths) + "\n"
        f"期望的属性: {expected_attributes}\n"
        f"最后错误: {last_error}"
    )


def get_import_path_context() -> dict:
    """
    获取当前导入上下文信息

    Returns:
        dict: 包含当前模块、包、sys.path 等信息
    """
    import inspect

    # 获取调用者的信息
    frame = inspect.currentframe().f_back
    module_file = inspect.getfile(frame)
    module_name = frame.f_globals.get('__name__', '__main__')

    return {
        'module_file': module_file,
        'module_name': module_name,
        'sys_path': sys.path.copy(),
        'calling_module': module_name
    }


def log_import_attempt(module_name: str, import_path: str, success: bool, error: Optional[str] = None):
    """
    记录导入尝试（用于调试）

    Args:
        module_name: 要导入的模块名
        import_path: 尝试的导入路径
        success: 是否成功
        error: 错误信息（如果失败）
    """
    context = get_import_path_context()

    log_message = (
        f"[导入尝试] 模块: {module_name}\n"
        f"  路径: {import_path}\n"
        f"  状态: {'成功' if success else '失败'}\n"
        f"  调用模块: {context['calling_module']}\n"
    )

    if error:
        log_message += f"  错误: {error}\n"

    # 这里可以替换为实际的日志系统
    # print(log_message)  # 调试时取消注释
    return log_message
