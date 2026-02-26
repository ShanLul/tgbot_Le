"""
LeBot2 - Telegram智能算价机器人
FastAPI主入口
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters
)

from app.bot.config import settings
from app.bot.commands import command_handlers
from app.bot.handler import message_handler
from app.models.database import init_db, async_session_maker
from app.utils.monitoring import performance_monitor


# 配置日志
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, settings.LOG_LEVEL),
    handlers=[
        logging.FileHandler(settings.LOG_FILE, encoding="utf-8") if Path(settings.LOG_FILE).parent.exists() else logging.StreamHandler(),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Telegram Bot应用
telegram_app: Application | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global telegram_app

    # 确保目录存在
    Path("data").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)

    # 启动时
    logger.info("正在启动 LeBot2...")

    # 初始化数据库
    await init_db()
    logger.info("数据库初始化完成")

    # 启动性能监控
    await performance_monitor.start_monitoring(interval_seconds=120)
    logger.info("性能监控已启动")

    # 创建Telegram应用（使用代理）
    if settings.PROXY_URL:
        import httpx
        from telegram.request._httpxrequest import HTTPXRequest
        # 创建带代理的请求对象（增加超时时间）
        request = HTTPXRequest(
            proxy=settings.PROXY_URL,
            connection_pool_size=20,
            read_timeout=60,
            write_timeout=60,
            connect_timeout=30,
        )
        telegram_app = Application.builder().token(settings.BOT_TOKEN).request(request).build()
        logger.info(f"使用代理: {settings.PROXY_URL}")
    else:
        telegram_app = Application.builder().token(settings.BOT_TOKEN).build()

    # 创建命令回调（带db session）
    async def start_callback(update, context):
        async with async_session_maker() as db:
            await command_handlers.start(update, context)

    async def help_callback(update, context):
        async with async_session_maker() as db:
            await command_handlers.help_command(update, context)

    async def bill_callback(update, context):
        async with async_session_maker() as db:
            await command_handlers.bill(update, context, db)

    async def history_callback(update, context):
        async with async_session_maker() as db:
            await command_handlers.history(update, context, db)

    async def set_admin_callback(update, context):
        async with async_session_maker() as db:
            await command_handlers.set_admin(update, context, db)

    async def set_super_admin_callback(update, context):
        async with async_session_maker() as db:
            await command_handlers.set_super_admin(update, context, db)

    async def remove_super_admin_callback(update, context):
        async with async_session_maker() as db:
            await command_handlers.remove_super_admin(update, context, db)

    async def list_admins_callback(update, context):
        async with async_session_maker() as db:
            await command_handlers.list_admins(update, context, db)

    async def id_callback(update, context):
        await command_handlers.get_id(update, context)

    # 注册命令处理器
    telegram_app.add_handler(CommandHandler("start", start_callback))
    telegram_app.add_handler(CommandHandler("help", help_callback))
    telegram_app.add_handler(CommandHandler("bill", bill_callback))
    telegram_app.add_handler(CommandHandler("history", history_callback))
    telegram_app.add_handler(CommandHandler("set_admin", set_admin_callback))
    telegram_app.add_handler(CommandHandler("setadmin", set_admin_callback))  # 别名(不带下划线)
    telegram_app.add_handler(CommandHandler("set_super_admin", set_super_admin_callback))
    telegram_app.add_handler(CommandHandler("remove_super_admin", remove_super_admin_callback))
    telegram_app.add_handler(CommandHandler("list_admins", list_admins_callback))
    telegram_app.add_handler(CommandHandler("id", id_callback))  # 获取用户ID

    # 注册消息处理器（需要在回调中获取db session）
    async def message_callback(update: Update, context):
        async with async_session_maker() as db:
            await message_handler.handle_message(update, context, db)

    telegram_app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_callback)
    )

    # 注册错误处理器
    telegram_app.add_error_handler(message_handler.handle_error)

    # 调试：记录所有更新
    async def debug_all_updates(update: Update, context):
        logger.info(f"收到更新: {update.update_id}, 类型: {update.effective_chat.type if update.effective_chat else 'None'}")

    telegram_app.add_handler(MessageHandler(filters.ALL, debug_all_updates), group=-1)

    # 启动bot
    await telegram_app.initialize()
    await telegram_app.start()
    logger.info("Telegram Bot 已启动")

    # 启动轮询
    asyncio.create_task(telegram_app.updater.start_polling(drop_pending_updates=True))
    logger.info("开始轮询消息...")

    yield

    # 关闭时
    logger.info("正在关闭 LeBot2...")
    # 停止性能监控
    await performance_monitor.stop_monitoring()
    if telegram_app:
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()
    logger.info("LeBot2 已关闭")


# 创建FastAPI应用
app = FastAPI(
    title="LeBot2",
    description="Telegram智能算价机器人",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "LeBot2",
        "description": "Telegram智能算价机器人",
        "status": "running"
    }


@app.get("/health")
async def health():
    """健康检查"""
    health_status = performance_monitor.is_healthy()
    status_code = 200 if health_status["healthy"] else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if health_status["healthy"] else "unhealthy",
            "issues": health_status["issues"]
        }
    )


@app.get("/stats")
async def stats():
    """获取统计信息"""
    return performance_monitor.get_stats()


@app.get("/bot/info")
async def bot_info():
    """Bot信息"""
    return {
        "token": settings.BOT_TOKEN[:10] + "..." if settings.BOT_TOKEN else "",
        "super_admins": settings.super_admin_id_list,
        "database": settings.DATABASE_URL
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )
