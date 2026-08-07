from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from pathlib import Path
from typing import Generator, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session

from . import database, market, models, schemas, service

# configure application logging to file for easier debugging
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
APP_LOG_FILE = LOG_DIR / "app.log"

logger = logging.getLogger("vibecoding")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    from logging.handlers import RotatingFileHandler

    handler = RotatingFileHandler(APP_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # also log to stdout for container visibility
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)

app = FastAPI(title="Vibecoding Trading System")

template_file = Path(__file__).resolve().parent.parent / "templates" / "dashboard.html"
market_scheduler: market.MarketScheduler | None = None


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    try:
        if not template_file.exists():
            logger.error("dashboard.html 템플릿을 찾을 수 없습니다.")
            # return a helpful HTML page linking to the logs
            return """
<html><body>
<h1>Dashboard template missing</h1>
<p>The dashboard template <b>dashboard.html</b> was not found. Check server logs for details.</p>
<p>View recent logs: <a href="/logs">/logs</a></p>
</body></html>
"""
        return template_file.read_text(encoding="utf-8")
    except Exception as exc:
        logger.exception("Error rendering dashboard root: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/dashboard-data")
def get_dashboard_data() -> dict[str, object]:
    if market_scheduler is None:
        raise HTTPException(status_code=503, detail="Market scheduler is not initialized")
    return market_scheduler.get_dashboard_data()


def _tail_file(path: Path, lines: int = 200) -> str:
    try:
        with path.open('rb') as f:
            f.seek(0, 2)
            end = f.tell()
            size = 1024
            data = b''
            while lines > 0 and end > 0:
                read_size = min(size, end)
                f.seek(end - read_size)
                chunk = f.read(read_size) + data
                data = chunk
                end -= read_size
                lines = max(0, lines - data.count(b'\n'))
            try:
                return data.decode('utf-8', errors='replace').splitlines()[-200:]
            except Exception:
                return data.decode('utf-8', errors='replace')
    except Exception as exc:
        logger.exception('Failed to tail log file: %s', exc)
        return ''


@app.get('/logs')
def get_logs(name: str = Query('app.log'), lines: int = Query(200)) -> PlainTextResponse:
    # simple log tail endpoint; restrict to files under logs dir
    safe_name = Path(name).name
    path = LOG_DIR / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail='log file not found')
    try:
        # return last N lines
        with path.open('r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
            tail = all_lines[-int(lines):]
            return PlainTextResponse(''.join(tail), status_code=200)
    except Exception as exc:
        logger.exception('Error reading log file: %s', exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.on_event("startup")
async def startup_event() -> None:
    global market_scheduler
    models.Base.metadata.create_all(bind=database.engine)
    market_scheduler = market.MarketScheduler()
    market_scheduler.load_saved_history()
    await market_scheduler.load_initial_history()
    app.state.market_scheduler_task = asyncio.create_task(market_scheduler.run_loop())
    logger.info('MarketScheduler started and task created')


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


@app.post("/api/poll-now")
def poll_now() -> dict[str, object]:
    if market_scheduler is None:
        raise HTTPException(status_code=503, detail="Market scheduler is not initialized")
    # perform immediate poll and gap computation
    try:
        market_scheduler.poll_market()
        market_scheduler._compute_and_store_gap()
        return {"status": "ok", "gap_realtime_len": len(market_scheduler.gap_history)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/cleanup-gaps")
def cleanup_gaps() -> dict[str, object]:
    if market_scheduler is None:
        raise HTTPException(status_code=503, detail="Market scheduler is not initialized")
    try:
        removed = market_scheduler._cleanup_old_gaps()
        return {"status": "ok", "removed": removed}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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
