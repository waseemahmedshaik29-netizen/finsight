import json
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import analyst, data
from app.db import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_live_price_parse_alignment_and_cache(db, monkeypatch):
    dates = data.pd.bdate_range("2025-01-01", periods=40)
    response = Mock(
        text="Date,Close\n"
        + "\n".join(f"{d.date()},{100 + i}" for i, d in enumerate(dates))
    )
    get = Mock(return_value=response)
    monkeypatch.setattr(data, "request", get)
    prices, source = data.market(db, ["MSFT", "SPY"], "live")
    assert len(prices) == 40 and source["mode"] == "live"
    data.market(db, ["MSFT", "SPY"], "live")
    assert get.call_count == 2
    monkeypatch.setattr(data, "request", lambda *a, **kw: Mock(text="No data"))
    with pytest.raises(data.DataError):
        data.market(db, ["XYZ"], "live")


def test_macro_skips_missing_and_preserves_dates(db, monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "unit-test-not-a-secret")
    monkeypatch.setattr(
        data,
        "request",
        lambda *a, **kw: Mock(
            json=lambda: {
                "observations": [
                    {"value": ".", "date": "2026-01-02"},
                    {"value": "4.2", "date": "2026-01-01"},
                ]
            }
        ),
    )
    result = data.macro(db, "live")
    assert len(result["series"]) == 4 and result["series"][0]["date"] == "2026-01-01"
    assert result["series"][0]["value"] == 4.2


def test_sec_annual_fact_filter_and_period_mismatch(db, monkeypatch):
    monkeypatch.setattr(data, "cik_for", lambda db, ticker: "0000000001")

    def tag(value, start="2025-01-01", end="2025-12-31", form="10-K"):
        return {
            "units": {
                "USD": [
                    {
                        "val": value,
                        "start": start,
                        "end": end,
                        "form": form,
                        "filed": "2026-02-01",
                    }
                ]
            }
        }

    facts = {
        "entityName": "Example issuer",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "val": 100,
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "form": "10-K",
                                "filed": "2026-02-01",
                            },
                            {
                                "val": 30,
                                "start": "2025-10-01",
                                "end": "2025-12-31",
                                "form": "10-K",
                                "filed": "2026-02-01",
                            },
                        ]
                    }
                },
                "OperatingIncomeLoss": tag(20),
                "NetCashProvidedByUsedInOperatingActivities": tag(25),
                "PaymentsToAcquirePropertyPlantAndEquipment": tag(
                    5, start="2024-01-01", end="2024-12-31"
                ),
            }
        },
    }
    monkeypatch.setattr(data, "request", lambda *a, **kw: Mock(json=lambda: facts))
    f = data.fundamentals(db, "MSFT", "live")
    assert f["revenue"] == 100 and f["operating_margin"] == 0.2
    assert f["free_cash_flow"] is None and f["equity"] is None


def test_filing_chunk_citation_and_no_match():
    fixture = {
        "documents": [
            {
                "id": "example",
                "form": "10-K",
                "date": "2025-01-01",
                "url": "https://www.sec.gov/",
                "text": "a" * 1500 + " material liquidity risk " + "b" * 1000,
            }
        ]
    }
    hits = data.search_filings(fixture, "liquidity risk")
    assert hits and hits[0]["document_id"] == "example" and hits[0]["offset"] == 1000
    assert not data.search_filings(fixture, "unmatchedkeyword")


def test_model_plan_validated_and_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-not-a-secret")
    monkeypatch.setenv("OPENAI_MODEL", "unit-test-model")
    plan = analyst.Plan(company_ticker="MSFT", filing_query="risk").model_dump()
    response = Mock()
    response.json.return_value = {
        "output": [
            {
                "type": "function_call",
                "name": "plan_research",
                "arguments": json.dumps(plan),
            }
        ]
    }
    post = Mock(return_value=response)
    monkeypatch.setattr(analyst.httpx, "post", post)
    actual, engine, warning = analyst.choose_plan(
        "MSFT filing risks", {"MSFT": 0.5}, True
    )
    assert actual.company_ticker == "MSFT" and warning is None
    assert "OpenAI" in engine and post.call_args.kwargs["json"]["store"] is False
    plan["company_ticker"] = "EVIL"
    response.json.return_value = {
        "output": [
            {
                "type": "function_call",
                "name": "plan_research",
                "arguments": json.dumps(plan),
            }
        ]
    }
    actual, engine, warning = analyst.choose_plan(
        "MSFT filing risks", {"MSFT": 0.5}, True
    )
    assert (
        warning
        and actual.company_ticker == "MSFT"
        and engine == "deterministic tool analyst"
    )


def test_model_absent_is_local_and_does_not_call_network(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    post = Mock()
    monkeypatch.setattr(analyst.httpx, "post", post)
    plan, engine, warning = analyst.choose_plan("What changed?", {"MSFT": 0.5}, True)
    assert warning and plan.include_changes and not post.called


def test_alpha_vantage_compact_and_quota_errors(db, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "alphavantage")
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "unit-test-not-a-secret")
    rows = {
        str(d.date()): {"4. close": str(100 + i)}
        for i, d in enumerate(data.pd.bdate_range("2025-01-01", periods=40))
    }
    monkeypatch.setattr(
        data,
        "request",
        lambda *a, **kw: Mock(json=lambda: {"Time Series (Daily)": rows}),
    )
    frame, source = data.market(db, ["SPY"], "live")
    assert len(frame) == 40 and "Alpha Vantage" in source["source"]
    monkeypatch.setattr(
        data,
        "request",
        lambda *a, **kw: Mock(json=lambda: {"Information": "quota exhausted"}),
    )
    with pytest.raises(data.DataError, match="quota"):
        data.market(db, ["MSFT"], "live")


def test_malformed_macro_response_is_source_error(db, monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "unit-test-not-a-secret")
    monkeypatch.setattr(
        data, "request", lambda *a, **kw: Mock(json=lambda: {"unexpected": []})
    )
    with pytest.raises(data.DataError, match="unexpected response"):
        data.macro(db, "live")


def test_http_error_names_provider_without_exposing_key(monkeypatch):
    import httpx

    request = httpx.Request("GET", "https://stooq.com/q/d/l/?apikey=private")
    response = httpx.Response(404, request=request)
    monkeypatch.setattr(data.httpx, "get", lambda *args, **kwargs: response)
    with pytest.raises(data.DataError) as error:
        data.request("https://stooq.com/q/d/l/", {"apikey": "private"})
    assert "stooq.com returned HTTP 404" in str(error.value)
    assert "alphavantage" in str(error.value)
    assert "private" not in str(error.value)
