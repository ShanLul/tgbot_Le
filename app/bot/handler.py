"""
Telegram消息处理器
"""
import logging
import re
from decimal import Decimal, InvalidOperation
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from app.services.price_parser import price_parser
from app.services.database_service import db_service
from app.bot.config import settings
from app.utils.auth import (
    permission_checker,
    get_user_id,
    get_chat_id,
    get_user_name,
    get_group_name,
    check_has_prefix,
    extract_amount_command,
    is_clear_command
)

logger = logging.getLogger(__name__)


def clean_message_text(text: str) -> str:
    """
    清洗消息文本，只保留机器人需要的字符

    保留：数字、中文字符、基本运算符、基本标点
    删除：其他所有特殊符号和表情

    Args:
        text: 原始文本

    Returns:
        清洗后的文本
    """
    if not text:
        return text

    # 只保留需要的字符：
    # \u4e00-\u9fff 中文字符
    # \d 数字
    # +\-*/=() 运算符和括号
    # \s 空白字符
    # ,.;:，。；：、！!? 基本标点
    pattern = re.compile(r"[^\u4e00-\u9fff\d+\-*/=()×\s,.;:，。；：、！!?.]")
    text = pattern.sub("", text)

    # 替换乘号为 *
    text = text.replace("×", "*")

    # 移除多余的空白字符
    text = re.sub(r"\s+", " ", text)

    return text.strip()


class MessageHandler:
    """消息处理器"""

    async def _register_user(self, update: Update, db: AsyncSession):
        """自动注册/更新用户信息（仅私聊时）"""
        if not update.message or not update.message.from_user:
            return

        # 只在私聊时注册用户
        if update.message.chat.type != "private":
            return

        user = update.message.from_user
        await db_service.register_user(
            db=db,
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            language_code=user.language_code or "",
            is_premium=user.is_premium or False,
            is_bot=user.is_bot or False
        )

    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        db: AsyncSession
    ):
        """处理文本消息"""
        if not update.message or not update.message.text:
            return

        # 自动注册/更新用户信息
        await self._register_user(update, db)

        # 清洗消息文本（移除表情符号和特殊字符）
        text = clean_message_text(update.message.text)
        user_id = get_user_id(update)
        chat_id = get_chat_id(update)
        user_name = get_user_name(update)
        group_name = get_group_name(update)

        # 调试信息
        chat = update.message.chat
        debug_info = f"DEBUG: user_id={user_id}, chat_id={chat_id}, chat_type={chat.type if chat else 'None'}, chat_title={chat.title if chat else 'None'}, group_name='{group_name}'"
        print(debug_info, flush=True)
        logger.info(debug_info)

        # 1. 检查是否为管理员调整金额指令
        cmd_op, cmd_amount = extract_amount_command(text)
        if cmd_op:
            await self._handle_amount_adjust(
                update, db, chat_id, user_id, user_name, group_name, cmd_op, cmd_amount
            )
            return

        # 2. 检查是否为清账指令
        print(f"[DEBUG] 检查清账: text='{text}', is_clear={is_clear_command(text)}", flush=True)
        if is_clear_command(text):
            await self._handle_clear(update, db, chat_id, user_id, user_name, group_name)
            return

        # 3. 只有消息包含"总"字时才解析价格
        if "总" not in text:
            return  # 不处理，静默忽略

        result = price_parser.parse(text)

        if not result.success:
            await update.message.reply_text(
                f"❌ 无法识别价格信息\n\n{result.error or '请确认格式正确'}"
            )
            return

        # 5. 添加订单
        try:
            await db_service.add_order(
                db=db,
                chat_id=chat_id,
                user_id=user_id,
                user_name=user_name,
                amount=result.amount,
                raw_text=text[:500],  # 限制长度
                group_name=group_name
            )

            # 获取当前总额
            group = await db_service.get_group(db, chat_id)

            response = f"✅ 订单已记录\n"
            response += f"💰 金额: `{result.amount}` 元\n"
            response += f"📊 当前总额: `{group.total_amount}` 元"

            if result.expression:
                response += f"\n🧮 算式: `{result.expression}`"

            await update.message.reply_text(response, parse_mode="Markdown")

        except Exception as e:
            await update.message.reply_text(f"❌ 记录订单时出错: {str(e)}")

    async def _handle_amount_adjust(
        self,
        update: Update,
        db: AsyncSession,
        chat_id: int,
        user_id: int,
        user_name: str,
        group_name: str,
        operation: str,
        amount: float
    ):
        """处理金额调整指令"""
        # 检查权限
        is_admin = await permission_checker.is_admin(db, user_id, chat_id)
        if not is_admin:
            await update.message.reply_text("❌ 只有管理员才能调整账单")
            return

        try:
            decimal_amount = Decimal(str(amount))

            if operation == "+":
                trans_type = "add"
                sign = "+"
                action = "增加"
            else:
                trans_type = "reduce"
                sign = "-"
                action = "减少"

            await db_service.add_transaction(
                db=db,
                chat_id=chat_id,
                user_id=user_id,
                user_name=user_name,
                trans_type=trans_type,
                amount=decimal_amount,
                note=f"管理员{action}: {user_name}",
                group_name=group_name
            )

            group = await db_service.get_group(db, chat_id)

            await update.message.reply_text(
                f"✅ 已{action}账单 `{decimal_amount}` 元\n"
                f"📊 当前总额: `{group.total_amount}` 元",
                parse_mode="Markdown"
            )

        except (InvalidOperation, Exception) as e:
            await update.message.reply_text(f"❌ 调整账单时出错: {str(e)}")

    async def _handle_clear(
        self,
        update: Update,
        db: AsyncSession,
        chat_id: int,
        user_id: int,
        user_name: str,
        group_name: str
    ):
        """处理清账指令"""
        # 调试信息
        print(f"[DEBUG] 清账命令 - user_id={user_id}, chat_id={chat_id}", flush=True)
        print(f"[DEBUG] 配置的超级管理员: {settings.super_admin_id_list}", flush=True)

        # 检查权限
        is_admin = await permission_checker.is_admin(db, user_id, chat_id)
        print(f"[DEBUG] is_admin={is_admin}", flush=True)
        if not is_admin:
            await update.message.reply_text("❌ 只有管理员才能清账")
            return

        # 获取当前金额（先确保群组存在）
        group = await db_service.get_or_create_group(db, chat_id, group_name)
        current_amount = group.total_amount if group else Decimal("0")

        # 执行清账
        success = await db_service.clear_group_data(db, chat_id)

        if success:
            await update.message.reply_text(
                f"🗑️ 账单已清空\n"
                f"💰 清空前总额: `{current_amount}` 元\n"
                f"📊 当前总额: `0.00` 元\n"
                f"⚠️ 所有历史订单和交易记录已删除",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ 清账失败，请稍后重试")

    async def handle_error(
        self,
        update: object,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """处理错误"""
        print(f"Error: {context.error}")

        # update 可能是 None 或不是 Update 对象
        if update and isinstance(update, Update) and update.message:
            try:
                await update.message.reply_text(
                    f"❌ 处理消息时出错: {str(context.error)}"
                )
            except Exception:
                pass  # 忽略回复错误


# 全局消息处理器实例
message_handler = MessageHandler()
