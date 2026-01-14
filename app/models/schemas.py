"""
Pydantic数据模型
"""
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field


class GroupResponse(BaseModel):
    """群组响应"""
    id: int
    chat_id: int
    group_name: str
    total_amount: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    """订单响应"""
    id: int
    chat_id: int
    user_id: int
    user_name: str
    amount: Decimal
    raw_text: str
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionResponse(BaseModel):
    """交易响应"""
    id: int
    chat_id: int
    user_id: int
    user_name: str
    type: str
    amount: Decimal
    note: str
    created_at: datetime

    class Config:
        from_attributes = True


class AdminResponse(BaseModel):
    """管理员响应"""
    id: int
    user_id: int
    chat_id: int | None
    is_super_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PriceParseResult(BaseModel):
    """价格解析结果"""
    success: bool
    amount: Decimal | None = None
    expression: str | None = None
    error: str | None = None


class BillInfo(BaseModel):
    """账单信息"""
    chat_id: int
    group_name: str
    total_amount: Decimal
    order_count: int
