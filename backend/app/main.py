import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from .analyst import choose_plan
from .analytics import analyze, dcf, sensitivity
from .data import (
    COMPANIES,
    DataError,
    filings,
    fundamentals,
    macro,
    market,
    search_filings,
)
from .db import Base, Portfolio, Position, Session, Snapshot, engine, session

Mode = Literal["demo", "live"]
Ticker = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9.\-]{0,11}$")]
DB = Annotated[DBSession, Depends(session)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PortfolioInput(Input):
    name: str = Field(min_length=1, max_length=100)
    benchmark: Ticker = "SPY"
    cash: float = Field(default=0, ge=0, le=1e12)

    @field_validator("name")
    @classmethod
    def name_valid(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be blank")
        return v.strip()


class PositionInput(Input):
    ticker: Ticker
    quantity: float = Field(gt=0, le=1e9)
    cost_basis: float = Field(ge=0, le=1e7)


class DCFInput(Input):
    revenue: float = Field(default=100e9, gt=0, le=1e14)
    growth: float = Field(default=0.08, ge=-0.5, le=1)
    margin: float = Field(default=0.25, ge=-1, le=1)
    tax_rate: float = Field(default=0.21, ge=0, le=1)
    da_ratio: float = Field(default=0.03, ge=0, le=1)
    capex_ratio: float = Field(default=0.06, ge=0, le=1)
    working_capital_ratio: float = Field(default=0.1, ge=0, le=1)
    wacc: float = Field(default=0.09, gt=0, le=0.5)
    terminal_growth: float = Field(default=0.025, ge=-0.1, le=0.1)
    net_debt: float = Field(default=10e9, ge=-1e13, le=1e13)
    shares: float = Field(default=3e9, gt=0, le=1e13)

    @model_validator(mode="after")
    def spread(self):
        if self.wacc <= self.terminal_growth:
            raise ValueError("WACC must exceed terminal growth")
        return self


class StressInput(Input):
    market_shock: float = Field(default=-0.2, ge=-1, le=1)
    rate_bps: float = Field(default=100, ge=-1000, le=1000)
    oil_shock: float = Field(default=-0.25, ge=-1, le=1)


class AnalystInput(Input):
    question: str = Field(min_length=3, max_length=2000)
    use_model: bool = False


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with Session() as db:
        if not db.scalars(select(Portfolio)).first():
            p = Portfolio(name="Core conviction", benchmark="SPY", cash=10000)
            db.add(p)
            db.flush()
            for t, q, c in [
                ("MSFT", 60, 320),
                ("NVDA", 150, 90),
                ("JPM", 90, 170),
                ("XOM", 130, 98),
                ("WMT", 150, 65),
            ]:
                db.add(Position(portfolio_id=p.id, ticker=t, quantity=q, cost_basis=c))
            db.commit()
    yield


app = FastAPI(title="FinSight intelligence API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(DataError)
async def source_error(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def calculation_error(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=422, content={"detail": str(exc)})


def get_portfolio(db, id):
    p = db.get(Portfolio, id)
    if not p:
        raise HTTPException(404, "Portfolio not found")
    return p


def serialize(p):
    return {
        "id": p.id,
        "name": p.name,
        "benchmark": p.benchmark,
        "cash": p.cash,
        "positions": [
            {
                "id": x.id,
                "ticker": x.ticker,
                "quantity": x.quantity,
                "cost_basis": x.cost_basis,
            }
            for x in p.positions
        ],
    }


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "This ticker already exists in the portfolio"
        ) from None


def portfolio_analysis(db, id, mode):
    p = get_portfolio(db, id)
    prices, provenance = market(
        db, [x.ticker for x in p.positions] + [p.benchmark], mode
    )
    result = analyze(
        prices, {x.ticker: x.quantity for x in p.positions}, p.cash, p.benchmark
    )
    result.update(
        {
            "portfolio": serialize(p),
            "provenance": provenance,
            "methodology": "Constant current share quantities held over entire sample; cash earns zero; no transaction history. Risk-free rate 4% annual assumption. Historical one-day 95% VaR/CVaR. Alpha is annualized arithmetic CAPM intercept.",
        }
    )
    holdings = []
    for x in p.positions:
        price = float(prices[x.ticker].iloc[-1])
        value = price * x.quantity
        holdings.append(
            {
                "id": x.id,
                "ticker": x.ticker,
                "name": COMPANIES.get(x.ticker, (x.ticker, "Other"))[0],
                "sector": COMPANIES.get(x.ticker, (x.ticker, "Other"))[1],
                "quantity": x.quantity,
                "cost_basis": x.cost_basis,
                "price": price,
                "value": value,
                "weight": value / result["value"],
                "pnl": value - x.quantity * x.cost_basis,
            }
        )
    result["holdings"] = holdings
    return result


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/portfolios")
def list_portfolios(db: DB):
    return [serialize(p) for p in db.scalars(select(Portfolio).order_by(Portfolio.id))]


@app.post("/portfolios", status_code=201)
def create_portfolio(body: PortfolioInput, db: DB):
    p = Portfolio(**body.model_dump())
    db.add(p)
    db.commit()
    return serialize(p)


@app.get("/portfolios/{id}")
def detail(id: int, db: DB):
    return serialize(get_portfolio(db, id))


@app.put("/portfolios/{id}")
def update(id: int, body: PortfolioInput, db: DB):
    p = get_portfolio(db, id)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return serialize(p)


@app.delete("/portfolios/{id}", status_code=204)
def delete(id: int, db: DB):
    db.delete(get_portfolio(db, id))
    db.commit()


@app.post("/portfolios/{id}/positions", status_code=201)
def add_position(id: int, body: PositionInput, db: DB):
    get_portfolio(db, id)
    x = Position(portfolio_id=id, **body.model_dump())
    db.add(x)
    commit(db)
    return {"id": x.id}


@app.put("/portfolios/{id}/positions/{position_id}")
def update_position(id: int, position_id: int, body: PositionInput, db: DB):
    x = db.get(Position, position_id)
    if not x or x.portfolio_id != id:
        raise HTTPException(404, "Position not found")
    for k, v in body.model_dump().items():
        setattr(x, k, v)
    commit(db)
    return {"id": x.id}


@app.delete("/portfolios/{id}/positions/{position_id}", status_code=204)
def remove_position(id: int, position_id: int, db: DB):
    x = db.get(Position, position_id)
    if not x or x.portfolio_id != id:
        raise HTTPException(404, "Position not found")
    db.delete(x)
    db.commit()


@app.get("/portfolios/{id}/analytics")
def analytics(id: int, db: DB, mode: Mode = "demo"):
    return portfolio_analysis(db, id, mode)


@app.post("/portfolios/{id}/ingest")
def ingest(id: int, db: DB, mode: Mode = "demo"):
    a = portfolio_analysis(db, id, mode)
    return {
        "provenance": a["provenance"],
        "observations": a["observations"],
        "tickers": list(a["weights"]),
    }


@app.get("/macro")
def macro_data(db: DB, mode: Mode = "demo"):
    return macro(db, mode)


@app.get("/companies/{ticker}/fundamentals")
def company(ticker: Ticker, db: DB, mode: Mode = "demo"):
    return fundamentals(db, ticker, mode)


@app.get("/companies/{ticker}/filings")
def company_filings(ticker: Ticker, db: DB, mode: Mode = "demo"):
    data = filings(db, ticker, mode)
    return {
        **data,
        "documents": [
            {k: v for k, v in d.items() if k != "text"} for d in data["documents"]
        ],
    }


@app.get("/companies/{ticker}/filings/search")
def filing_search(
    ticker: Ticker,
    db: DB,
    q: str = Query(min_length=3, max_length=300),
    mode: Mode = "demo",
):
    data = filings(db, ticker, mode)
    return {
        "mode": mode,
        "results": search_filings(data, q),
        "method": "Deterministic lexical chunk retrieval; offsets refer to normalized cached text",
    }


@app.post("/valuation/dcf")
def valuation(body: DCFInput):
    inputs = body.model_dump()
    return {
        **dcf(inputs),
        "sensitivity": sensitivity(inputs),
        "growth_columns": [0.01, 0.02, 0.03, 0.04],
        "inputs": inputs,
    }


@app.post("/portfolios/{id}/stress")
def stress(id: int, body: StressInput, db: DB, mode: Mode = "demo"):
    a = portfolio_analysis(db, id, mode)
    rows = []
    for h in a["holdings"]:
        # Explicit sector heuristics, not estimated macro causality.
        duration = {
            "Technology": 6,
            "Financials": 2,
            "Energy": 1,
            "Consumer staples": 3,
        }.get(h["sector"], 3)
        shock = max(
            -1,
            min(
                1,
                (a["beta"] or 0) * body.market_shock
                - duration * body.rate_bps / 10000
                + (body.oil_shock * 0.6 if h["sector"] == "Energy" else 0),
            ),
        )
        rows.append(
            {"ticker": h["ticker"], "shock": shock, "impact": h["value"] * shock}
        )
    impact = sum(r["impact"] for r in rows)
    return {
        "impact": impact,
        "return": impact / a["value"],
        "positions": rows,
        "assumptions": body.model_dump(),
        "method": "Illustrative linear sector-duration heuristic using portfolio beta; no causal forecast or historical crisis replay",
        "provenance": a["provenance"],
    }


def capture(db, id, mode):
    a = portfolio_analysis(db, id, mode)
    try:
        m = macro(db, mode)
    except DataError as e:
        m = {"series": [], "error": str(e)}
    filing_ids = {}
    filing_errors = {}
    if mode == "demo" or os.getenv("SEC_USER_AGENT"):
        for h in a["holdings"]:
            try:
                filing_ids[h["ticker"]] = [
                    d["id"] for d in filings(db, h["ticker"], mode)["documents"]
                ]
            except DataError as exc:
                filing_errors[h["ticker"]] = str(exc)
    if mode == "live" and not os.getenv("SEC_USER_AGENT"):
        filing_errors = {
            h["ticker"]: "SEC_USER_AGENT missing; filing IDs not captured"
            for h in a["holdings"]
        }
    if m.get("error"):
        filing_errors["_macro"] = m["error"]
    return {
        "analytics": a,
        "macro": m,
        "filing_ids": filing_ids,
        "filing_errors": filing_errors,
        "mode": mode,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/portfolios/{id}/snapshots", status_code=201)
def snapshot(id: int, db: DB, mode: Mode = "demo"):
    s = Snapshot(portfolio_id=id, payload=capture(db, id, mode))
    db.add(s)
    db.commit()
    return {
        "id": s.id,
        "created_at": s.created_at.replace(tzinfo=timezone.utc).isoformat(),
        "mode": mode,
    }


@app.get("/portfolios/{id}/snapshots")
def snapshots(id: int, db: DB):
    get_portfolio(db, id)
    return [
        {
            "id": s.id,
            "created_at": s.created_at.replace(tzinfo=timezone.utc).isoformat(),
            "mode": s.payload["mode"],
            "value": s.payload["analytics"]["value"],
        }
        for s in db.scalars(
            select(Snapshot)
            .where(Snapshot.portfolio_id == id)
            .order_by(Snapshot.id.desc())
        )
    ]


@app.get("/portfolios/{id}/changes")
def changes(id: int, db: DB, before: int, after: int):
    get_portfolio(db, id)
    left = db.get(Snapshot, before)
    right = db.get(Snapshot, after)
    if not left or not right or left.portfolio_id != id or right.portfolio_id != id:
        raise HTTPException(404, "Snapshot not found in this portfolio")
    if before >= after:
        raise HTTPException(422, "Choose an earlier baseline and a later comparison")
    if left.payload["mode"] != right.payload["mode"]:
        raise HTTPException(422, "Cannot compare demo and live snapshots")
    a = left.payload["analytics"]
    b = right.payload["analytics"]
    metrics = []
    for key in [
        "value",
        "total_return",
        "volatility",
        "beta",
        "var_dollars",
        "max_drawdown",
    ]:
        if a[key] is not None and b[key] is not None:
            metrics.append(
                {
                    "metric": key,
                    "before": a[key],
                    "after": b[key],
                    "delta": b[key] - a[key],
                }
            )
    allocation = [
        {
            "ticker": t,
            "before": a["weights"].get(t, 0),
            "after": b["weights"].get(t, 0),
            "delta": b["weights"].get(t, 0) - a["weights"].get(t, 0),
        }
        for t in sorted(set(a["weights"]) | set(b["weights"]))
    ]
    oldmacro = {s["id"]: s for s in left.payload["macro"]["series"]}
    macro_changes = [
        {
            "series": s["id"],
            "before": oldmacro[s["id"]]["value"],
            "after": s["value"],
            "delta": s["value"] - oldmacro[s["id"]]["value"],
            "unit": s["unit"],
        }
        for s in right.payload["macro"]["series"]
        if s["id"] in oldmacro
    ]
    new_filings = [
        {"ticker": t, "id": f}
        for t, docs in right.payload["filing_ids"].items()
        for f in docs
        if t in left.payload["filing_ids"] and f not in left.payload["filing_ids"][t]
    ]
    return {
        "before": before,
        "after": after,
        "metrics": metrics,
        "allocation": allocation,
        "macro": macro_changes,
        "new_filings": new_filings,
        "evidence_gaps": {
            "before": left.payload.get("filing_errors", {}),
            "after": right.payload.get("filing_errors", {}),
        },
        "summary": "Observed differences between stored snapshots. Price, holdings, sample-window and macro changes may overlap; this comparison does not establish causality.",
        "mode": left.payload["mode"],
    }


def evidence_pack(db, id, mode):
    a = portfolio_analysis(db, id, mode)
    top = sorted(a["risk_contribution"].items(), key=lambda x: x[1], reverse=True)
    return {
        "analytics": a,
        "top_risk": top[:3],
        "tools": [
            {
                "name": "portfolio_analytics",
                "endpoint": f"/portfolios/{id}/analytics",
                "source": a["provenance"],
            }
        ],
    }


@app.post("/portfolios/{id}/analyst")
def analyst(id: int, body: AnalystInput, db: DB, mode: Mode = "demo"):
    e = evidence_pack(db, id, mode)
    a = e["analytics"]
    sections = []
    citations = []
    plan, engine_name, warning = choose_plan(
        body.question, a["weights"], body.use_model
    )
    if plan.company_ticker:
        ticker = plan.company_ticker
        try:
            f = fundamentals(db, ticker, mode)
            sections.append(
                f"{ticker}: financial source is {f['source']}. Revenue: {f.get('revenue')}; free cash flow: {f.get('free_cash_flow')}. Missing facts remain unavailable."
            )
            e["tools"].append({"name": "company_fundamentals", "ticker": ticker})
            if plan.filing_query:
                citations = search_filings(
                    filings(db, ticker, mode), plan.filing_query
                )[:3]
                e["tools"].append({"name": "search_filings", "ticker": ticker})
                if not citations:
                    sections.append(
                        "No filing passages matched the search. Try more specific terms."
                    )
            if plan.include_valuation and f.get("revenue") and f.get("shares"):
                inputs = DCFInput(revenue=f["revenue"], shares=f["shares"]).model_dump()
                val = dcf(inputs)
                sections.append(
                    f"Illustrative DCF implied share price: ${val['price']:,.2f}. Uses default growth 8%, operating margin 25%, WACC 9%, terminal growth 2.5%, net debt $10 billion. Review all inputs in Research before using this estimate."
                )
                e["tools"].append(
                    {"name": "dcf_valuation", "ticker": ticker, "inputs": inputs}
                )
        except DataError as exc:
            sections.append("Company evidence unavailable: " + str(exc))
    if plan.include_macro:
        try:
            m = macro(db, mode)
            sections.append(
                "Macro observations: "
                + ", ".join(
                    f"{s['name']} {s['value']} {s['unit']} ({s['date']})"
                    for s in m["series"]
                )
            )
            e["tools"].append({"name": "macro_observations", "source": m["source"]})
        except DataError as exc:
            sections.append("Macro evidence unavailable: " + str(exc))
    if plan.include_stress:
        scenario = stress(id, StressInput(), db, mode)
        sections.append(
            f"Default combined stress scenario impact: ${scenario['impact']:,.2f} ({scenario['return']:.2%}). Market -20%, rates +100 bps, oil -25%. {scenario['method']}."
        )
        e["tools"].append(
            {"name": "stress_test", "assumptions": scenario["assumptions"]}
        )
    if plan.include_changes:
        saved = [
            s
            for s in db.scalars(
                select(Snapshot)
                .where(Snapshot.portfolio_id == id)
                .order_by(Snapshot.id.desc())
            )
            if s.payload["mode"] == mode
        ][:2]
        if len(saved) == 2:
            comparison = changes(id, db, saved[1].id, saved[0].id)
            sections.append(
                "Latest snapshot changes: "
                + ", ".join(
                    f"{r['metric']} delta {r['delta']:.6g}"
                    for r in comparison["metrics"]
                )
                + ". "
                + comparison["summary"]
            )
            e["tools"].append(
                {
                    "name": "compare_snapshots",
                    "before": saved[1].id,
                    "after": saved[0].id,
                }
            )
        else:
            sections.append("Capture two snapshots in this mode to compare changes.")
    sections.append(
        f"Portfolio value is ${a['value']:,.2f}. Historical one-day 95% VaR is ${a['var_dollars']:,.2f}; annualized volatility is {a['volatility']:.2%}. Maximum sample drawdown is {a['max_drawdown']:.2%}."
    )
    if e["top_risk"]:
        sections.append(
            "Largest covariance risk contributions: "
            + ", ".join(f"{t} {v:.1%}" for t, v in e["top_risk"])
            + ". These use current weights, not a causal explanation of changes."
        )
    if not any(
        [
            plan.company_ticker,
            plan.include_macro,
            plan.include_stress,
            plan.include_changes,
        ]
    ) and not any(
        w in body.question.lower()
        for w in [
            "risk",
            "portfolio",
            "return",
            "volatility",
            "beta",
            "sharpe",
            "drawdown",
            "allocation",
        ]
    ):
        sections.append(
            "The available tools cover portfolio risk, fundamentals, filings, macro, default DCF/stress assumptions and snapshot changes. This question may require evidence those tools do not contain."
        )
    return {
        "answer": "\n\n".join(sections),
        "engine": engine_name,
        "question": body.question,
        "tools": e["tools"],
        "citations": citations,
        "provenance": a["provenance"],
        "plan": plan.model_dump(),
        "warning": warning,
        "limitation": "Tool results are rendered by deterministic evidence templates. Optional model planning chooses tools; it cannot supply displayed numeric claims.",
    }


@app.get("/portfolios/{id}/report", response_class=PlainTextResponse)
def report(id: int, db: DB, mode: Mode = "demo"):
    e = evidence_pack(db, id, mode)
    a = e["analytics"]
    lines = [
        f"# Investment committee | {a['portfolio']['name']}",
        f"Generated {datetime.now(timezone.utc).isoformat()}",
        f"Data: {a['provenance']['source']} | as of {a['end']}",
        "",
        "## Portfolio and risk",
        f"Value: ${a['value']:,.2f}; sample return: {a['total_return']:.2%}; volatility: {a['volatility']:.2%}; one-day 95% VaR: ${a['var_dollars']:,.2f}.",
        f"Largest risk contributions: {e['top_risk']}",
        "",
        "## Holdings",
    ]
    for h in a["holdings"]:
        lines.append(f"- {h['ticker']}: ${h['value']:,.2f}, weight {h['weight']:.1%}")
    lines.extend(["", "## Macro evidence"])
    try:
        m = macro(db, mode)
        lines.append(m["source"])
        for s in m["series"]:
            lines.append(
                f"- {s['name']}: {s['value']} {s['unit']} ({s['date']}) {s.get('url', 'synthetic fixture')}"
            )
    except DataError as exc:
        lines.append(str(exc))
    lines.extend(["", "## Company and filing evidence"])
    for h in a["holdings"]:
        try:
            f = fundamentals(db, h["ticker"], mode)
            lines.append(
                f"- {h['ticker']}: revenue {f.get('revenue')}; free cash flow {f.get('free_cash_flow')}; source {f['source']} {f.get('url', '')}"
            )
            for d in filings(db, h["ticker"], mode)["documents"]:
                lines.append(f"  {d['form']} {d['date']}: {d['url']} [{d['id']}]")
        except DataError as exc:
            lines.append(f"- {h['ticker']}: evidence unavailable: {exc}")
    scenario = stress(id, StressInput(), db, mode)
    lines.extend(
        [
            "",
            "## Scenario review",
            f"Default combined scenario: {scenario['return']:.2%} / ${scenario['impact']:,.2f}",
            str(scenario["assumptions"]),
            scenario["method"],
        ]
    )
    saved = [
        s
        for s in db.scalars(
            select(Snapshot)
            .where(Snapshot.portfolio_id == id)
            .order_by(Snapshot.id.desc())
        )
        if s.payload["mode"] == mode
    ][:2]
    lines.extend(["", "## What changed"])
    if len(saved) == 2:
        comparison = changes(id, db, saved[1].id, saved[0].id)
        for row in comparison["metrics"]:
            lines.append(
                f"- {row['metric']}: {row['before']} → {row['after']} (delta {row['delta']})"
            )
        lines.append(comparison["summary"])
    else:
        lines.append("Two snapshots are required; no change attribution generated.")
    lines.extend(
        [
            "",
            "## Review items",
            "Verify source dates and filing context; review concentration, liquidity and scenario assumptions before making decisions. DCF assumptions require a separate analyst model.",
            "",
            "## Methodology",
            a["methodology"],
            "No investment recommendations or calibrated confidence scores are generated.",
        ]
    )
    return "\n".join(lines)
