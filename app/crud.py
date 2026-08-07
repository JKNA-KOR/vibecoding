from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


def get_account(db: Session, account_id: int) -> Optional[models.Account]:
    return db.execute(select(models.Account).where(models.Account.id == account_id)).scalars().first()


def get_account_by_number(db: Session, account_number: str) -> Optional[models.Account]:
    return db.execute(select(models.Account).where(models.Account.account_number == account_number)).scalars().first()


def create_account(db: Session, account_number: str, owner_name: str, initial_balance: Decimal) -> models.Account:
    account = models.Account(
        account_number=account_number,
        owner_name=owner_name,
        balance=initial_balance,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def create_order(db: Session, account_id: int, symbol: str, quantity: int, price: Decimal, side: str) -> models.Order:
    order = models.Order(
        account_id=account_id,
        symbol=symbol,
        quantity=quantity,
        price=price,
        side=side,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id: int) -> Optional[models.Order]:
    return db.execute(select(models.Order).where(models.Order.id == order_id)).scalars().first()


def cancel_order(db: Session, order_id: int) -> Optional[models.Order]:
    order = get_order(db, order_id)
    if order is None or order.status != models.OrderStatus.PENDING:
        return None
    order.status = models.OrderStatus.CANCELLED
    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(order)
    return order


def create_execution(db: Session, order: models.Order, executed_price: Decimal, quantity: int, pnl: Decimal) -> models.Execution:
    execution = models.Execution(
        order_id=order.id,
        account_id=order.account_id,
        symbol=order.symbol,
        executed_price=executed_price,
        quantity=quantity,
        side=order.side,
        pnl=pnl,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def get_position(db: Session, account_id: int, symbol: str) -> Optional[models.Position]:
    return db.execute(
        select(models.Position).where(
            models.Position.account_id == account_id,
            models.Position.symbol == symbol,
        )
    ).scalars().first()


def update_position_on_execution(db: Session, account_id: int, symbol: str, quantity: int, executed_price: Decimal, side: str) -> Decimal:
    position = get_position(db, account_id, symbol)
    if side == "BUY":
        if position is None:
            position = models.Position(
                account_id=account_id,
                symbol=symbol,
                quantity=quantity,
                average_cost=executed_price,
            )
            db.add(position)
        else:
            total_cost = position.average_cost * position.quantity + executed_price * quantity
            position.quantity += quantity
            position.average_cost = total_cost / position.quantity
            position.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(position)
        return Decimal("0.0")

    if position is None or position.quantity < quantity:
        raise ValueError("Insufficient position for sell execution")

    pnl = (executed_price - position.average_cost) * quantity
    position.quantity -= quantity
    if position.quantity == 0:
        position.average_cost = Decimal("0.0")
    position.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(position)
    return pnl


def create_signal(
    db: Session,
    account_id: Optional[int],
    symbol: str,
    recommendation: str,
    reason: str,
    price: Decimal,
    previous_price: Optional[Decimal],
) -> models.Signal:
    signal = models.Signal(
        account_id=account_id,
        symbol=symbol,
        recommendation=recommendation,
        reason=reason,
        price=price,
        previous_price=previous_price,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


def list_signals(db: Session, account_id: Optional[int] = None) -> list[models.Signal]:
    query = select(models.Signal)
    if account_id is not None:
        query = query.where(models.Signal.account_id == account_id)
    return db.execute(query).scalars().all()


def create_market_quote(db: Session, symbol: str, price: Decimal, timestamp: datetime) -> models.MarketQuote:
    quote = models.MarketQuote(symbol=symbol, price=price, timestamp=timestamp)
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


def list_market_quotes(db: Session, symbol: str, limit: int = 100) -> list[models.MarketQuote]:
    query = select(models.MarketQuote).where(models.MarketQuote.symbol == symbol).order_by(models.MarketQuote.timestamp.desc()).limit(limit)
    return db.execute(query).scalars().all()


def update_account_balance(db: Session, account: models.Account, delta: Decimal) -> models.Account:
    account.balance += delta
    account.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(account)
    return account


def list_orders(db: Session, account_id: int) -> list[models.Order]:
    return db.execute(select(models.Order).where(models.Order.account_id == account_id)).scalars().all()


def list_positions(db: Session, account_id: int) -> list[models.Position]:
    return db.execute(select(models.Position).where(models.Position.account_id == account_id)).scalars().all()


def list_executions(db: Session, account_id: int) -> list[models.Execution]:
    return db.execute(select(models.Execution).where(models.Execution.account_id == account_id)).scalars().all()
