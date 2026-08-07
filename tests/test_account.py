from decimal import Decimal

from app.crud import create_account, get_account, get_account_by_number
from app.models import Base


def test_create_and_read_account(monkeypatch):
    db_url = "sqlite+pysqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", db_url)
    from app.database import engine, SessionLocal
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        account = create_account(db, "ACC123", "Kim", Decimal("10000.00"))
        assert account.id is not None
        assert account.account_number == "ACC123"
        assert account.owner_name == "Kim"
        assert account.balance == Decimal("10000.00")

        found = get_account(db, account.id)
        assert found is not None
        assert found.account_number == "ACC123"

        found_by_number = get_account_by_number(db, "ACC123")
        assert found_by_number is not None
        assert found_by_number.id == account.id
    finally:
        db.close()
