from __future__ import annotations

from decimal import Decimal
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from . import crud, market, models


class TradingService:
    def __init__(self, db: Session):
        self.db = db

    def create_account(self, account_number: str, owner_name: str, initial_balance: Decimal) -> models.Account:
        existing = crud.get_account_by_number(self.db, account_number)
        if existing:
            raise ValueError("Account number already exists")
        return crud.create_account(self.db, account_number, owner_name, initial_balance)

    def get_account(self, account_id: int) -> Optional[models.Account]:
        return crud.get_account(self.db, account_id)

    def create_order(self, account_id: int, symbol: str, quantity: int, price: Decimal, side: str) -> models.Order:
        account = crud.get_account(self.db, account_id)
        if not account:
            raise ValueError("Account not found")
        if side == "BUY":
            if account.balance < price * quantity:
                raise ValueError("Insufficient balance")
        else:
            position = crud.get_position(self.db, account_id, symbol)
            if position is None or position.quantity < quantity:
                raise ValueError("Insufficient position quantity for SELL order")
        return crud.create_order(self.db, account_id, symbol, quantity, price, side)

    def cancel_order(self, order_id: int) -> Optional[models.Order]:
        return crud.cancel_order(self.db, order_id)

    def simulate_execution(self, order_id: int, executed_price: Decimal) -> models.Execution:
        order = crud.get_order(self.db, order_id)
        if not order:
            raise ValueError("Order not found")
        if order.status != models.OrderStatus.PENDING:
            raise ValueError("Only pending orders can be executed")

        quantity = order.quantity
        pnl = crud.update_position_on_execution(
            self.db,
            order.account_id,
            order.symbol,
            quantity,
            executed_price,
            order.side,
        )

        delta = executed_price * quantity * (Decimal("-1") if order.side == "BUY" else Decimal("1"))
        order.status = models.OrderStatus.FILLED
        order.updated_at = datetime.utcnow()
        crud.update_account_balance(self.db, order.account, delta)
        execution = crud.create_execution(self.db, order, executed_price, quantity, pnl)
        return execution

    def generate_signal(
        self,
        symbol: str,
        account_id: Optional[int] = None,
        previous_price: Optional[Decimal] = None,
    ) -> models.Signal:
        analyzer = market.MarketAnalyzer(market.MarketDataProvider())
        result = analyzer.analyze(symbol, previous_price)
        quote = result["quote"]
        return crud.create_signal(
            self.db,
            account_id,
            symbol,
            result["recommendation"],
            result["reason"],
            quote.price,
            previous_price,
        )

    def get_account_profit_loss(self, account_id: int) -> Decimal:
        executions = crud.list_executions(self.db, account_id)
        return sum((execution.pnl for execution in executions), Decimal("0.0"))

    def get_account_orders(self, account_id: int) -> list[models.Order]:
        return crud.list_orders(self.db, account_id)

    def get_account_positions(self, account_id: int) -> list[models.Position]:
        return crud.list_positions(self.db, account_id)

    def get_market_quote(self, symbol: str) -> market.QuoteRead:
        return market.MarketDataProvider().get_real_time_quote(symbol)

    def get_signals(self, account_id: Optional[int] = None) -> list[models.Signal]:
        return crud.list_signals(self.db, account_id)
