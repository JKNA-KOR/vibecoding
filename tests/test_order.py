from decimal import Decimal

from app import database
from app.crud import create_account, create_order, get_order, cancel_order
from app.models import Base, OrderStatus


def test_create_order_and_cancel(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    from app.database import engine, SessionLocal

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        account = create_account(db, "ACC456", "Lee", Decimal("10000.00"))
        order = create_order(db, account.id, "KODEXGOLD", 10, Decimal("500.00"), "BUY")
        assert order.id is not None
        assert order.status == OrderStatus.PENDING

        cancelled = cancel_order(db, order.id)
        assert cancelled is not None
        assert cancelled.status == cancelled.status.CANCELLED

        same_order = get_order(db, order.id)
        assert same_order.status == same_order.status.CANCELLED
    finally:
        db.close()
