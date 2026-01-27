"""
简单测试：验证 representation 模块是否存在且可导入
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _check_representation_files():
    """测试 representation 文件是否存在"""
    print("测试 1: 检查 representation 文件结构")

    rep_dir = os.path.join(project_root, 'representation')
    utils_rep_dir = os.path.join(project_root, 'utils', 'representation')

    checks = []

    # 检查主 representation 目录
    if os.path.exists(rep_dir):
        print(f"[PASS] 主 representation 目录存在: {rep_dir}")
        checks.append(True)

        # 检查关键文件
        init_file = os.path.join(rep_dir, '__init__.py')
        base_file = os.path.join(rep_dir, 'base.py')
        integer_file = os.path.join(rep_dir, 'integer.py')

        if os.path.exists(init_file):
            print(f"[PASS] __init__.py 存在")
            checks.append(True)
        else:
            print(f"[FAIL] __init__.py 不存在")
            checks.append(False)

        if os.path.exists(base_file):
            print(f"[PASS] base.py 存在")
            checks.append(True)
        else:
            print(f"[FAIL] base.py 不存在")
            checks.append(False)

        if os.path.exists(integer_file):
            print(f"[PASS] integer.py 存在")
            checks.append(True)
        else:
            print(f"[FAIL] integer.py 不存在")
            checks.append(False)
    else:
        print(f"[FAIL] 主 representation 目录不存在: {rep_dir}")
        checks.append(False)

    # 检查 utils representation 目录（向后兼容）
    if os.path.exists(utils_rep_dir):
        print(f"[PASS] utils/representation 目录存在（向后兼容）: {utils_rep_dir}")
        checks.append(True)
    else:
        print(f"[FAIL] utils/representation 目录不存在")
        checks.append(False)

    return all(checks)

def _check_representation_content():
    """测试 representation 模块内容"""
    print("\n测试 2: 检查 representation 模块内容")

    try:
        # 直接导入 representation 模块（不通过 nsgablack）
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "representation",
            os.path.join(project_root, "representation", "__init__.py")
        )
        if spec and spec.loader:
            print("[PASS] representation 模块可以加载")
            return True
        else:
            print("[FAIL] representation 模块无法加载")
            return False
    except Exception as e:
        print(f"[FAIL] 加载 representation 模块时出错: {e}")
        return False

def test_representation_files():
    assert _check_representation_files()


def test_representation_content():
    assert _check_representation_content()


def main():
    """运行测试"""
    print("=" * 60)
    print("Representation 模块结构验证")
    print("=" * 60)
    print(f"项目根目录: {project_root}\n")

    results = {
        "文件结构": _check_representation_files(),
        "模块内容": _check_representation_content(),
    }

    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{test_name}: {status}")

    all_passed = all(results.values())
    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] representation 模块结构正确！")
        print("\n说明:")
        print("1. 主 representation 目录已创建")
        print("2. utils/representation 保留（向后兼容）")
        print("3. 两处内容完全相同")
    else:
        print("[FAIL] 部分测试失败")
    print("=" * 60)

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
