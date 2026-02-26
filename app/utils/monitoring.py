"""
性能监控和健康检查工具
"""
import asyncio
import logging
import psutil
import time
from datetime import datetime
from typing import Optional

from app.utils.concurrency import db_semaphore, message_rate_limiter, price_parse_rate_limiter

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self.start_time = time.time()
        self.message_count = 0
        self.error_count = 0
        self.last_message_time: Optional[float] = None
        self.message_times: list = []
        self.lock = asyncio.Lock()
        self._monitoring_task: Optional[asyncio.Task] = None

    async def record_message(self):
        """记录消息"""
        async with self.lock:
            self.message_count += 1
            now = time.time()
            self.last_message_time = now
            self.message_times.append(now)
            # 只保留最近1000条消息的时间戳
            if len(self.message_times) > 1000:
                self.message_times = self.message_times[-1000:]

    async def record_error(self):
        """记录错误"""
        async with self.lock:
            self.error_count += 1

    def get_message_rate(self, window_seconds: int = 60) -> float:
        """获取消息速率（每秒）"""
        now = time.time()
        cutoff = now - window_seconds
        recent = [t for t in self.message_times if t > cutoff]
        return len(recent) / window_seconds if window_seconds > 0 else 0

    def get_stats(self) -> dict:
        """获取统计信息"""
        uptime = time.time() - self.start_time
        process = psutil.Process()

        try:
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            cpu_percent = process.cpu_percent(interval=0.1)
        except Exception as e:
            logger.warning(f"获取进程信息失败: {e}")
            memory_mb = 0
            cpu_percent = 0

        return {
            "uptime_seconds": uptime,
            "uptime_formatted": self._format_uptime(uptime),
            "message_count": self.message_count,
            "error_count": self.error_count,
            "message_rate_1min": self.get_message_rate(60),
            "message_rate_5min": self.get_message_rate(300),
            "last_message_time": datetime.fromtimestamp(self.last_message_time).isoformat() if self.last_message_time else None,
            "memory_mb": round(memory_mb, 2),
            "memory_percent": round(process.memory_percent(), 2) if memory_mb > 0 else 0,
            "cpu_percent": round(cpu_percent, 2),
            "db_semaphore": db_semaphore.get_stats(),
            "message_rate_limiter": message_rate_limiter.get_stats(),
            "price_parse_rate_limiter": price_parse_rate_limiter.get_stats(),
        }

    def _format_uptime(self, seconds: float) -> str:
        """格式化运行时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}h {minutes}m {secs}s"

    def is_healthy(self) -> dict:
        """健康检查"""
        stats = self.get_stats()
        issues = []

        # 内存检查 (> 1GB)
        if stats["memory_mb"] > 1024:
            issues.append(f"内存使用过高: {stats['memory_mb']:.2f} MB")

        # CPU 检查 (> 80%)
        if stats["cpu_percent"] > 80:
            issues.append(f"CPU 使用过高: {stats['cpu_percent']:.2f}%")

        # 数据库连接检查
        if stats["db_semaphore"]["available"] == 0:
            issues.append("数据库连接池已耗尽")

        # 错误率检查
        if stats["message_count"] > 0:
            error_rate = stats["error_count"] / stats["message_count"]
            if error_rate > 0.1:  # 错误率 > 10%
                issues.append(f"错误率过高: {error_rate:.1%}")

        return {
            "healthy": len(issues) == 0,
            "issues": issues
        }

    async def start_monitoring(self, interval_seconds: int = 60):
        """启动定期监控任务"""
        async def monitor_loop():
            while True:
                try:
                    stats = self.get_stats()
                    health = self.is_healthy()
                    logger.info(f"性能监控: 消息={stats['message_count']}, "
                              f"速率={stats['message_rate_1min']:.1f}/s, "
                              f"内存={stats['memory_mb']:.1f}MB, "
                              f"CPU={stats['cpu_percent']:.1f}%")

                    if health["issues"]:
                        logger.warning(f"健康检查发现问题: {health['issues']}")
                except Exception as e:
                    logger.error(f"监控任务出错: {e}")

                await asyncio.sleep(interval_seconds)

        self._monitoring_task = asyncio.create_task(monitor_loop())
        logger.info(f"性能监控已启动，间隔: {interval_seconds}秒")

    async def stop_monitoring(self):
        """停止监控任务"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("性能监控已停止")


# 全局性能监控器实例
performance_monitor = PerformanceMonitor()
