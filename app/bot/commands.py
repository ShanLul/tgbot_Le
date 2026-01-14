"""
命令处理模块
"""
from decimal import Decimal, InvalidOperation
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from app.bot.config import settings
from app.services.database_service import db_service
from app.utils.auth import permission_checker, get_user_id, get_chat_id, get_user_name


class CommandHandlers:
    """命令处理器"""

    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """开始命令"""
        welcome_text = """
🤖 *智能算价机器人*

*使用方法：*
直接发送订单内容即可

*示例：*
```
d程
13045201820
黑龙江省齐齐哈尔市依安县依安镇翰林新居六栋一单元

雪茄鸭嘴兽 铁观音 绿豆 备选龙井
高维 绿豆 备选蓝莓
总186
```

*可用命令：*
`/start` - 开始使用
`/bill` 或 `/账单` - 查看当前账单
`/history` - 查看账单历史
`/help` - 显示帮助信息

*管理员命令：*
`+金额` - 增加账单 (如: `+100`)
`-金额` - 减少账单 (如: `-50`)
`清账` - 清空账单和历史数据
`/set_admin` - 设置管理员
        """
        await update.message.reply_text(welcome_text, parse_mode="Markdown")

    @staticmethod
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """帮助命令"""
        help_text = """
📖 *帮助信息*

*报单格式：*
直接发送订单内容，包含 `总xxx` 或 `合计xxx` 即可

*支持的格式：*
• `总186` - 直接识别金额
• `总60*2+60+6=186` - 带算式的金额

*查询命令：*
`/bill` 或 `/账单` - 查看当前账单
`/history` - 查看账单历史

*管理员命令：*
`+100` - 增加100元
`-50` - 减少50元
`清账` - 清空账单（会删除历史数据）
        """
        await update.message.reply_text(help_text, parse_mode="Markdown")

    @staticmethod
    async def bill(update: Update, context: ContextTypes.DEFAULT_TYPE, db: AsyncSession):
        """查看账单"""
        chat_id = get_chat_id(update)

        group = await db_service.get_group(db, chat_id)
        if group is None:
            await update.message.reply_text("📊 当前群组暂无账单记录")
            return

        order_count = await db_service.get_order_count(db, chat_id)

        bill_text = f"""
📊 *当前账单*

🏠 群组: {group.group_name or f'chat_{chat_id}'}
💰 总额: `{group.total_amount}` 元
📦 订单数: {order_count} 笔
🕒 更新: {group.updated_at.strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()
        await update.message.reply_text(bill_text, parse_mode="Markdown")

    @staticmethod
    async def history(update: Update, context: ContextTypes.DEFAULT_TYPE, db: AsyncSession):
        """查看账单历史"""
        chat_id = get_chat_id(update)

        transactions = await db_service.get_recent_transactions(db, chat_id, limit=10)

        if not transactions:
            await update.message.reply_text("📋 暂无账单历史记录")
            return

        type_names = {
            "order": "📦 订单",
            "add": "➕ 增加",
            "reduce": "➖ 减少",
            "clear": "🗑️ 清账"
        }

        lines = ["📋 *最近账单历史*"]
        for trans in transactions:
            type_name = type_names.get(trans.type, trans.type)
            sign = "+" if trans.type in ["order", "add"] else ""
            lines.append(f"{type_name} | {trans.user_name} | {sign}{trans.amount}元")

        lines.append(f"\n🕒 查询时间: {transactions[0].created_at.strftime('%Y-%m-%d %H:%M:%S')}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    @staticmethod
    async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """获取用户ID"""
        if update.message.reply_to_message:
            # 回复了其他人，显示被回复用户的ID
            target_user = update.message.reply_to_message.from_user
            target_name = target_user.username or target_user.first_name or "未知用户"
            await update.message.reply_text(
                f"👤 *{target_name}* 的用户ID：\n\n`{target_user.id}`",
                parse_mode="Markdown"
            )
        else:
            # 显示自己的ID
            user = update.message.from_user
            user_name = user.username or user.first_name or "未知用户"
            await update.message.reply_text(
                f"👤 你的用户ID：\n\n`{user.id}`\n\n💡 提示：回复别人的消息后使用此命令，可以查看对方的ID",
                parse_mode="Markdown"
            )

    @staticmethod
    async def set_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, db: AsyncSession):
        """设置管理员"""
        user_id = get_user_id(update)
        chat_id = get_chat_id(update)
        chat_type = update.message.chat.type if update.message.chat else None

        # 检查是否为超级管理员（配置 + 数据库）
        if not await permission_checker.is_super_admin(db, user_id):
            await update.message.reply_text("❌ 只有超级管理员才能设置管理员")
            return

        # 检查参数
        is_global = "--global" in context.args or "-g" in context.args if context.args else False

        # 获取要设置的用户
        if update.message.reply_to_message:
            # 方式1: 通过回复消息
            target_user_id = update.message.reply_to_message.from_user.id
            target_user_name = update.message.reply_to_message.from_user.username or \
                              update.message.reply_to_message.from_user.first_name
        elif context.args and context.args[0] not in ["--global", "-g"]:
            # 方式2: 通过用户ID
            try:
                target_user_id = int(context.args[0])
                target_user_name = f"用户({target_user_id})"
            except ValueError:
                await update.message.reply_text(
                    "❌ 用户ID必须是数字\n\n"
                    "📋 使用方法：\n"
                    "• 回复用户消息: `/set_admin [--global]`\n"
                    "• 直接指定ID: `/set_admin <用户ID> [--global]`"
                )
                return
        else:
            help_text = "📋 *使用方法：*\n\n"
            if is_global:
                help_text += "设置全局管理员：\n"
                help_text += "• 回复用户消息: `/set_admin --global`\n"
                help_text += "• 指定用户ID: `/set_admin <用户ID> --global`\n\n"
            else:
                help_text += "设置群组管理员：\n"
                help_text += "• 回复用户消息: `/set_admin`\n"
                help_text += "• 指定用户ID: `/set_admin <用户ID>`\n\n"
            help_text += "参数说明：\n"
            help_text += "`--global` 或 `-g`: 设置为全局管理员（所有群组有效）"
            await update.message.reply_text(help_text, parse_mode="Markdown")
            return

        # 添加管理员
        if is_global:
            await db_service.add_admin(db, target_user_id, chat_id=None, is_super_admin=True)
            await update.message.reply_text(
                f"✅ 已设置 `{target_user_name}` 为**全局管理员**（所有群组有效）",
                parse_mode="Markdown"
            )
        else:
            # 设置群组管理员（必须在群组中使用）
            if chat_type == "private":
                await update.message.reply_text(
                    "⚠️ 设置群组管理员需要在群组中使用\n\n"
                    "如需设置全局管理员，请使用：`/set_admin --global`",
                    parse_mode="Markdown"
                )
                return
            await db_service.add_admin(db, target_user_id, chat_id, is_super_admin=False)
            await update.message.reply_text(
                f"✅ 已设置 `{target_user_name}` 为本群组管理员",
                parse_mode="Markdown"
            )

    @staticmethod
    async def set_super_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, db: AsyncSession):
        """设置超级管理员"""
        user_id = get_user_id(update)

        # 检查是否为超级管理员
        if not await permission_checker.is_super_admin(db, user_id):
            await update.message.reply_text("❌ 只有超级管理员才能设置超级管理员")
            return

        # 获取要设置的用户
        if update.message.reply_to_message:
            # 方式1: 通过回复消息
            target_user_id = update.message.reply_to_message.from_user.id
            target_user_name = update.message.reply_to_message.from_user.username or \
                              update.message.reply_to_message.from_user.first_name
        elif context.args and context.args[0]:
            # 方式2: 通过用户ID
            try:
                target_user_id = int(context.args[0])
                target_user_name = f"用户({target_user_id})"
            except ValueError:
                await update.message.reply_text(
                    "❌ 用户ID必须是数字\n\n"
                    "📋 使用方法：\n"
                    "• 回复用户消息: `/set_super_admin`\n"
                    "• 指定用户ID: `/set_super_admin <用户ID>`"
                )
                return
        else:
            await update.message.reply_text(
                "📋 使用方法：\n"
                "回复要设置为超级管理员的用户消息，然后输入 `/set_super_admin`\n\n"
                "或直接指定用户ID：`/set_super_admin <用户ID>`"
            )
            return

        # 添加超级管理员
        await db_service.add_admin(db, target_user_id, chat_id=None, is_super_admin=True)

        await update.message.reply_text(
            f"✅ 已设置 `{target_user_name}` 为**超级管理员**（最高权限）",
            parse_mode="Markdown"
        )

    @staticmethod
    async def remove_super_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, db: AsyncSession):
        """移除超级管理员"""
        user_id = get_user_id(update)

        # 检查是否为超级管理员
        if not await permission_checker.is_super_admin(db, user_id):
            await update.message.reply_text("❌ 只有超级管理员才能移除超级管理员")
            return

        if not context.args:
            await update.message.reply_text(
                "📋 使用方法：`/remove_super_admin <用户ID>`\n\n"
                "提示：回复用户消息后使用 `/id` 可获取用户ID"
            )
            return

        try:
            target_user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ 用户ID必须是数字")
            return

        # 不能移除配置文件中的超级管理员
        if permission_checker.is_config_super_admin(target_user_id):
            await update.message.reply_text(
                "❌ 无法移除配置文件中的超级管理员\n\n"
                "如需移除，请修改 .env 文件中的 SUPER_ADMIN_IDS"
            )
            return

        # 检查是否为超级管理员
        if not await db_service.is_super_admin(db, target_user_id):
            await update.message.reply_text("❌ 该用户不是超级管理员")
            return

        # 移除超级管理员
        await db_service.remove_admin(db, target_user_id, chat_id=None)

        await update.message.reply_text(
            f"✅ 已移除用户 `{target_user_id}` 的超级管理员权限",
            parse_mode="Markdown"
        )

    @staticmethod
    async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE, db: AsyncSession):
        """列出所有管理员"""
        user_id = get_user_id(update)

        # 只有超级管理员可以查看
        if not await permission_checker.is_super_admin(db, user_id):
            await update.message.reply_text("❌ 只有超级管理员才能查看管理员列表")
            return

        # 获取所有超级管理员
        super_admins = await db_service.get_super_admins(db)

        lines = ["👑 *超级管理员列表*\n"]

        # 配置文件中的超级管理员
        config_admins = settings.super_admin_id_list
        if config_admins:
            lines.append("📁 *配置文件中：*")
            for admin_id in config_admins:
                lines.append(f"  • `{admin_id}` (.env)")

        # 数据库中的超级管理员
        if super_admins:
            lines.append("\n💾 *数据库中：*")
            for admin in super_admins:
                if admin.user_id not in config_admins:
                    lines.append(f"  • `{admin.user_id}`")

        if not config_admins and not super_admins:
            lines.append("暂无超级管理员")

        lines.append(f"\n📊 共 {len(config_admins) + len(super_admins)} 位超级管理员")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# 全局命令处理器实例
command_handlers = CommandHandlers()
