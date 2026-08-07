from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path
from typing import Generator, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from . import database, market, models, schemas, service

app = FastAPI(title="Vibecoding Trading System")

template_file = Path(__file__).resolve().parent.parent / "templates" / "dashboard.html"
market_scheduler: market.MarketScheduler | None = None


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    if not template_file.exists():
        raise HTTPException(status_code=500, detail="dashboard.html 템플릿을 찾을 수 없습니다.")
    return template_file.read_text(encoding="utf-8")


@app.get("/api/dashboard-data")
def get_dashboard_data() -> dict[str, object]:
    if market_scheduler is None:
        raise HTTPException(status_code=503, detail="Market scheduler is not initialized")
    return market_scheduler.get_dashboard_data()


@app.on_event("startup")
async def startup_event() -> None:
    global market_scheduler
    models.Base.metadata.create_all(bind=database.engine)
    market_scheduler = market.MarketScheduler()
    market_scheduler.load_saved_history()
    await market_scheduler.load_initial_history()
    app.state.market_scheduler_task = asyncio.create_task(market_scheduler.run_loop())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    task = getattr(app.state, "market_scheduler_task", None)
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def get_db() -> Generator[Session, None, None]:
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/accounts", response_model=schemas.AccountRead)
def create_account(account_in: schemas.AccountCreate, db: Session = Depends(get_db)) -> schemas.AccountRead:
    try:
        account = service.TradingService(db).create_account(
            account_number=account_in.account_number,
            owner_name=account_in.owner_name,
            initial_balance=account_in.initial_balance,
        )
        return account
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/accounts/{account_id}", response_model=schemas.AccountRead)
def read_account(account_id: int, db: Session = Depends(get_db)) -> schemas.AccountRead:
    account = service.TradingService(db).get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@app.post("/orders", response_model=schemas.OrderRead)
def create_order(order_in: schemas.OrderCreate, db: Session = Depends(get_db)) -> schemas.OrderRead:
    try:
        order = service.TradingService(db).create_order(
            account_id=order_in.account_id,
            symbol=order_in.symbol,
            quantity=order_in.quantity,
            price=order_in.price,
            side=order_in.side,
        )
        return order
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/orders/{order_id}/cancel", response_model=schemas.OrderRead)
def cancel_order(order_id: int, db: Session = Depends(get_db)) -> schemas.OrderRead:
    order = service.TradingService(db).cancel_order(order_id)
    if not order:
        raise HTTPException(status_code=400, detail="Order cannot be cancelled")
    return order


@app.post("/orders/{order_id}/execute", response_model=schemas.ExecutionRead)
def execute_order(order_id: int, execution_in: schemas.ExecutionCreate, db: Session = Depends(get_db)) -> schemas.ExecutionRead:
    try:
        execution = service.TradingService(db).simulate_execution(order_id, execution_in.executed_price)
        return execution
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/accounts/{account_id}/orders", response_model=list[schemas.OrderRead])
def list_account_orders(account_id: int, db: Session = Depends(get_db)) -> list[schemas.OrderRead]:
    return service.TradingService(db).get_account_orders(account_id)


@app.get("/accounts/{account_id}/positions", response_model=list[schemas.PositionRead])
def list_account_positions(account_id: int, db: Session = Depends(get_db)) -> list[schemas.PositionRead]:
    return service.TradingService(db).get_account_positions(account_id)


@app.get("/accounts/{account_id}/pnl")
def account_pnl(account_id: int, db: Session = Depends(get_db)) -> dict[str, float]:
    pnl = service.TradingService(db).get_account_profit_loss(account_id)
    return {"pnl": float(pnl)}


@app.get("/market/{symbol}", response_model=schemas.QuoteRead)
def get_market_quote(symbol: str, db: Session = Depends(get_db)) -> schemas.QuoteRead:
    return service.TradingService(db).get_market_quote(symbol)


@app.get(
    "/market/{symbol}/recommendation",
    response_model=schemas.MarketRecommendationRead,
)
def get_market_recommendation(
    symbol: str,
    previous_price: Optional[Decimal] = None,
    db: Session = Depends(get_db),
) -> schemas.MarketRecommendationRead:
    result = market.MarketAnalyzer(market.MarketDataProvider()).analyze(symbol, previous_price)
    quote = result["quote"]
    return schemas.MarketRecommendationRead(
        symbol=quote.symbol,
        price=quote.price,
        timestamp=quote.timestamp,
        recommendation=result["recommendation"],
        reason=result["reason"],
    )


@app.post("/signals", response_model=schemas.SignalRead)
def create_signal(signal_in: schemas.SignalCreate, db: Session = Depends(get_db)) -> schemas.SignalRead:
    try:
        signal = service.TradingService(db).generate_signal(
            symbol=signal_in.symbol,
            account_id=signal_in.account_id,
            previous_price=signal_in.previous_price,
        )
        return signal
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/signals", response_model=list[schemas.SignalRead])
def list_signals(account_id: Optional[int] = None, db: Session = Depends(get_db)) -> list[schemas.SignalRead]:
    return service.TradingService(db).get_signals(account_id)
