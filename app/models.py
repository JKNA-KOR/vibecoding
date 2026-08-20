from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_number = Column(String(32), unique=True, nullable=False)
    owner_name = Column(String(128), nullable=False)
    balance = Column(Numeric(18, 4), nullable=False, default=Decimal("0.0"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    orders = relationship("Order", back_populates="account")
    executions = relationship("Execution", back_populates="account")
    positions = relationship("Position", back_populates="account")
    signals = relationship("Signal", back_populates="account")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    symbol = Column(String(32), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(18, 4), nullable=False)
    side = Column(String(4), nullable=False)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    account = relationship("Account", back_populates="orders")
    executions = relationship("Execution", back_populates="order")


class Execution(Base):
    __tablename__ = "executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    symbol = Column(String(32), nullable=False)
    executed_price = Column(Numeric(18, 4), nullable=False)
    quantity = Column(Integer, nullable=False)
    side = Column(String(4), nullable=False)
    pnl = Column(Numeric(18, 4), nullable=False, default=Decimal("0.0"))
    executed_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    order = relationship("Order", back_populates="executions")
    account = relationship("Account", back_populates="executions")


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    symbol = Column(String(32), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    average_cost = Column(Numeric(18, 4), nullable=False, default=Decimal("0.0"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    account = relationship("Account", back_populates="positions")


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    symbol = Column(String(32), nullable=False)
    recommendation = Column(String(16), nullable=False)
    reason = Column(String(256), nullable=False)
    price = Column(Numeric(18, 4), nullable=False)
    previous_price = Column(Numeric(18, 4), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    account = relationship("Account", back_populates="signals")


class MarketQuote(Base):
    __tablename__ = "market_quotes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False, index=True)
    price = Column(Numeric(18, 4), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class MarketGap(Base):
    __tablename__ = "market_gaps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    gap_percent = Column(Numeric(10, 4), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class GoldPrediction(Base):
    __tablename__ = "gold_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(100), nullable=False)
    horizon = Column(String(20), nullable=False)
    predicted_price = Column(Numeric(18, 4), nullable=False)
    predicted_at = Column(DateTime(timezone=True), nullable=False)
    target_timestamp = Column(DateTime(timezone=True), nullable=False)
    recommendation = Column(String(20), nullable=True)
    confidence = Column(String(20), nullable=True)
    training_mode = Column(String(50), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=datetime.utcnow,
    )


