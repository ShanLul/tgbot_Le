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
