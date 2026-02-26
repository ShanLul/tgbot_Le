"""
数据库模型定义
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, BigInteger, Boolean, DateTime, Numeric, Text, Integer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from app.bot.config import settings


class Base(DeclarativeBase):
    """数据库基类"""
    pass


# 创建异步引擎（针对200+群组高并发场景优化）
# pool_size: 保持连接池大小，SQLite 不需要连接池但设置以防未来迁移
# pool_recycle: 自动回收连接，防止连接过期
# pool_pre_ping: 使用前测试连接
# connect_args: SQLite 特定配置
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
)

# 创建会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """获取数据库会话"""
    async with async_session_maker() as session:
        yield session


async def init_db():
    """初始化数据库表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ============= 数据表模型 =============


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(255), default="")
    first_name: Mapped[str] = mapped_column(String(255), default="")
    last_name: Mapped[str] = mapped_column(String(255), default="")
    language_code: Mapped[str] = mapped_column(String(10), default="")
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    last_interaction_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Group(Base):
    """群组表"""
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    group_name: Mapped[str] = mapped_column(String(255), default="")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class Order(Base):
    """订单记录表"""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_name: Mapped[str] = mapped_column(String(255), default="")
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Transaction(Base):
    """账单变动表"""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_name: Mapped[str] = mapped_column(String(255), default="")
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # order/add/reduce/clear
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Admin(Base):
    """管理员表"""
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # NULL表示超级管理员
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
