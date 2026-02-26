"""
Bot配置文件
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    # Telegram Bot配置
    BOT_TOKEN: str = ""

    # 超级管理员ID（逗号分隔）
    SUPER_ADMIN_IDS: str = ""

    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/bot.db"

    # API配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/bot.log"

    # 性能配置
    # 数据库连接池大小
    DB_POOL_SIZE: int = 5
    # 最大溢出连接数
    DB_MAX_OVERFLOW: int = 10
    # 连接回收时间（秒）
    DB_POOL_RECYCLE: int = 3600

    # 并发配置
    # 最大并发数据库操作数
    MAX_DB_CONCURRENT: int = 50
    # 每个群组每分钟最大消息数
    MAX_MESSAGES_PER_GROUP_PER_MINUTE: int = 100
    # 每个用户每分钟最大价格解析次数
    MAX_PRICE_PARSE_PER_USER_PER_MINUTE: int = 50

    # 代理配置（访问 Telegram API 需要）
    PROXY_URL: str = "http://127.0.0.1:7897"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def super_admin_id_list(self) -> list[int]:
        """获取超级管理员ID列表"""
        if not self.SUPER_ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.SUPER_ADMIN_IDS.split(",") if x.strip()]


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 全局配置实例
settings = get_settings()
