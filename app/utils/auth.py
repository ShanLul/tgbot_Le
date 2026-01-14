"""
权限验证工具
"""
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.config import settings
from app.services.database_service import db_service


class PermissionChecker:
    """权限检查器"""

    @staticmethod
    def is_config_super_admin(user_id: int) -> bool:
        """检查是否为配置文件中的超级管理员"""
        return user_id in settings.super_admin_id_list

    @staticmethod
    async def is_super_admin(db: AsyncSession, user_id: int) -> bool:
        """检查是否为超级管理员（配置 + 数据库）"""
        # 先检查配置文件
        if user_id in settings.super_admin_id_list:
            return True

        # 检查数据库中的超级管理员
        return await db_service.is_super_admin(db, user_id)

    @staticmethod
    async def is_admin(
        db: AsyncSession,
        user_id: int,
        chat_id: int | None = None
    ) -> bool:
        """检查是否为管理员（包括超级管理员）"""
        # 先检查是否为超级管理员
        if await PermissionChecker.is_super_admin(db, user_id):
            return True

        # 检查数据库中的群组管理员
        if chat_id is not None:
            return await db_service.is_group_admin(db, user_id, chat_id)

        return False

    @staticmethod
    def get_user_id(update) -> int:
        """从Update对象中获取用户ID"""
        if update.message and update.message.from_user:
            return update.message.from_user.id
        elif update.callback_query and update.callback_query.from_user:
            return update.callback_query.from_user.id
        elif update.inline_query and update.inline_query.from_user:
            return update.inline_query.from_user.id
        raise ValueError("Cannot get user_id from update")

    @staticmethod
    def get_chat_id(update) -> int:
        """从Update对象中获取聊天ID"""
        if update.message and update.message.chat:
            return update.message.chat.id
        elif update.callback_query and update.callback_query.message:
            return update.callback_query.message.chat.id
        elif update.inline_query and update.inline_query.from_user:
            return update.inline_query.from_user.id
        raise ValueError("Cannot get chat_id from update")

    @staticmethod
    def get_user_name(update) -> str:
        """从Update对象中获取用户名"""
        if update.message and update.message.from_user:
            user = update.message.from_user
        elif update.callback_query and update.callback_query.from_user:
            user = update.callback_query.from_user
        elif update.inline_query and update.inline_query.from_user:
            user = update.inline_query.from_user
        else:
            return "Unknown"

        if user.username:
            return f"@{user.username}"
        return f"{user.first_name or ''} {user.last_name or ''}".strip()

    @staticmethod
    def get_group_name(update) -> str:
        """从Update对象中获取群组名"""
        if update.message and update.message.chat:
            chat = update.message.chat
        elif update.callback_query and update.callback_query.message:
            chat = update.callback_query.message.chat
        else:
            return "Unknown"

        if chat.title:
            return chat.title
        return f"chat_{chat.id}"


def check_has_prefix(text: str) -> bool:
    """
    检查文本是否有 a/A 前缀
    规则：以 a 或 A 开头即视为有前缀

    Args:
        text: 待检查的文本

    Returns:
        是否有有效前缀
    """
    if not text:
        return False

    text = text.strip()
    if not text:
        return False

    # 检查是否以 a 或 A 开头
    return text[0] in "aA"


def extract_amount_command(text: str) -> tuple[Literal["+", "-"] | None, float | None]:
    """
    提取金额调整指令

    Args:
        text: 待解析的文本

    Returns:
        (操作类型, 金额) 如 ("+", 100) 或 ("-", 50)
    """
    if not text:
        return None, None

    text = text.strip()

    # 匹配 +数字 或 -数字
    if text.startswith("+") and len(text) > 1:
        try:
            amount = float(text[1:])
            if amount > 0:
                return "+", amount
        except ValueError:
            pass
    elif text.startswith("-") and len(text) > 1:
        try:
            amount = float(text[1:])
            if amount > 0:
                return "-", amount
        except ValueError:
            pass

    return None, None


def is_clear_command(text: str) -> bool:
    """
    检查是否为清账指令
    支持"清账"和"清帐"（两个常用字）

    Args:
        text: 待检查的文本

    Returns:
        是否为清账指令
    """
    if not text:
        return False
    stripped = text.strip()
    # 同时支持"清账"和"清帐"
    return stripped == "清账" or stripped == "清帐"


# 模块级函数（方便导入使用）
def get_user_id(message) -> int:
    """从消息中获取用户ID"""
    return PermissionChecker.get_user_id(message)


def get_chat_id(message) -> int:
    """从消息中获取聊天ID"""
    return PermissionChecker.get_chat_id(message)


def get_user_name(message) -> str:
    """从消息中获取用户名"""
    return PermissionChecker.get_user_name(message)


def get_group_name(message) -> str:
    """从消息中获取群组名"""
    return PermissionChecker.get_group_name(message)


# 全局权限检查器实例
permission_checker = PermissionChecker()
