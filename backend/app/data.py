"""Explicit demo fixtures and bounded, cached public-source adapters."""

import hashlib
import io
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

import httpx
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from sqlalchemy.exc import IntegrityError

from .db import Cache

COMPANIES = {
    "MSFT": ("Microsoft", "Technology", 430, 320),
    "NVDA": ("NVIDIA", "Technology", 135, 90),
    "JPM": ("JPMorgan Chase", "Financials", 220, 170),
    "XOM": ("Exxon Mobil", "Energy", 115, 98),
    "WMT": ("Walmart", "Consumer staples", 82, 65),
    "SPY": ("S&P 500 ETF", "Broad market", 565, 490),
    "AAPL": ("Apple", "Technology", 225, 180),
    "GOOGL": ("Alphabet", "Technology", 170, 140),
}


class DataError(Exception):
    pass


_SEC_LOCK = threading.Lock()
_LAST_SEC_REQUEST = 0.0


def cached(db, key, fetch, hours=12):
    row = db.get(Cache, key)
    if row and row.updated.replace(tzinfo=timezone.utc) > datetime.now(
        timezone.utc
    ) - timedelta(hours=hours):
        return row.payload
    payload = fetch()
    if row:
        row.payload = payload
        row.updated = datetime.now(timezone.utc)
    else:
        db.add(Cache(key=key, payload=payload))
    try:
        db.commit()
    except IntegrityError:
        # Concurrent reads can fetch the same missing cache key; use the winner.
        db.rollback()
        winner = db.get(Cache, key)
        if winner is None:
            raise
        return winner.payload
    return payload


def request(url, params=None, sec=False):
    if sec and not os.getenv("SEC_USER_AGENT"):
        raise DataError(
            "Set SEC_USER_AGENT to your application name and contact email for EDGAR access"
        )
    headers = (
        {"User-Agent": os.getenv("SEC_USER_AGENT", "FinSight local research")}
        if sec
        else {}
    )
    global _LAST_SEC_REQUEST
    if sec:
        with _SEC_LOCK:
            delay = max(0.0, 0.2 - (time.monotonic() - _LAST_SEC_REQUEST))
            time.sleep(delay)
            _LAST_SEC_REQUEST = time.monotonic()
    try:
        response = httpx.get(
            url, params=params, headers=headers, timeout=20, follow_redirects=True
        )
        response.raise_for_status()
        if len(response.content) > 15_000_000:
            raise DataError("Source response exceeds 15 MB limit")
        return response
    except httpx.HTTPError as e:
        raise DataError(
            f"Public source unavailable ({type(e).__name__}); retry later or select demo mode"
        ) from e


def source_boundary(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (KeyError, TypeError, IndexError, ValueError) as exc:
            raise DataError(
                "Public source returned an unexpected response format; no synthetic fallback was used"
            ) from exc

    return wrapped


@source_boundary
def market(db, tickers, mode="demo"):
    tickers = sorted(set(tickers))
    if mode == "demo":
        dates = pd.bdate_range("2025-01-02", periods=300)
        market_returns = np.random.default_rng(41).normal(0.00045, 0.009, len(dates))
        frame = {}
        for ticker in tickers:
            seed = int(hashlib.sha256(ticker.encode()).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            start = COMPANIES.get(ticker, (ticker, "Other", 100, 80))[3]
            beta = 1.7 if ticker == "NVDA" else 0.65 if ticker == "WMT" else 1.05
            daily = (
                market_returns
                if ticker == "SPY"
                else beta * market_returns + rng.normal(0.00015, 0.007, len(dates))
            )
            frame[ticker] = start * np.cumprod(1 + daily)
        return pd.DataFrame(frame, index=dates), {
            "mode": "demo",
            "source": "Seeded synthetic adjusted-price fixture; not market observations",
            "as_of": str(dates[-1].date()),
        }

    provider = os.getenv("MARKET_DATA_PROVIDER", "stooq")
    if provider not in ["stooq", "alphavantage"]:
        raise DataError("MARKET_DATA_PROVIDER must be stooq or alphavantage")
    if provider == "alphavantage" and not os.getenv("ALPHA_VANTAGE_API_KEY"):
        raise DataError(
            "ALPHA_VANTAGE_API_KEY is required for the configured market provider"
        )

    def fetch(ticker):
        if provider == "alphavantage":
            payload = request(
                "https://www.alphavantage.co/query",
                {
                    "function": "TIME_SERIES_DAILY",
                    "symbol": ticker,
                    "outputsize": "compact",
                    "apikey": os.getenv("ALPHA_VANTAGE_API_KEY"),
                },
            ).json()
            rows = payload.get("Time Series (Daily)")
            if not rows:
                raise DataError(
                    "Alpha Vantage returned no daily observations; check your key, symbol or plan quota"
                )
            df = pd.Series(
                {date: float(row["4. close"]) for date, row in rows.items()}
            ).sort_index()
            df = df[(df > 0) & np.isfinite(df)]
            if len(df) < 30:
                raise DataError("Alpha Vantage history has fewer than 30 observations")
            return {"dates": df.index.tolist(), "prices": df.tolist()}
        # Stooq daily prices are not a guaranteed total-return series.
        response = request(
            "https://stooq.com/q/d/l/", {"s": ticker.lower() + ".us", "i": "d"}
        )
        try:
            df = pd.read_csv(io.StringIO(response.text)).tail(505)
            df["Date"] = pd.to_datetime(df["Date"])
            df["Close"] = pd.to_numeric(df["Close"])
            df = (
                df[(df["Close"] > 0) & np.isfinite(df["Close"])]
                .drop_duplicates("Date")
                .sort_values("Date")
            )
            if len(df) < 30:
                raise ValueError()
            return {
                "dates": df.Date.dt.strftime("%Y-%m-%d").tolist(),
                "prices": df.Close.tolist(),
            }
        except (ValueError, KeyError) as e:
            raise DataError(f"No usable price history for {ticker}") from e

    series = {}
    for ticker in tickers:
        data = cached(db, provider + ":" + ticker, lambda ticker=ticker: fetch(ticker))
        series[ticker] = pd.Series(data["prices"], index=pd.to_datetime(data["dates"]))
    frame = pd.DataFrame(series).dropna()
    if len(frame) < 30:
        raise DataError(
            "Fewer than 30 overlapping observations across holdings and benchmark"
        )
    return frame, {
        "mode": "live",
        "source": f"{'Stooq' if provider == 'stooq' else 'Alpha Vantage compact'} daily closes; no guaranteed total-return adjustment; 12-hour cache",
        "as_of": str(frame.index[-1].date()),
    }


@source_boundary
def macro(db, mode):
    if mode == "demo":
        return {
            "mode": "demo",
            "source": "Illustrative fixture, not current FRED observations",
            "series": [
                {
                    "id": "DGS10",
                    "name": "10Y Treasury",
                    "value": 4.25,
                    "unit": "%",
                    "date": "2026-02-25",
                },
                {
                    "id": "DGS2",
                    "name": "2Y Treasury",
                    "value": 3.95,
                    "unit": "%",
                    "date": "2026-02-25",
                },
                {
                    "id": "UNRATE",
                    "name": "Unemployment",
                    "value": 4.2,
                    "unit": "%",
                    "date": "2026-02-01",
                },
                {
                    "id": "CPIAUCSL",
                    "name": "Consumer price index",
                    "value": 320.4,
                    "unit": "index",
                    "date": "2026-02-01",
                },
            ],
        }
    key = os.getenv("FRED_API_KEY")
    if not key:
        raise DataError("FRED_API_KEY is required for live macro observations")
    series = []
    for id, name, unit in [
        ("DGS10", "10Y Treasury", "%"),
        ("DGS2", "2Y Treasury", "%"),
        ("UNRATE", "Unemployment", "%"),
        ("CPIAUCSL", "Consumer price index", "index"),
    ]:

        def fetch(id=id):
            data = request(
                "https://api.stlouisfed.org/fred/series/observations",
                {
                    "series_id": id,
                    "api_key": key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 30,
                },
            ).json()
            valid = [x for x in data["observations"] if x["value"] != "."]
            if not valid:
                raise DataError(f"No observations for {id}")
            return valid[0]

        item = cached(db, "fred:" + id, fetch)
        series.append(
            {
                "id": id,
                "name": name,
                "unit": unit,
                "value": float(item["value"]),
                "date": item["date"],
                "url": "https://fred.stlouisfed.org/series/" + id,
            }
        )
    return {"mode": "live", "source": "FRED; series dates may differ", "series": series}


def cik_for(db, ticker):
    data = cached(
        db,
        "sec:tickers",
        lambda: request(
            "https://www.sec.gov/files/company_tickers.json", sec=True
        ).json(),
        168,
    )
    for item in data.values():
        if item["ticker"] == ticker:
            return str(item["cik_str"]).zfill(10)
    raise DataError(
        "Ticker not found in SEC issuer mapping; funds may not have company facts"
    )


@source_boundary
def fundamentals(db, ticker, mode):
    if mode == "demo":
        seed = int(hashlib.sha256(ticker.encode()).hexdigest()[:4], 16)
        revenue = (30 + seed % 250) * 1e9
        return {
            "ticker": ticker,
            "name": COMPANIES.get(ticker, (ticker,))[0],
            "mode": "demo",
            "source": "Illustrative company financial fixture, not reported financials",
            "period": "2025-12-31",
            "revenue": revenue,
            "operating_income": revenue * 0.25,
            "net_income": revenue * 0.19,
            "cash": revenue * 0.15,
            "debt": revenue * 0.22,
            "assets": revenue * 1.8,
            "equity": revenue * 0.8,
            "operating_cash_flow": revenue * 0.28,
            "capex": revenue * 0.06,
            "free_cash_flow": revenue * 0.22,
            "shares": 3e9,
            "operating_margin": 0.25,
            "fcf_margin": 0.22,
            "roe": 0.2375,
            "history": [],
        }
    cik = cik_for(db, ticker)
    facts = cached(
        db,
        "sec:facts:" + cik,
        lambda: request(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", sec=True
        ).json(),
        24,
    )
    tags = {
        "revenue": [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ],
        "operating_income": ["OperatingIncomeLoss"],
        "net_income": ["NetIncomeLoss"],
        "cash": ["CashAndCashEquivalentsAtCarryingValue"],
        "debt": ["LongTermDebtCurrent", "LongTermDebtNoncurrent"],
        "assets": ["Assets"],
        "equity": ["StockholdersEquity"],
        "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
        "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    }
    output = {
        "ticker": ticker,
        "name": facts["entityName"],
        "mode": "live",
        "source": "SEC XBRL annual facts; unavailable fields are null",
        "url": f"https://www.sec.gov/edgar/browse/?CIK={cik}",
        "history": [],
    }

    def annual(tag, unit="USD", duration=True):
        records = (
            facts.get("facts", {})
            .get("us-gaap", {})
            .get(tag, {})
            .get("units", {})
            .get(unit, [])
        )
        selected = []
        for x in records:
            if x.get("form") != "10-K":
                continue
            if duration:
                if not x.get("start"):
                    continue
                days = (pd.Timestamp(x["end"]) - pd.Timestamp(x["start"])).days
                if not 330 <= days <= 380:
                    continue
            selected.append(x)
        return sorted(
            selected, key=lambda x: (x["end"], x.get("filed", "")), reverse=True
        )

    periods = {}
    for field, names in tags.items():
        found = []
        for tag in names:
            found = annual(
                tag, duration=field not in ["cash", "debt", "assets", "equity"]
            )
            if found:
                break
        output[field] = found[0]["val"] if found else None
        if found:
            periods[field] = found[0]["end"]
        if field == "revenue":
            seen = set()
            for x in found:
                if x["end"] not in seen:
                    output["history"].append({"date": x["end"], "revenue": x["val"]})
                    seen.add(x["end"])
            output["history"] = output["history"][:5][::-1]
    shares = annual("CommonStockSharesOutstanding", "shares", False)
    output["shares"] = shares[0]["val"] if shares else None
    output["periods"] = periods
    output["period"] = periods.get("revenue")
    output["debt_note"] = (
        "Debt is the first available long-term debt tag, not total net debt. Verify DCF inputs against filing."
    )
    output["free_cash_flow"] = (
        output["operating_cash_flow"] - output["capex"]
        if output["operating_cash_flow"] is not None
        and output["capex"] is not None
        and periods.get("operating_cash_flow") == periods.get("capex")
        else None
    )
    for name, numerator, denominator in [
        ("operating_margin", "operating_income", "revenue"),
        ("roe", "net_income", "equity"),
    ]:
        output[name] = (
            output[numerator] / output[denominator]
            if output.get(numerator) is not None
            and output.get(denominator)
            and periods.get(numerator) == periods.get(denominator)
            else None
        )
    output["fcf_margin"] = (
        output["free_cash_flow"] / output["revenue"]
        if output.get("free_cash_flow") is not None
        and output.get("revenue")
        and periods.get("revenue") == periods.get("capex")
        else None
    )
    return output


@source_boundary
def filings(db, ticker, mode):
    if mode == "demo":
        return {
            "mode": "demo",
            "documents": [
                {
                    "id": ticker + "-demo",
                    "form": "10-K",
                    "date": "2025-12-31",
                    "url": "https://www.sec.gov/edgar/search/",
                    "title": ticker + " synthetic research document",
                    "text": "ILLUSTRATIVE FIXTURE. Revenue growth depends on customer demand. Risk factors include supply chain disruption, competition, interest rates and regulatory changes. Management discusses capital expenditure and liquidity. This text is synthetic and is not a quotation from an SEC filing.",
                }
            ],
        }
    cik = cik_for(db, ticker)

    def fetch():
        data = request(
            f"https://data.sec.gov/submissions/CIK{cik}.json", sec=True
        ).json()["filings"]["recent"]
        docs = []
        for i, form in enumerate(data["form"]):
            if form not in ["10-K", "10-Q", "8-K"]:
                continue
            accession = data["accessionNumber"][i]
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{data['primaryDocument'][i]}"
            html = request(url, sec=True).text
            soup = BeautifulSoup(html, "html.parser")
            for el in soup(["script", "style", "ix:header"]):
                el.decompose()
            content = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:2_000_000]
            docs.append(
                {
                    "id": accession,
                    "form": form,
                    "date": data["filingDate"][i],
                    "url": url,
                    "title": ticker + " " + form,
                    "text": content,
                }
            )
            if len(docs) == 3:
                break
        return {"mode": "live", "documents": docs}

    return cached(db, "sec:filings:" + cik, fetch, 24)


def search_filings(data, query):
    terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    hits = []
    for doc in data["documents"]:
        text = doc["text"]
        for offset in range(0, len(text), 1000):
            chunk = text[offset : offset + 1400]
            score = sum(chunk.lower().count(term) for term in terms if len(term) > 2)
            if score:
                hits.append(
                    {
                        "document_id": doc["id"],
                        "form": doc["form"],
                        "date": doc["date"],
                        "url": doc["url"],
                        "offset": offset,
                        "text": chunk,
                        "score": score,
                        "citation": f"{doc['id']} · character {offset}",
                    }
                )
    return sorted(hits, key=lambda x: x["score"], reverse=True)[:8]
