"""
数据库操作服务
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import Group, Order, Transaction, Admin, User


class DatabaseService:
    """数据库操作服务"""

    @staticmethod
    async def register_user(
        db: AsyncSession,
        user_id: int,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
        language_code: str = "",
        is_premium: bool = False,
        is_bot: bool = False
    ) -> User:
        """注册或更新用户信息"""
        result = await db.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                user_id=user_id,
                username=username or "",
                first_name=first_name or "",
                last_name=last_name or "",
                language_code=language_code or "",
                is_premium=is_premium,
                is_bot=is_bot,
                last_interaction_at=datetime.now()
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
            # 更新用户信息和最后交互时间
            user.username = username or user.username
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.language_code = language_code or user.language_code
            user.is_premium = is_premium
            user.is_bot = is_bot
            user.last_interaction_at = datetime.now()
            await db.commit()

        return user

    @staticmethod
    async def get_user(db: AsyncSession, user_id: int) -> User | None:
        """获取用户"""
        result = await db.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all_users(db: AsyncSession, limit: int = 100) -> list[User]:
        """获取所有用户"""
        result = await db.execute(
            select(User)
            .order_by(User.last_interaction_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_or_create_group(
        db: AsyncSession,
        chat_id: int,
        group_name: str = ""
    ) -> Group:
        """获取或创建群组"""
        result = await db.execute(select(Group).where(Group.chat_id == chat_id))
        group = result.scalar_one_or_none()

        if group is None:
            group = Group(
                chat_id=chat_id,
                group_name=group_name,
                total_amount=Decimal("0")
            )
            db.add(group)
            await db.commit()
            await db.refresh(group)
        elif group_name and group_name != group.group_name:
            group.group_name = group_name
            group.updated_at = datetime.now()
            await db.commit()

        return group

    @staticmethod
    async def get_group(db: AsyncSession, chat_id: int) -> Group | None:
        """获取群组"""
        result = await db.execute(select(Group).where(Group.chat_id == chat_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_group_amount(
        db: AsyncSession,
        chat_id: int,
        amount: Decimal
    ) -> Group:
        """更新群组账单金额"""
        group = await DatabaseService.get_or_create_group(db, chat_id)
        group.total_amount = amount
        group.updated_at = datetime.now()
        await db.commit()
        await db.refresh(group)
        return group

    @staticmethod
    async def add_order(
        db: AsyncSession,
        chat_id: int,
        user_id: int,
        user_name: str,
        amount: Decimal,
        raw_text: str = "",
        group_name: str = ""
    ) -> Order:
        """添加订单记录"""
        order = Order(
            chat_id=chat_id,
            user_id=user_id,
            user_name=user_name,
            amount=amount,
            raw_text=raw_text
        )
        db.add(order)

        # 更新群组总额
        group = await DatabaseService.get_or_create_group(db, chat_id, group_name)
        group.total_amount += amount
        group.updated_at = datetime.now()

        # 添加交易记录
        transaction = Transaction(
            chat_id=chat_id,
            user_id=user_id,
            user_name=user_name,
            type="order",
            amount=amount,
            note=f"订单: {user_name}"
        )
        db.add(transaction)

        await db.commit()
        await db.refresh(order)
        return order

    @staticmethod
    async def add_transaction(
        db: AsyncSession,
        chat_id: int,
        user_id: int,
        user_name: str,
        trans_type: str,
        amount: Decimal,
        note: str = "",
        group_name: str = ""
    ) -> Transaction:
        """添加交易记录"""
        transaction = Transaction(
            chat_id=chat_id,
            user_id=user_id,
            user_name=user_name,
            type=trans_type,
            amount=amount,
            note=note
        )
        db.add(transaction)

        # 更新群组总额
        group = await DatabaseService.get_or_create_group(db, chat_id, group_name)
        if trans_type in ["add", "order"]:
            group.total_amount += abs(amount)
        elif trans_type in ["reduce", "clear"]:
            group.total_amount -= abs(amount)
        group.updated_at = datetime.now()

        await db.commit()
        await db.refresh(transaction)
        return transaction

    @staticmethod
    async def get_order_count(db: AsyncSession, chat_id: int) -> int:
        """获取群组订单数量"""
        result = await db.execute(
            select(Order).where(Order.chat_id == chat_id)
        )
        return len(result.all())

    @staticmethod
    async def get_recent_orders(
        db: AsyncSession,
        chat_id: int,
        limit: int = 10
    ) -> list[Order]:
        """获取最近的订单记录"""
        result = await db.execute(
            select(Order)
            .where(Order.chat_id == chat_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_recent_transactions(
        db: AsyncSession,
        chat_id: int,
        limit: int = 10
    ) -> list[Transaction]:
        """获取最近的交易记录"""
        result = await db.execute(
            select(Transaction)
            .where(Transaction.chat_id == chat_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def clear_group_data(db: AsyncSession, chat_id: int) -> bool:
        """清空群组数据（删除订单和交易记录，清零金额）"""
        try:
            # 删除所有订单
            await db.execute(delete(Order).where(Order.chat_id == chat_id))

            # 删除所有交易
            await db.execute(delete(Transaction).where(Transaction.chat_id == chat_id))

            # 清零群组金额
            group = await DatabaseService.get_group(db, chat_id)
            if group:
                group.total_amount = Decimal("0")
                group.updated_at = datetime.now()

            await db.commit()
            return True
        except Exception:
            await db.rollback()
            return False

    @staticmethod
    async def is_super_admin(db: AsyncSession, user_id: int) -> bool:
        """检查是否为超级管理员（数据库中）"""
        result = await db.execute(
            select(Admin).where(
                Admin.user_id == user_id,
                Admin.is_super_admin == True
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def is_group_admin(db: AsyncSession, user_id: int, chat_id: int) -> bool:
        """检查是否为群组管理员"""
        result = await db.execute(
            select(Admin).where(
                Admin.user_id == user_id,
                Admin.chat_id == chat_id
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def is_admin(db: AsyncSession, user_id: int, chat_id: int | None = None) -> bool:
        """检查是否为管理员（包括超级管理员和群组管理员）"""
        # 检查是否为超级管理员
        if await db_service.is_super_admin(db, user_id):
            return True

        # 检查是否为群组管理员
        if chat_id is not None:
            if await db_service.is_group_admin(db, user_id, chat_id):
                return True

        return False

    @staticmethod
    async def get_super_admins(db: AsyncSession) -> list[Admin]:
        """获取所有超级管理员"""
        result = await db.execute(
            select(Admin).where(Admin.is_super_admin == True)
        )
        return list(result.scalars().all())

    @staticmethod
    async def add_admin(
        db: AsyncSession,
        user_id: int,
        chat_id: int | None = None,
        is_super_admin: bool = False
    ) -> Admin:
        """添加管理员"""
        # 检查是否已存在
        if is_super_admin:
            result = await db.execute(
                select(Admin).where(
                    Admin.user_id == user_id,
                    Admin.is_super_admin == True
                )
            )
        else:
            result = await db.execute(
                select(Admin).where(
                    Admin.user_id == user_id,
                    Admin.chat_id == chat_id
                )
            )

        existing = result.scalar_one_or_none()
        if existing:
            return existing

        admin = Admin(
            user_id=user_id,
            chat_id=chat_id,
            is_super_admin=is_super_admin
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        return admin

    @staticmethod
    async def remove_admin(
        db: AsyncSession,
        user_id: int,
        chat_id: int | None = None
    ) -> bool:
        """移除管理员"""
        if chat_id is None:
            # 移除超级管理员
            await db.execute(
                delete(Admin).where(
                    Admin.user_id == user_id,
                    Admin.is_super_admin == True
                )
            )
        else:
            # 移除群组管理员
            await db.execute(
                delete(Admin).where(
                    Admin.user_id == user_id,
                    Admin.chat_id == chat_id
                )
            )
        await db.commit()
        return True

    @staticmethod
    async def get_group_admins(db: AsyncSession, chat_id: int) -> list[Admin]:
        """获取群组管理员列表"""
        result = await db.execute(
            select(Admin).where(Admin.chat_id == chat_id)
        )
        return list(result.scalars().all())


# 全局数据库服务实例
db_service = DatabaseService()
