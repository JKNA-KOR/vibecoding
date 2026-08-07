from decimal import Decimal

from app.market import MarketAnalyzer, MarketDataProvider


def test_market_data_provider_supports_korean_symbols():
    provider = MarketDataProvider()

    quote_gold = provider.get_real_time_quote("마이크로섹터 금광3배 ETN")
    assert quote_gold.symbol == "마이크로섹터 금광3배 ETN"
    assert quote_gold.price == Decimal("15200.00")

    quote_ace = provider.get_real_time_quote("ACE KRX금현물")
    assert quote_ace.symbol == "ACE KRX금현물"
    assert quote_ace.price == Decimal("62000.00")


def test_market_data_provider_uses_external_api(monkeypatch):
    def fake_get(url, params, timeout, headers=None):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"price": 12345.67}

        assert url == "https://api.example.com/quote"
        assert params["symbol"] == "ACE_KRX_GOLD"
        assert params["api_key"] == "secret-key"
        return FakeResponse()

    monkeypatch.setenv("MARKET_API_PROVIDER", "external")
    monkeypatch.setenv("MARKET_API_URL", "https://api.example.com/quote")
    monkeypatch.setenv("MARKET_API_KEY", "secret-key")
    monkeypatch.setattr("app.market.httpx.get", fake_get)

    provider = MarketDataProvider()
    quote = provider.get_real_time_quote("ACE KRX금현물")
    assert quote.price == Decimal("12345.67")
    assert quote.symbol == "ACE KRX금현물"


def test_market_analyzer_recommendation_for_korean_symbols():
    provider = MarketDataProvider()
    analyzer = MarketAnalyzer(provider)

    result_buy = analyzer.analyze("마이크로섹터 금광3배 ETN", previous_price=Decimal("15000.00"))
    assert result_buy["recommendation"] == "BUY"
    assert "상승세" in result_buy["reason"]

    result_sell = analyzer.analyze("ACE KRX금현물", previous_price=Decimal("65000.00"))
    assert result_sell["recommendation"] == "SELL"
    assert "하락세" in result_sell["reason"]
