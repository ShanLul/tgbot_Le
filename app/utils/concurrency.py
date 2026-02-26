"""
并发控制和限流工具
"""
import asyncio
import time
from collections import defaultdict, deque
from typing import Dict, Deque
import logging

from app.bot.config import settings

logger = logging.getLogger(__name__)


class SemaphoreLimiter:
    """基于信号量的并发限制器"""

    def __init__(self, max_concurrent: int = 100):
        """
        初始化并发限制器

        Args:
            max_concurrent: 最大并发数
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        self.active_count = 0
        self.total_requests = 0
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()

    async def acquire(self):
        """获取许可"""
        await self.semaphore.acquire()
        async with self.lock:
            self.active_count += 1
            self.total_requests += 1

    async def release(self):
        """释放许可"""
        self.semaphore.release()
        async with self.lock:
            self.active_count -= 1

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "max_concurrent": self.max_concurrent,
            "active_count": self.active_count,
            "total_requests": self.total_requests,
            "available": self.max_concurrent - self.active_count
        }


class RateLimiter:
    """基于时间窗口的限流器"""

    def __init__(self, max_requests: int = 1000, time_window: int = 60):
        """
        初始化限流器

        Args:
            max_requests: 时间窗口内最大请求数
            time_window: 时间窗口（秒）
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[int, Deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    async def is_allowed(self, key: int) -> bool:
        """
        检查是否允许请求

        Args:
            key: 限流键（通常是 chat_id 或 user_id）

        Returns:
            是否允许请求
        """
        now = time.time()

        async with self.lock:
            requests = self.requests[key]

            # 移除时间窗口外的请求
            while requests and requests[0] < now - self.time_window:
                requests.popleft()

            # 检查是否超限
            if len(requests) >= self.max_requests:
                logger.warning(f"Rate limit exceeded for key={key}: {len(requests)}/{self.max_requests}")
                return False

            # 记录本次请求
            requests.append(now)
            return True

    async def get_remaining(self, key: int) -> int:
        """获取剩余请求数"""
        async with self.lock:
            now = time.time()
            requests = self.requests[key]
            # 移除时间窗口外的请求
            while requests and requests[0] < now - self.time_window:
                requests.popleft()
            return self.max_requests - len(requests)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "max_requests": self.max_requests,
            "time_window": self.time_window,
            "active_keys": len(self.requests)
        }


class MessageQueue:
    """消息队列处理器"""

    def __init__(self, max_size: int = 10000, workers: int = 10):
        """
        初始化消息队列

        Args:
            max_size: 队列最大长度
            workers: 工作协程数
        """
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self.workers = workers
        self.running = False
        self.worker_tasks: list[asyncio.Task] = []
        self.processed_count = 0
        self.dropped_count = 0
        self.lock = asyncio.Lock()

    async def start(self, handler):
        """
        启动工作协程

        Args:
            handler: 消息处理函数
        """
        self.running = True
        for i in range(self.workers):
            task = asyncio.create_task(self._worker(handler, i))
            self.worker_tasks.append(task)
        logger.info(f"消息队列已启动: {self.workers} 个工作协程")

    async def stop(self):
        """停止工作协程"""
        self.running = False
        for task in self.worker_tasks:
            task.cancel()
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        self.worker_tasks.clear()
        logger.info("消息队列已停止")

    async def _worker(self, handler, worker_id: int):
        """工作协程"""
        logger.info(f"工作协程 #{worker_id} 已启动")
        while self.running:
            try:
                # 等待消息，超时 1 秒检查 running 状态
                item = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                try:
                    await handler(item)
                    async with self.lock:
                        self.processed_count += 1
                except Exception as e:
                    logger.error(f"工作协程 #{worker_id} 处理消息失败: {e}")
                finally:
                    self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"工作协程 #{worker_id} 异常: {e}")

    async def put(self, item):
        """添加消息到队列"""
        try:
            # 非阻塞添加，队列满时丢弃旧消息
            if self.queue.full():
                async with self.lock:
                    self.dropped_count += 1
                # 尝试移除最旧的消息
                try:
                    self.queue.get_nowait()
                    self.queue.task_done()
                except asyncio.QueueEmpty:
                    pass
            await self.queue.put(item)
        except Exception as e:
            logger.error(f"添加消息到队列失败: {e}")

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "workers": self.workers,
            "queue_size": self.queue.qsize(),
            "max_queue_size": self.queue.maxsize,
            "processed_count": self.processed_count,
            "dropped_count": self.dropped_count,
            "running": self.running
        }


# 全局并发限制器
# 针对数据库操作限制并发（SQLite 不支持真正并发）
db_semaphore = SemaphoreLimiter(max_concurrent=settings.MAX_DB_CONCURRENT)

# 针对消息处理的限流器（每个群组每分钟最多N条消息）
message_rate_limiter = RateLimiter(
    max_requests=settings.MAX_MESSAGES_PER_GROUP_PER_MINUTE,
    time_window=60
)

# 针对价格解析的限流器（每个用户每分钟最多N次解析）
price_parse_rate_limiter = RateLimiter(
    max_requests=settings.MAX_PRICE_PARSE_PER_USER_PER_MINUTE,
    time_window=60
)
