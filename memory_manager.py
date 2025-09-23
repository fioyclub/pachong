#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内存管理工具模块
提供统一的内存管理和OOM预防功能
"""

import os
import gc
import psutil
import asyncio
import logging
from typing import Optional, Callable, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MemoryManager:
    """内存管理器"""
    
    def __init__(self, max_memory_mb: int = 450, check_interval: int = 300):
        self.max_memory_mb = max_memory_mb
        self.check_interval = check_interval
        self.process = psutil.Process()
        self.last_cleanup = datetime.now()
        self.cleanup_callbacks = []
        self._monitoring_task = None
        self._is_monitoring = False
    
    def add_cleanup_callback(self, callback: Callable[[], Any]):
        """添加清理回调函数"""
        self.cleanup_callbacks.append(callback)
    
    def get_memory_usage(self) -> dict:
        """获取当前内存使用情况"""
        memory_info = self.process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        memory_percent = self.process.memory_percent()
        
        return {
            'memory_mb': round(memory_mb, 2),
            'memory_percent': round(memory_percent, 2),
            'max_memory_mb': self.max_memory_mb,
            'usage_ratio': round(memory_mb / self.max_memory_mb, 2),
            'objects_count': len(gc.get_objects())
        }
    
    def is_memory_critical(self) -> bool:
        """检查内存是否达到临界状态"""
        usage = self.get_memory_usage()
        return usage['memory_mb'] > self.max_memory_mb * 0.9
    
    def is_memory_high(self) -> bool:
        """检查内存使用是否过高"""
        usage = self.get_memory_usage()
        return usage['memory_mb'] > self.max_memory_mb * 0.7
    
    async def cleanup_memory(self, force: bool = False) -> dict:
        """执行内存清理"""
        start_usage = self.get_memory_usage()
        
        # 执行自定义清理回调
        for callback in self.cleanup_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"清理回调执行失败: {e}")
        
        # 强制垃圾回收
        collected = gc.collect()
        
        # 更新最后清理时间
        self.last_cleanup = datetime.now()
        
        end_usage = self.get_memory_usage()
        freed_mb = start_usage['memory_mb'] - end_usage['memory_mb']
        
        result = {
            'freed_mb': round(freed_mb, 2),
            'collected_objects': collected,
            'before_mb': start_usage['memory_mb'],
            'after_mb': end_usage['memory_mb'],
            'timestamp': self.last_cleanup.isoformat()
        }
        
        logger.info(f"内存清理完成: 释放 {freed_mb:.2f}MB, 回收 {collected} 个对象")
        return result
    
    async def check_and_cleanup(self) -> Optional[dict]:
        """检查内存并在必要时清理"""
        if self.is_memory_critical():
            logger.warning("内存使用达到临界状态，执行强制清理")
            return await self.cleanup_memory(force=True)
        
        elif self.is_memory_high():
            # 检查是否需要定期清理
            time_since_cleanup = datetime.now() - self.last_cleanup
            if time_since_cleanup > timedelta(seconds=self.check_interval):
                logger.info("内存使用较高，执行定期清理")
                return await self.cleanup_memory()
        
        return None
    
    async def start_monitoring(self):
        """开始内存监控"""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"内存监控已启动，检查间隔: {self.check_interval}秒")
    
    async def stop_monitoring(self):
        """停止内存监控"""
        if not self._is_monitoring:
            return
        
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("内存监控已停止")
    
    async def _monitor_loop(self):
        """内存监控循环"""
        try:
            while self._is_monitoring:
                await self.check_and_cleanup()
                await asyncio.sleep(self.check_interval)
        except asyncio.CancelledError:
            logger.info("内存监控循环被取消")
        except Exception as e:
            logger.error(f"内存监控循环异常: {e}")
    
    def get_status_report(self) -> str:
        """获取内存状态报告"""
        usage = self.get_memory_usage()
        time_since_cleanup = datetime.now() - self.last_cleanup
        
        status = "🟢 正常"
        if usage['memory_mb'] > self.max_memory_mb * 0.9:
            status = "🔴 临界"
        elif usage['memory_mb'] > self.max_memory_mb * 0.7:
            status = "🟡 较高"
        
        return f"""
💾 **内存状态报告**

📊 当前使用: {usage['memory_mb']:.1f}MB / {self.max_memory_mb}MB
📈 使用率: {usage['usage_ratio']*100:.1f}%
🎯 状态: {status}
🧹 对象数: {usage['objects_count']:,}
⏰ 上次清理: {int(time_since_cleanup.total_seconds())}秒前
🔄 监控状态: {'🟢 运行中' if self._is_monitoring else '🔴 已停止'}
"""

# 全局内存管理器实例
_global_memory_manager = None

def get_memory_manager() -> MemoryManager:
    """获取全局内存管理器实例"""
    global _global_memory_manager
    if _global_memory_manager is None:
        max_memory = int(os.getenv('MAX_MEMORY_MB', '450'))
        check_interval = int(os.getenv('MEMORY_CHECK_INTERVAL', '300'))
        _global_memory_manager = MemoryManager(max_memory, check_interval)
    return _global_memory_manager

async def init_global_memory_manager():
    """初始化全局内存管理器"""
    manager = get_memory_manager()
    await manager.start_monitoring()
    logger.info("全局内存管理器已初始化")

async def cleanup_global_memory():
    """清理全局内存"""
    manager = get_memory_manager()
    return await manager.cleanup_memory()

def get_memory_status() -> dict:
    """获取内存状态"""
    manager = get_memory_manager()
    return manager.get_memory_usage()

def get_memory_report() -> str:
    """获取内存报告"""
    manager = get_memory_manager()
    return manager.get_status_report()