import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, session
from app.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[session] = override
    # No lifespan: use isolated in-memory data without seeding the on-disk database.
    c = TestClient(app, raise_server_exceptions=True)
    try:
        yield c
    finally:
        c.close()
    app.dependency_overrides.clear()
    engine.dispose()


def portfolio(c):
    r = c.post("/portfolios", json={"name": "Test", "cash": 10000})
    assert r.status_code == 201
    id = r.json()["id"]
    assert (
        c.post(
            f"/portfolios/{id}/positions",
            json={"ticker": "MSFT", "quantity": 10, "cost_basis": 100},
        ).status_code
        == 201
    )
    return id


def test_crud_validation_and_scoping(client):
    c = client
    id = portfolio(c)
    r = c.post(
        f"/portfolios/{id}/positions",
        json={"ticker": "MSFT", "quantity": 10, "cost_basis": 100},
    )
    assert r.status_code == 409
    assert (
        c.post(
            f"/portfolios/{id}/positions",
            json={"ticker": "bad /", "quantity": -1, "cost_basis": 100},
        ).status_code
        == 422
    )
    assert c.post("/portfolios", json={"name": " ", "cash": 0}).status_code == 422
    p = c.get(f"/portfolios/{id}").json()["positions"][0]
    assert (
        c.put(
            f"/portfolios/{id}/positions/{p['id']}",
            json={"ticker": "NVDA", "quantity": 2, "cost_basis": 50},
        ).status_code
        == 200
    )
    other = c.post("/portfolios", json={"name": "Other", "cash": 10}).json()["id"]
    assert c.delete(f"/portfolios/{other}/positions/{p['id']}").status_code == 404
    assert c.delete(f"/portfolios/{id}/positions/{p['id']}").status_code == 204
    assert c.delete(f"/portfolios/{id}").status_code == 204
    assert c.get(f"/portfolios/{id}").status_code == 404


def test_analytics_snapshots_and_changes(client):
    c = client
    id = portfolio(c)
    a = c.get(f"/portfolios/{id}/analytics").json()
    assert a["provenance"]["mode"] == "demo"
    before = c.post(f"/portfolios/{id}/snapshots").json()["id"]
    p = c.get(f"/portfolios/{id}").json()["positions"][0]
    c.put(
        f"/portfolios/{id}/positions/{p['id']}",
        json={"ticker": "MSFT", "quantity": 20, "cost_basis": 100},
    )
    after = c.post(f"/portfolios/{id}/snapshots").json()["id"]
    delta = c.get(f"/portfolios/{id}/changes?before={before}&after={after}")
    assert delta.status_code == 200
    values = [r for r in delta.json()["metrics"] if r["metric"] == "value"][0]
    assert values["delta"] == pytest.approx(a["holdings"][0]["value"])
    assert (
        c.get(f"/portfolios/{id}/changes?before={after}&after={before}").status_code
        == 422
    )
    assert c.get(f"/portfolios/{id}/changes?before=999&after=1000").status_code == 404


def test_research_stress_dcf_and_grounded_analyst(client):
    c = client
    id = portfolio(c)
    f = c.get("/companies/MSFT/fundamentals").json()
    assert f["free_cash_flow"] == pytest.approx(f["operating_cash_flow"] - f["capex"])
    hits = c.get("/companies/MSFT/filings/search?q=risk%20factors").json()["results"]
    assert hits and "ILLUSTRATIVE" in hits[0]["text"] and hits[0]["citation"]
    d = c.post("/valuation/dcf", json={})
    assert d.status_code == 200 and len(d.json()["sensitivity"]) == 5
    assert (
        c.post(
            "/valuation/dcf", json={"wacc": 0.02, "terminal_growth": 0.03}
        ).status_code
        == 422
    )
    s = c.post(
        f"/portfolios/{id}/stress",
        json={"market_shock": 0, "rate_bps": 0, "oil_shock": 0},
    ).json()
    assert s["impact"] == 0
    result = c.post(
        f"/portfolios/{id}/analyst", json={"question": "What are my risks?"}
    ).json()
    assert "portfolio_analytics" == result["tools"][0]["name"]
    a = c.get(f"/portfolios/{id}/analytics").json()
    assert f"${a['var_dollars']:,.2f}" in result["answer"]
    report = c.get(f"/portfolios/{id}/report")
    assert report.status_code == 200 and "synthetic" in report.text.lower()


def test_live_credentials_and_ticker_guard(client, monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    assert client.get("/macro?mode=live").status_code == 502
    assert client.get("/companies/MSFT/fundamentals?mode=live").status_code == 502
    assert client.get("/companies/%24BAD/fundamentals").status_code == 422
    assert client.get("/macro?mode=other").status_code == 422
