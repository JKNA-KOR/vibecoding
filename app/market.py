from __future__ import annotations

import asyncio
import os
import re
import smtplib
import ssl
from collections import deque
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from email.message import EmailMessage
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from . import crud, database, models
from .schemas import QuoteRead


class MarketProviderError(Exception):
    pass


class BaseMarketProvider:
    def get_quote(self, symbol: str) -> QuoteRead:
        raise NotImplementedError


class ExternalMarketApiProvider(BaseMarketProvider):
    def __init__(self, api_url: str, api_key: str | None = None) -> None:
        self.api_url = api_url
        self.api_key = api_key

    def get_quote(self, symbol: str) -> QuoteRead:
        now = datetime.now(timezone.utc)
        params = {"symbol": symbol}
        if self.api_key:
            params["api_key"] = self.api_key

        response = httpx.get(self.api_url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()

        price = data.get("price")
        if price is None:
            raise MarketProviderError("External API did not return a price")

        return QuoteRead(symbol=symbol, price=Decimal(str(price)), timestamp=now)

    def get_historical_quotes(self, symbol: str, days: int = 30) -> list[QuoteRead]:
        raise MarketProviderError("External provider does not support historical quote retrieval")


class YahooFinanceProvider(BaseMarketProvider):
    BASE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
    CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

    def get_quote(self, symbol: str) -> QuoteRead:
        now = datetime.now(timezone.utc)
        response = httpx.get(
            self.BASE_URL,
            params={"symbols": symbol},
            timeout=10.0,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        data = response.json()
        results = data.get("quoteResponse", {}).get("result", [])
        if not results:
            raise MarketProviderError("Yahoo Finance did not return quote data")

        quote_data = results[0]
        price = quote_data.get("regularMarketPrice")
        if price is None:
            raise MarketProviderError("Yahoo Finance quote is missing price")

        return QuoteRead(symbol=symbol, price=Decimal(str(price)), timestamp=now)

    def get_historical_quotes(self, symbol: str, days: int = 30) -> list[QuoteRead]:
        response = httpx.get(
            f"{self.CHART_URL}/{symbol}",
            params={"range": "1mo", "interval": "1d"},
            timeout=10.0,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        data = response.json()
        chart = data.get("chart", {}).get("result")
        if not chart:
            raise MarketProviderError("Yahoo Finance did not return historical chart data")

        quote_data = chart[0]
        timestamps = quote_data.get("timestamp") or []
        indicators = quote_data.get("indicators", {}).get("quote", [{}])[0]
        closes = indicators.get("close", [])
        if not timestamps or not closes:
            raise MarketProviderError("Yahoo Finance historical data is incomplete")

        history: list[QuoteRead] = []
        for timestamp, close in zip(timestamps, closes):
            if close is None:
                continue
            history.append(
                QuoteRead(
                    symbol=symbol,
                    price=Decimal(str(close)),
                    timestamp=datetime.fromtimestamp(timestamp, timezone.utc),
                )
            )

        if not history:
            raise MarketProviderError("Yahoo Finance historical data contained no valid closing prices")

        return history


class NaverMarketProvider(BaseMarketProvider):
    SYMBOL_TO_QUERY: dict[str, str] = {
        "MICROSECTOR_GOLD3X": "GDXU",
        "ACE_KRX_GOLD": "411060",
    }

    FX_QUERY_URL = "https://search.naver.com/search.naver?query=USD+KRW"

    def get_quote(self, symbol: str) -> QuoteRead:
        now = datetime.now(timezone.utc)
        query_symbol = self.SYMBOL_TO_QUERY.get(symbol, symbol)

        if query_symbol == "411060":
            url = f"https://finance.naver.com/item/main.naver?code={query_symbol}"
            response = httpx.get(url, timeout=15.0, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            html = response.text
            match = re.search(r'<p class="no_today">.*?<span class="blind">([^<]+)</span>', html, re.S)
            if not match:
                raise MarketProviderError("Naver item page did not contain expected price")
            price_text = match.group(1).strip()
        else:
            url = f"https://search.naver.com/search.naver?query={query_symbol}"
            response = httpx.get(url, timeout=15.0, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            html = response.text
            match = re.search(r'<strong class="now">현재가</strong>\s*<span class="blind">([^<]+)</span>', html)
            if not match:
                raise MarketProviderError("Naver search page did not contain expected price")
            price_text = match.group(1).strip()

        price_number = re.search(r"[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?", price_text)
        if not price_number:
            raise MarketProviderError("Failed to parse Naver price text")

        price_value = Decimal(price_number.group(0).replace(",", ""))
        return QuoteRead(symbol=symbol, price=price_value, timestamp=now)

    def get_fx_rate(self) -> Decimal:
        response = httpx.get(self.FX_QUERY_URL, timeout=15.0, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        html = response.text
        match = re.search(r'<span class="nb_txt _pronunciation" data-currency-unit="원">\s*([0-9,]+(?:\.[0-9]+)?)\s*원</span>', html)
        if not match:
            raise MarketProviderError("Naver FX 검색 페이지에서 환율을 가져오지 못했습니다")
        return Decimal(match.group(1).replace(",", ""))

    def get_historical_quotes(self, symbol: str, days: int = 30) -> list[QuoteRead]:
        return []


class EmailNotifier:
    def __init__(
        self,
        smtp_server: str | None,
        smtp_port: int,
        username: str | None,
        password: str | None,
        sender: str | None,
        recipient: str | None,
    ) -> None:
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender = sender
        self.recipient = recipient

    def is_configured(self) -> bool:
        return bool(self.smtp_server and self.smtp_port and self.sender and self.recipient)

    def send_email(self, subject: str, body: str) -> None:
        if not self.is_configured():
            return

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.sender
        message["To"] = self.recipient
        message.set_content(body)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context) as smtp:
            if self.username and self.password:
                smtp.login(self.username, self.password)
            smtp.send_message(message)


class MarketDataProvider:
    SYMBOL_ALIASES: dict[str, str] = {
        "마이크로섹터 금광3배 ETN": "MICROSECTOR_GOLD3X",
        "마이크로섹터금광3배ETN": "MICROSECTOR_GOLD3X",
        "ACE KRX금현물": "ACE_KRX_GOLD",
        "ACE KRX 금현물": "ACE_KRX_GOLD",
        "ACE XRX금현물": "ACE_KRX_GOLD",
        "ACE_XRX_GOLD": "ACE_KRX_GOLD",
        "MICROSECTOR_GOLD3X": "MICROSECTOR_GOLD3X",
        "ACE_KRX_GOLD": "ACE_KRX_GOLD",
        "KODEXGOLD": "KODEXGOLD",
    }

    FALLBACK_PRICES: dict[str, Decimal] = {
        "MICROSECTOR_GOLD3X": Decimal("15200.00"),
        "ACE_KRX_GOLD": Decimal("62000.00"),
        "KODEXGOLD": Decimal("500.00"),
    }

    def __init__(self) -> None:
        self.provider = self._select_provider()

    def _select_provider(self) -> BaseMarketProvider:
        provider_name = os.getenv("MARKET_API_PROVIDER", "naver").strip().lower()
        api_url = os.getenv("MARKET_API_URL")
        api_key = os.getenv("MARKET_API_KEY")

        if provider_name == "yahoo":
            return YahooFinanceProvider()

        if provider_name == "naver":
            return NaverMarketProvider()

        if provider_name in {"external", "api"} and api_url:
            return ExternalMarketApiProvider(api_url, api_key)

        if api_url:
            return ExternalMarketApiProvider(api_url, api_key)

        return NaverMarketProvider()

    def normalize_symbol(self, symbol: str) -> str:
        cleaned = symbol.strip()
        if cleaned in self.SYMBOL_ALIASES:
            return self.SYMBOL_ALIASES[cleaned]
        return cleaned.upper()

    def get_real_time_quote(self, symbol: str) -> QuoteRead:
        normalized_symbol = self.normalize_symbol(symbol)
        try:
            quote = self.provider.get_quote(normalized_symbol)
            return QuoteRead(symbol=symbol, price=quote.price, timestamp=quote.timestamp)
        except Exception:
            return self._get_fallback_quote(normalized_symbol, symbol)

    def get_quote(self, symbol: str) -> QuoteRead:
        return self.get_real_time_quote(symbol)

    def get_fx_rate(self) -> Decimal:
        if hasattr(self.provider, "get_fx_rate"):
            try:
                return self.provider.get_fx_rate()
            except Exception:
                pass
        return Decimal("1300.00")

    def get_historical_quotes(self, symbol: str, days: int = 30) -> list[QuoteRead]:
        normalized_symbol = self.normalize_symbol(symbol)
        if hasattr(self.provider, "get_historical_quotes"):
            try:
                return self.provider.get_historical_quotes(normalized_symbol, days=days)
            except Exception:
                pass
        return []

    def _get_fallback_quote(self, normalized_symbol: str, original_symbol: str) -> QuoteRead:
        now = datetime.now(timezone.utc)
        price = self.FALLBACK_PRICES.get(normalized_symbol, Decimal("1000.00"))
        return QuoteRead(symbol=original_symbol, price=price, timestamp=now)


class MarketAnalyzer:
    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    def analyze(self, symbol: str, previous_price: Decimal | None = None) -> dict[str, Any]:
        quote = self.provider.get_real_time_quote(symbol)
        recommendation = "HOLD"
        reason = "데이터가 충분하지 않아 신중하게 접근하세요."

        if previous_price is not None:
            if quote.price > previous_price:
                recommendation = "BUY"
                reason = "최근 가격이 상승세여서 매수 타이밍으로 판단됩니다."
            elif quote.price < previous_price:
                recommendation = "SELL"
                reason = "최근 가격이 하락세여서 매도 타이밍으로 판단됩니다."
            else:
                recommendation = "HOLD"
                reason = "가격 변화가 크지 않아 관망이 적절합니다."
        else:
            if quote.price >= Decimal("50000"):
                recommendation = "SELL"
                reason = "현재 가격이 비교적 높아 매도 검토가 가능합니다."
            elif quote.price <= Decimal("20000"):
                recommendation = "BUY"
                reason = "현재 가격이 비교적 낮아 매수 기회로 보입니다."
            else:
                recommendation = "HOLD"
                reason = "중립적인 가격대이므로 추가 정보를 확인하세요."

        return {
            "quote": quote,
            "recommendation": recommendation,
            "reason": reason,
        }


class PricePredictor:
    @staticmethod
    def predict_price(history: deque[QuoteRead]) -> tuple[Decimal | None, str, str]:
        if len(history) < 2:
            return None, "HOLD", "가격 히스토리가 부족해 예측이 불가합니다."

        last_price = history[-1].price
        previous_price = history[-2].price
        if previous_price == 0:
            return None, "HOLD", "이전 가격 데이터가 유효하지 않습니다."

        change = (last_price - previous_price) / previous_price
        predicted_price = last_price * (Decimal("1.0") + change)

        if change > Decimal("0.001"):
            signal = "BUY"
            reason = "최근 상승 추세가 계속되면 추가 매수 기회가 될 수 있습니다."
        elif change < Decimal("-0.001"):
            signal = "SELL"
            reason = "최근 하락 추세가 계속되면 매도 검토가 필요합니다."
        else:
            signal = "HOLD"
            reason = "가격 변동이 작아 관망이 타당합니다."

        return predicted_price.quantize(Decimal("0.01")), signal, reason

    @staticmethod
    def predict_spot_from_etf(etf_history: deque[QuoteRead], spot_history: deque[QuoteRead]) -> tuple[Decimal | None, str, str]:
        if len(etf_history) < 2 or len(spot_history) < 1:
            return None, "HOLD", "금광 ETN과 금현물 가격 데이터가 충분하지 않습니다."

        etf_last = etf_history[-1].price
        etf_prev = etf_history[-2].price
        spot_last = spot_history[-1].price

        if etf_prev == 0 or spot_last == 0:
            return None, "HOLD", "이전 가격 데이터가 유효하지 않습니다."

        etf_delta = (etf_last - etf_prev) / etf_prev
        predicted_price = spot_last * (Decimal("1.0") + etf_delta / Decimal("3"))

        if etf_delta > Decimal("0.001"):
            signal = "BUY"
            reason = "금광3배 ETN이 선행 상승 신호를 보여 금현물 상승 가능성이 높아 보입니다."
        elif etf_delta < Decimal("-0.001"):
            signal = "SELL"
            reason = "금광3배 ETN이 선행 하락 신호를 보여 금현물 조정 가능성이 높아 보입니다."
        else:
            signal = "HOLD"
            reason = "금광3배 ETN의 움직임이 약해 금현물 관망이 유효합니다."

        return predicted_price.quantize(Decimal("0.01")), signal, reason


class MarketScheduler:
    DEFAULT_SYMBOLS = ["마이크로섹터 금광3배 ETN", "ACE KRX금현물"]

    def __init__(self) -> None:
        raw_symbols = os.getenv("MARKET_POLL_SYMBOLS", ",".join(self.DEFAULT_SYMBOLS))
        self.symbols = [symbol.strip() for symbol in raw_symbols.split(",") if symbol.strip()]
        self.poll_interval_seconds = int(os.getenv("MARKET_POLL_INTERVAL_SECONDS", "300"))
        self.email_interval_seconds = int(os.getenv("EMAIL_REPORT_INTERVAL_SECONDS", "3600"))
        self.initial_history_days = int(os.getenv("MARKET_HISTORY_DAYS", "30"))
        self.history_maxlen = int(os.getenv("MARKET_HISTORY_MAXLEN", "1440"))
        self.recipient = os.getenv("EMAIL_RECIPIENT", "bonapart97@gmail.com")
        self.sender = os.getenv("EMAIL_SENDER")
        self.smtp_server = os.getenv("EMAIL_SMTP_SERVER")
        self.smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "465"))
        self.smtp_username = os.getenv("EMAIL_SMTP_USERNAME")
        self.smtp_password = os.getenv("EMAIL_SMTP_PASSWORD")

        self.provider = MarketDataProvider()
        self.notifier = EmailNotifier(
            smtp_server=self.smtp_server,
            smtp_port=self.smtp_port,
            username=self.smtp_username,
            password=self.smtp_password,
            sender=self.sender,
            recipient=self.recipient,
        )
        self.history: dict[str, deque[QuoteRead]] = {
            self.normalize_symbol(symbol): deque(maxlen=self.history_maxlen) for symbol in self.symbols
        }
        self.latest_quotes: dict[str, QuoteRead] = {}
        self.db_session_factory = database.SessionLocal

    def normalize_symbol(self, symbol: str) -> str:
        return self.provider.normalize_symbol(symbol)

    def get_historical_quotes(self, symbol: str, days: int = 30) -> list[QuoteRead]:
        normalized_symbol = self.normalize_symbol(symbol)
        try:
            history = self.provider.get_historical_quotes(normalized_symbol, days=days)
        except Exception:
            return self._build_synthetic_history(symbol, days)

        if len(history) < days:
            history = self._fill_missing_history(symbol, history, days)

        return history

    def save_market_quote(self, quote: QuoteRead) -> None:
        db = self.db_session_factory()
        try:
            crud.create_market_quote(db, symbol=quote.symbol, price=quote.price, timestamp=quote.timestamp)
        finally:
            db.close()

    def load_saved_history(self) -> None:
        for symbol in self.symbols:
            normalized = self.normalize_symbol(symbol)
            db = self.db_session_factory()
            try:
                saved_quotes = crud.list_market_quotes(db, symbol=symbol, limit=self.history_maxlen)
            finally:
                db.close()
            if saved_quotes:
                if normalized not in self.history:
                    self.history[normalized] = deque(maxlen=self.history_maxlen)
                for model_quote in reversed(saved_quotes):
                    self.history[normalized].append(
                        QuoteRead(
                            symbol=model_quote.symbol,
                            price=model_quote.price,
                            timestamp=model_quote.timestamp,
                        )
                    )

    def _build_synthetic_history(self, symbol: str, days: int) -> list[QuoteRead]:
        now = datetime.now(timezone.utc)
        current = self.provider.get_quote(self.normalize_symbol(symbol)).price
        result: list[QuoteRead] = []
        for day_delta in range(days, 0, -1):
            timestamp = now - timedelta(days=day_delta)
            variation = Decimal(str((day_delta - days / 2) / max(days, 1) * 0.01))
            price = (current * (Decimal("1.0") + variation)).quantize(Decimal("0.01"))
            result.append(QuoteRead(symbol=symbol, price=price, timestamp=timestamp))
        return result

    def _fill_missing_history(self, symbol: str, history: list[QuoteRead], days: int) -> list[QuoteRead]:
        if len(history) >= days:
            return history

        now = datetime.now(timezone.utc)
        history_map = {quote.timestamp.date(): quote for quote in history}
        filled: list[QuoteRead] = []
        current = history[-1].price if history else self.provider.get_quote(self.normalize_symbol(symbol)).price
        for day_delta in range(days, 0, -1):
            candidate_date = (now - timedelta(days=day_delta)).date()
            if candidate_date in history_map:
                filled.append(history_map[candidate_date])
                continue
            variation = Decimal(str((day_delta - days / 2) / max(days, 1) * 0.01))
            price = (current * (Decimal("1.0") + variation)).quantize(Decimal("0.01"))
            filled.append(QuoteRead(symbol=symbol, price=price, timestamp=datetime.combine(candidate_date, datetime.min.time(), tzinfo=timezone.utc)))
        return filled

    def poll_market(self) -> None:
        for symbol in self.symbols:
            quote = self.provider.get_real_time_quote(symbol)
            normalized = self.normalize_symbol(symbol)
            self.latest_quotes[symbol] = quote
            if normalized not in self.history:
                self.history[normalized] = deque(maxlen=self.history_maxlen)
            self.history[normalized].append(quote)
            self.save_market_quote(quote)

    async def load_initial_history(self) -> None:
        self.load_saved_history()
        for symbol in self.symbols:
            normalized = self.normalize_symbol(symbol)
            if self.history.get(normalized):
                continue
            oldest_quotes = self.get_historical_quotes(symbol, days=self.initial_history_days)
            if normalized not in self.history:
                self.history[normalized] = deque(maxlen=self.history_maxlen)
            for quote in oldest_quotes:
                self.history[normalized].append(quote)

    def get_dashboard_data(self) -> dict[str, object]:
        fx_rate = self.provider.get_fx_rate()
        series: dict[str, list[dict[str, object]]] = {}
        gold_alias = self.provider.normalize_symbol(self.DEFAULT_SYMBOLS[0])
        for symbol in self.symbols:
            normalized = self.normalize_symbol(symbol)
            history = self.history.get(normalized, deque())
            if normalized == gold_alias:
                series[normalized] = [
                    {
                        "symbol": symbol,
                        "price": float((quote.price * fx_rate / Decimal("10")).quantize(Decimal("0.01"))),
                        "timestamp": quote.timestamp.isoformat(),
                    }
                    for quote in history
                ]
            else:
                series[normalized] = [
                    {
                        "symbol": symbol,
                        "price": float(quote.price),
                        "timestamp": quote.timestamp.isoformat(),
                    }
                    for quote in history
                ]

        prediction_symbol = "ACE KRX금현물"
        normalized = self.normalize_symbol(prediction_symbol)
        history = self.history.get(normalized, deque())
        gold_history = self.history.get(gold_alias, deque())
        predicted_price, signal, reason = PricePredictor.predict_spot_from_etf(gold_history, history)
        future_point = None
        if predicted_price is not None and history:
            future_point = {
                "symbol": prediction_symbol,
                "price": float(predicted_price),
                "timestamp": (history[-1].timestamp + timedelta(days=1)).isoformat(),
            }

        latest_quotes = {}
        ace_latest_price = None
        for symbol, quote in self.latest_quotes.items():
            if symbol == self.DEFAULT_SYMBOLS[0]:
                krw_price = (quote.price * fx_rate).quantize(Decimal("0.01"))
                latest_quotes[symbol] = {
                    "price_usd": float(quote.price),
                    "krw_price": float(krw_price),
                    "krw_price_div10": float((krw_price / Decimal("10")).quantize(Decimal("0.01"))),
                    "fx_rate": float(fx_rate),
                    "timestamp": quote.timestamp.isoformat(),
                }
            elif symbol == prediction_symbol:
                ace_latest_price = quote.price
                latest_quotes[symbol] = {
                    "price": float(quote.price),
                    "timestamp": quote.timestamp.isoformat(),
                }
            else:
                latest_quotes[symbol] = {
                    "price": float(quote.price),
                    "timestamp": quote.timestamp.isoformat(),
                }

        gap_percent = None
        if self.DEFAULT_SYMBOLS[0] in latest_quotes and ace_latest_price is not None:
            gold_etf_div10 = Decimal(str(latest_quotes[self.DEFAULT_SYMBOLS[0]]['krw_price_div10']))
            if ace_latest_price > 0:
                gap_percent = float(((gold_etf_div10 - Decimal(str(ace_latest_price))) / Decimal(str(ace_latest_price)) * Decimal('100')).quantize(Decimal('0.01')))

        return {
            "series": series,
            "fx_rate": float(fx_rate),
            "latest_quotes": latest_quotes,
            "prediction": {
                "symbol": prediction_symbol,
                "predicted_price": float(predicted_price) if predicted_price is not None else None,
                "recommendation": signal,
                "reason": reason,
                "future_point": future_point,
                "gap_percent": gap_percent,
                "gap_description": self._describe_gap(gap_percent),
            },
        }

    def _describe_gap(self, gap_percent: float | None) -> str:
        if gap_percent is None:
            return "갭 정보를 계산할 수 없습니다."
        if gap_percent >= 0:
            return "금현물이 금광 ETN 대비 과도하게 강세입니다."
        return "금현물이 금광 ETN 대비 과도하게 약세입니다."

    def build_report(self) -> str:
        lines: list[str] = [
            "[실시간 시세 리포트]",
            f"생성시간: {datetime.now(timezone.utc).isoformat()}",
            "",
        ]

        for symbol, quote in self.latest_quotes.items():
            lines.append(f"종목: {symbol}")
            lines.append(f"현재가: {quote.price}")
            lines.append(f"조회시간: {quote.timestamp.isoformat()}")
            lines.append("")

        prediction_symbol = "ACE KRX금현물"
        normalized = self.normalize_symbol(prediction_symbol)
        history = self.history.get(normalized, deque())
        predicted_price, signal, reason = PricePredictor.predict_price(history)

        lines.append("[ACE KRX금현물 가격 예측]")
        if predicted_price is not None:
            lines.append(f"예측 가격: {predicted_price}")
            lines.append(f"추천: {signal}")
            lines.append(f"사유: {reason}")
        else:
            lines.append(reason)

        lines.append("")
        lines.append("[매수/매도 시점 알림]")
        previous_price = history[-2].price if len(history) >= 2 else None
        analysis = MarketAnalyzer(self.provider).analyze(prediction_symbol, previous_price)
        lines.append(f"추천: {analysis['recommendation']}")
        lines.append(f"사유: {analysis['reason']}")

        return "\n".join(lines)

    async def run_loop(self) -> None:
        next_email_time = datetime.now(timezone.utc) + timedelta(seconds=self.email_interval_seconds)
        while True:
            try:
                self.poll_market()
                now = datetime.now(timezone.utc)
                if now >= next_email_time:
                    report = self.build_report()
                    if self.notifier.is_configured():
                        try:
                            self.notifier.send_email("ACE KRX금현물 시세 및 추천 리포트", report)
                        except Exception:
                            pass
                    next_email_time = now + timedelta(seconds=self.email_interval_seconds)
            except Exception:
                pass
            await asyncio.sleep(self.poll_interval_seconds)
