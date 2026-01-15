"""
项目清理脚本

清理：
1. Python缓存文件（__pycache__, *.pyc）
2. 临时文件（tmpclaude-*）
3. 测试结果文件（*.json.history等）
4. 其他临时文件
"""

import os
import shutil
from pathlib import Path
from typing import List


class ProjectCleaner:
    """项目清理工具"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.cleaned_files = []
        self.cleaned_dirs = []
        self.errors = []

    def clean_pycache(self):
        """清理Python缓存目录"""
        print("\n[1/4] 清理Python缓存...")

        pycache_dirs = list(self.project_root.rglob("__pycache__"))

        for dir_path in pycache_dirs:
            try:
                shutil.rmtree(dir_path)
                self.cleaned_dirs.append(dir_path)
                print(f"  ✓ 删除: {dir_path.relative_to(self.project_root)}")
            except Exception as e:
                self.errors.append(f"删除{dir_path}失败: {e}")

        print(f"  共删除 {len(pycache_dirs)} 个缓存目录")

    def clean_pyc_files(self):
        """清理.pyc文件"""
        print("\n[2/4] 清理.pyc文件...")

        pyc_files = list(self.project_root.rglob("*.pyc"))

        for file_path in pyc_files:
            try:
                file_path.unlink()
                self.cleaned_files.append(file_path)
            except Exception as e:
                self.errors.append(f"删除{file_path}失败: {e}")

        print(f"  共删除 {len(pyc_files)} 个.pyc文件")

    def clean_temp_files(self):
        """清理临时文件"""
        print("\n[3/4] 清理临时文件...")

        # tmpclaude临时文件
        temp_files = list(self.project_root.glob("tmpclaude-*"))

        for file_path in temp_files:
            try:
                file_path.unlink()
                self.cleaned_files.append(file_path)
                print(f"  ✓ 删除: {file_path.name}")
            except Exception as e:
                self.errors.append(f"删除{file_path}失败: {e}")

        print(f"  共删除 {len(temp_files)} 个临时文件")

    def clean_test_results(self):
        """清理测试结果文件（可选）"""
        print("\n[4/4] 清理测试结果文件...")

        # 根目录下的history.json文件
        history_files = [
            self.project_root / "blackbox_DTLZ2函数_(d=12,_objectives=2)_history.json",
            self.project_root / "blackbox_MiniSphere_history.json",
            self.project_root / "blackbox_ZDT1函数_(d=30)_history.json",
            self.project_root / "blackbox_ZDT3函数_(d=30)_history.json",
            self.project_root / "intelligent_blackbox_DTLZ2函数_(d=12,_objectives=2)_history.json",
            self.project_root / "intelligent_blackbox_MiniSphere_history.json",
            self.project_root / "intelligent_blackbox_ZDT1函数_(d=30)_history.json",
            self.project_root / "intelligent_blackbox_ZDT3函数_(d=30)_history.json",
            self.project_root / "sa_bias_evaluation_report.json",
        ]

        for file_path in history_files:
            if file_path.exists():
                try:
                    file_path.unlink()
                    self.cleaned_files.append(file_path)
                    print(f"  ✓ 删除: {file_path.name}")
                except Exception as e:
                    self.errors.append(f"删除{file_path}失败: {e}")

        print(f"  共删除 {sum(1 for f in history_files if f.exists())} 个测试结果文件")

    def clean_all(self, clean_test_results=False):
        """执行所有清理"""
        print("=" * 70)
        print("NSGABlack 项目清理工具")
        print("=" * 70)
        print(f"\n项目目录: {self.project_root}")

        self.clean_pycache()
        self.clean_pyc_files()
        self.clean_temp_files()

        if clean_test_results:
            self.clean_test_results()
        else:
            print("\n[4/4] 跳过测试结果文件（使用--clean-results来清理）")

        self._print_summary()

    def _print_summary(self):
        """打印清理摘要"""
        print("\n" + "=" * 70)
        print("清理完成！")
        print("=" * 70)

        print(f"\n统计:")
        print(f"  删除目录: {len(self.cleaned_dirs)} 个")
        print(f"  删除文件: {len(self.cleaned_files)} 个")

        if self.errors:
            print(f"\n错误: {len(self.errors)} 个")
            for error in self.errors:
                print(f"  - {error}")
        else:
            print("\n✓ 所有文件清理成功！")

        print(f"\n释放空间约: {self._estimate_size()} MB")

    def _estimate_size(self) -> float:
        """估算释放的空间（MB）"""
        total_size = 0

        # 每个__pycache__约1-5MB
        total_size += len(self.cleaned_dirs) * 3

        # 每个pyc约10-100KB
        total_size += len(self.cleaned_files) * 0.05

        # 临时文件很小
        total_size += len([f for f in self.cleaned_files if 'tmpclaude' in str(f)]) * 0.001

        return round(total_size, 2)


def clean_gitkeep_files():
    """创建.gitkeep文件保持空目录结构"""
    print("\n创建.gitkeep文件...")

    directories = [
        "results",
        "results/comparison",
        "results/comparison/visualizations",
        "reports",
    ]

    for dir_path in directories:
        path = Path(dir_path)
        path.mkdir(parents=True, exist_ok=True)

        gitkeep = path / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()
            print(f"  ✓ 创建: {gitkeep}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="清理NSGABlack项目")
    parser.add_argument("--clean-results", action="store_true",
                       help="同时清理测试结果文件")
    parser.add_argument("--gitkeep", action="store_true",
                       help="创建.gitkeep文件")

    args = parser.parse_args()

    # 获取项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # 执行清理
    cleaner = ProjectCleaner(project_root)
    cleaner.clean_all(clean_test_results=args.clean_results)

    # 创建.gitkeep
    if args.gitkeep:
        clean_gitkeep_files()

    print("\n提示: 运行以下命令提交到Git")
    print("  git add .")
    print("  git commit -m 'chore: clean up project files'")
    print("  git push")
