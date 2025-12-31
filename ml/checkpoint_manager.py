#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查点和状态保存管理工具

提供强大的检查点管理功能，包括：
- 训练状态保存和恢复
- 自动备份机制
- 检查点版本管理
- 增量保存支持
- 异常安全的保存机制
"""

import pickle
import json
import shutil
import threading
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from contextlib import contextmanager
import tempfile
import os


class CheckpointManager:
    """训练检查点管理器

    支持多种检查点策略，确保训练过程的安全性和可恢复性
    """

    def __init__(self,
                 checkpoint_dir: str = "checkpoints",
                 auto_backup: bool = True,
                 backup_count: int = 3,
                 checkpoint_interval: Optional[int] = None,
                 compression: bool = True,
                 hash_verification: bool = True):
        """
        初始化检查点管理器

        Args:
            checkpoint_dir: 检查点保存目录
            auto_backup: 是否自动创建备份
            backup_count: 保留的备份数量
            checkpoint_interval: 自动检查点间隔（None表示手动）
            compression: 是否压缩检查点文件
            hash_verification: 是否启用文件完整性验证
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)

        # 备份目录
        self.backup_dir = self.checkpoint_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)

        # 配置
        self.auto_backup = auto_backup
        self.backup_count = backup_count
        self.checkpoint_interval = checkpoint_interval
        self.compression = compression
        self.hash_verification = hash_verification

        # 状态
        self.latest_checkpoint = None
        self.checkpoint_history = []
        self.checkpoint_counter = 0
        self.auto_checkpoint_counter = 0

        # 线程安全锁
        self._lock = threading.Lock()

        # 自动保存的回调
        self.auto_save_callbacks: List[Callable] = []

        # 加载检查点元数据
        self._load_metadata()

    def _load_metadata(self):
        """加载检查点元数据"""
        metadata_path = self.checkpoint_dir / "checkpoint_metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                self.checkpoint_history = metadata.get('history', [])
                if metadata.get('latest'):
                    self.latest_checkpoint = metadata['latest']
                self.checkpoint_counter = metadata.get('counter', 0)
                self.auto_checkpoint_counter = metadata.get('auto_counter', 0)
            except Exception as e:
                print(f"加载元数据失败: {e}")

    def _save_metadata(self):
        """保存检查点元数据"""
        metadata = {
            'latest': self.latest_checkpoint,
            'history': self.checkpoint_history[-50:],  # 只保留最近50个
            'counter': self.checkpoint_counter,
            'auto_counter': self.auto_checkpoint_counter,
            'last_update': datetime.now().isoformat()
        }

        metadata_path = self.checkpoint_dir / "checkpoint_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def _calculate_hash(self, data: bytes) -> str:
        """计算数据哈希值"""
        return hashlib.sha256(data).hexdigest()

    def _compress_data(self, data: bytes) -> bytes:
        """压缩数据"""
        if self.compression:
            import gzip
            return gzip.compress(data)
        return data

    def _decompress_data(self, data: bytes) -> bytes:
        """解压数据"""
        if self.compression:
            import gzip
            return gzip.decompress(data)
        return data

    @contextmanager
    def _atomic_save(self, filepath: Path):
        """原子性保存上下文管理器"""
        # 创建临时文件
        fd, temp_path = tempfile.mkstemp(dir=filepath.parent)
        os.close(fd)
        temp_path = Path(temp_path)

        try:
            yield temp_path
            # 原子性移动到目标位置
            shutil.move(str(temp_path), str(filepath))
        except Exception:
            # 清理临时文件
            if temp_path.exists():
                temp_path.unlink()
            raise

    def save_checkpoint(self,
                       state: Dict[str, Any],
                       checkpoint_name: Optional[str] = None,
                       metadata: Optional[Dict] = None,
                       force: bool = False) -> str:
        """
        保存训练状态检查点

        Args:
            state: 要保存的状态字典
            checkpoint_name: 检查点名称（可选）
            metadata: 额外的元数据
            force: 是否强制保存（忽略间隔设置）

        Returns:
            保存的检查点路径
        """
        with self._lock:
            # 检查自动保存间隔
            if not force and self.checkpoint_interval is not None:
                self.auto_checkpoint_counter += 1
                if self.auto_checkpoint_counter < self.checkpoint_interval:
                    return ""
                self.auto_checkpoint_counter = 0

            # 生成检查点名称
            if checkpoint_name is None:
                self.checkpoint_counter += 1
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                checkpoint_name = f"checkpoint_{timestamp}_{self.checkpoint_counter}"

            # 准备保存数据
            checkpoint_data = {
                'state': state,
                'metadata': metadata or {},
                'save_time': datetime.now().isoformat(),
                'checkpoint_name': checkpoint_name,
                'counter': self.checkpoint_counter
            }

            # 序列化数据
            serialized_data = pickle.dumps(checkpoint_data)

            # 计算哈希值
            if self.hash_verification:
                data_hash = self._calculate_hash(serialized_data)
                checkpoint_data['hash'] = data_hash

            # 压缩数据
            compressed_data = self._compress_data(serialized_data)

            # 保存主检查点
            checkpoint_path = self.checkpoint_dir / f"{checkpoint_name}.pkl"
            with self._atomic_save(checkpoint_path) as temp_path:
                with open(temp_path, 'wb') as f:
                    f.write(compressed_data)

            # 创建备份
            if self.auto_backup:
                backup_path = self.backup_dir / f"{checkpoint_name}_backup.pkl"
                with self._atomic_save(backup_path) as temp_path:
                    with open(temp_path, 'wb') as f:
                        f.write(compressed_data)

            # 更新检查点信息
            checkpoint_info = {
                'name': checkpoint_name,
                'path': str(checkpoint_path),
                'timestamp': datetime.now().isoformat(),
                'state_size': len(serialized_data),
                'compressed_size': len(compressed_data),
                'compression_ratio': len(compressed_data) / len(serialized_data) if serialized_data else 1,
                'hash': data_hash if self.hash_verification else None
            }

            if metadata:
                checkpoint_info.update(metadata)

            self.latest_checkpoint = checkpoint_info
            self.checkpoint_history.append(checkpoint_info)

            # 保存元数据
            self._save_metadata()

            # 清理旧备份
            if self.auto_backup:
                self._cleanup_old_backups()

            # 触发自动保存回调
            for callback in self.auto_save_callbacks:
                try:
                    callback(checkpoint_info)
                except Exception as e:
                    print(f"自动保存回调失败: {e}")

            print(f"检查点已保存: {checkpoint_name} "
                  f"(大小: {len(serialized_data) / 1024 / 1024:.2f} MB)")

            return str(checkpoint_path)

    def load_checkpoint(self,
                       checkpoint_name: Optional[str] = None,
                       verify_integrity: bool = True) -> Optional[Dict[str, Any]]:
        """
        加载训练状态检查点

        Args:
            checkpoint_name: 检查点名称，如果为None则加载最新检查点
            verify_integrity: 是否验证文件完整性

        Returns:
            加载的状态字典，如果没有找到则返回None
        """
        # 确定要加载的检查点
        checkpoint_path = self._find_checkpoint_path(checkpoint_name)
        if checkpoint_path is None:
            return None

        # 尝试加载主检查点
        try:
            state_data = self._load_checkpoint_file(checkpoint_path, verify_integrity)
            if state_data:
                print(f"成功加载检查点: {checkpoint_path.name}")
                return state_data
        except Exception as e:
            print(f"加载主检查点失败: {e}")

        # 尝试加载备份
        if self.auto_backup:
            backup_path = self.backup_dir / f"{checkpoint_path.stem}_backup.pkl"
            if backup_path.exists():
                try:
                    state_data = self._load_checkpoint_file(backup_path, verify_integrity)
                    if state_data:
                        print(f"从备份加载检查点: {backup_path.name}")
                        return state_data
                except Exception as e:
                    print(f"加载备份也失败: {e}")

        return None

    def _find_checkpoint_path(self, checkpoint_name: Optional[str]) -> Optional[Path]:
        """查找检查点文件路径"""
        if checkpoint_name is None:
            # 加载最新检查点
            if self.latest_checkpoint:
                checkpoint_name = self.latest_checkpoint['name'].replace('.pkl', '')
            else:
                # 查找所有检查点文件
                checkpoint_files = list(self.checkpoint_dir.glob("checkpoint_*.pkl"))
                checkpoint_files.extend(list(self.checkpoint_dir.glob("training_run_*.pkl")))

                if not checkpoint_files:
                    print("没有找到检查点文件")
                    return None

                checkpoint_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                return checkpoint_files[0]

        # 查找指定检查点
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_name}.pkl"
        if checkpoint_path.exists():
            return checkpoint_path

        print(f"检查点文件不存在: {checkpoint_path}")
        return None

    def _load_checkpoint_file(self, filepath: Path, verify_integrity: bool) -> Optional[Dict]:
        """加载检查点文件"""
        with open(filepath, 'rb') as f:
            compressed_data = f.read()

        # 解压数据
        serialized_data = self._decompress_data(compressed_data)

        # 验证完整性
        if verify_integrity and self.hash_verification:
            try:
                checkpoint_data = pickle.loads(serialized_data)
                if 'hash' in checkpoint_data:
                    calculated_hash = self._calculate_hash(serialized_data)
                    if calculated_hash != checkpoint_data['hash']:
                        raise ValueError("文件完整性验证失败")
            except Exception as e:
                raise ValueError(f"数据损坏或格式错误: {e}")

        # 反序列化
        checkpoint_data = pickle.loads(serialized_data)
        return checkpoint_data.get('state', checkpoint_data)

    def list_checkpoints(self, limit: int = 20) -> List[Dict]:
        """
        列出所有可用的检查点

        Args:
            limit: 显示的检查点数量限制

        Returns:
            检查点信息列表
        """
        # 查找所有检查点文件
        checkpoint_files = []
        checkpoint_files.extend(list(self.checkpoint_dir.glob("checkpoint_*.pkl")))
        checkpoint_files.extend(list(self.checkpoint_dir.glob("training_run_*.pkl")))

        # 获取文件信息
        checkpoints = []
        for cp in checkpoint_files:
            try:
                stat = cp.stat()
                checkpoints.append({
                    'name': cp.stem,
                    'path': str(cp),
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime),
                    'is_backup': 'backup' in cp.name
                })
            except Exception:
                continue

        # 按修改时间排序
        checkpoints.sort(key=lambda x: x['modified'], reverse=True)

        # 显示信息
        print("\n=== 可用检查点 ===")
        for i, cp in enumerate(checkpoints[:limit]):
            size_mb = cp['size'] / (1024 * 1024)
            marker = "[备份]" if cp['is_backup'] else ""
            print(f"{i+1:2d}. {cp['name']:40s} "
                  f"{cp['modified'].strftime('%Y-%m-%d %H:%M:%S')} "
                  f"({size_mb:.1f} MB) {marker}")

        return checkpoints[:limit]

    def _cleanup_old_backups(self):
        """清理旧备份文件，只保留最新的几个"""
        backup_files = list(self.backup_dir.glob("*_backup.pkl"))
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        for old_backup in backup_files[self.backup_count:]:
            try:
                old_backup.unlink()
                print(f"删除旧备份: {old_backup.name}")
            except Exception as e:
                print(f"删除备份失败: {e}")

    def delete_checkpoint(self, checkpoint_name: str, delete_backup: bool = True):
        """
        删除指定的检查点

        Args:
            checkpoint_name: 检查点名称
            delete_backup: 是否同时删除备份
        """
        # 删除主检查点
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_name}.pkl"
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            print(f"删除检查点: {checkpoint_name}")

        # 删除备份
        if delete_backup:
            backup_path = self.backup_dir / f"{checkpoint_name}_backup.pkl"
            if backup_path.exists():
                backup_path.unlink()
                print(f"删除备份: {checkpoint_name}_backup")

        # 更新元数据
        self.checkpoint_history = [
            cp for cp in self.checkpoint_history
            if cp['name'] != checkpoint_name
        ]
        if self.latest_checkpoint and self.latest_checkpoint['name'] == checkpoint_name:
            self.latest_checkpoint = None
        self._save_metadata()

    def export_checkpoint(self, checkpoint_name: str, export_path: str):
        """
        导出检查点到指定路径

        Args:
            checkpoint_name: 检查点名称
            export_path: 导出路径
        """
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_name}.pkl"
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"检查点不存在: {checkpoint_name}")

        shutil.copy2(str(checkpoint_path), export_path)
        print(f"检查点已导出到: {export_path}")

    def import_checkpoint(self, import_path: str, checkpoint_name: Optional[str] = None):
        """
        从指定路径导入检查点

        Args:
            import_path: 导入路径
            checkpoint_name: 新的检查点名称（可选）
        """
        if checkpoint_name is None:
            checkpoint_name = Path(import_path).stem

        # 验证检查点文件
        try:
            with open(import_path, 'rb') as f:
                pickle.load(f)
        except Exception as e:
            raise ValueError(f"无效的检查点文件: {e}")

        # 复制到检查点目录
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_name}.pkl"
        shutil.copy2(import_path, checkpoint_path)

        print(f"检查点已导入: {checkpoint_name}")

    def register_auto_save_callback(self, callback: Callable[[Dict], None]):
        """
        注册自动保存回调函数

        Args:
            callback: 回调函数，接受检查点信息作为参数
        """
        self.auto_save_callbacks.append(callback)

    def get_checkpoint_info(self, checkpoint_name: str) -> Optional[Dict]:
        """
        获取检查点详细信息

        Args:
            checkpoint_name: 检查点名称

        Returns:
            检查点信息字典
        """
        for cp in self.checkpoint_history:
            if cp['name'] == checkpoint_name:
                return cp
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取检查点统计信息

        Returns:
            统计信息字典
        """
        checkpoint_files = list(self.checkpoint_dir.glob("*.pkl"))
        backup_files = list(self.backup_dir.glob("*.pkl"))

        total_size = sum(f.stat().st_size for f in checkpoint_files)
        backup_size = sum(f.stat().st_size for f in backup_files)

        return {
            'total_checkpoints': len(checkpoint_files),
            'total_backups': len(backup_files),
            'total_size_mb': total_size / (1024 * 1024),
            'backup_size_mb': backup_size / (1024 * 1024),
            'latest_checkpoint': self.latest_checkpoint,
            'checkpoint_count': self.checkpoint_counter
        }