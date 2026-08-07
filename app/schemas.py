from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class AccountCreate(BaseModel):
    account_number: str = Field(..., max_length=32)
    owner_name: str = Field(..., max_length=128)
    initial_balance: Decimal = Field(..., ge=0)


class AccountRead(BaseModel):
    id: int
    account_number: str
    owner_name: str
    balance: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    account_id: int
    symbol: str = Field(..., max_length=32)
    quantity: int = Field(..., gt=0)
    price: Decimal = Field(..., gt=0)
    side: str = Field(..., pattern="^(BUY|SELL)$")


class OrderRead(BaseModel):
    id: int
    account_id: int
    symbol: str
    quantity: int
    price: Decimal
    side: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExecutionCreate(BaseModel):
    executed_price: Decimal = Field(..., gt=0)


class ExecutionRead(BaseModel):
    id: int
    order_id: int
    account_id: int
    symbol: str
    executed_price: Decimal
    quantity: int
    side: str
    pnl: Decimal
    executed_at: datetime

    class Config:
        from_attributes = True


class QuoteRead(BaseModel):
    symbol: str
    price: Decimal
    timestamp: datetime


class SignalCreate(BaseModel):
    symbol: str = Field(..., max_length=32)
    account_id: Optional[int] = None
    previous_price: Optional[Decimal] = None


class PositionRead(BaseModel):
    id: int
    account_id: int
    symbol: str
    quantity: int
    average_cost: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SignalRead(BaseModel):
    id: int
    account_id: Optional[int] = None
    symbol: str
    recommendation: str
    reason: str
    price: Decimal
    previous_price: Optional[Decimal] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MarketRecommendationRead(BaseModel):
    symbol: str
    price: Decimal
    timestamp: datetime
    recommendation: str
    reason: str

    class Config:
        from_attributes = True
