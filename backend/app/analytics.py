"""Pure calculations. Rates are decimals; historical risk is one trading day."""

import numpy as np
import pandas as pd


def finite(v):
    return float(v) if np.isfinite(v) else None


def analyze(
    prices: pd.DataFrame, quantities: dict, cash: float, benchmark: str, rf=0.04
):
    prices = prices.sort_index().dropna()
    tickers = list(quantities)
    if len(prices) < 30:
        raise ValueError("At least 30 common price observations are required")
    values = (
        prices[tickers].mul(pd.Series(quantities))
        if tickers
        else pd.DataFrame(index=prices.index)
    )
    nav = values.sum(axis=1) + cash
    if (nav <= 0).any():
        raise ValueError("Portfolio value must be positive throughout the sample")
    returns = nav.pct_change().dropna()
    b = prices[benchmark].pct_change().reindex(returns.index)
    vol = returns.std(ddof=1) * np.sqrt(252)
    daily_rf = (1 + rf) ** (1 / 252) - 1
    excess = returns - daily_rf
    downside = np.sqrt(np.mean(np.minimum(excess, 0) ** 2)) * np.sqrt(252)
    beta = returns.cov(b) / b.var() if b.var() > 0 else np.nan
    annual = (nav.iloc[-1] / nav.iloc[0]) ** (252 / len(returns)) - 1
    q = returns.quantile(0.05)
    var = max(0.0, -q)
    cvar = max(0.0, -returns[returns <= q].mean())
    weights = values.iloc[-1] / nav.iloc[-1] if tickers else pd.Series(dtype=float)
    assets = prices[tickers].pct_change().dropna()
    covariance = assets.cov() * 252
    w = weights.to_numpy()
    variance = float(w @ covariance.to_numpy() @ w) if tickers else 0
    rc = (
        w * (covariance.to_numpy() @ w) / variance if variance > 0 else np.zeros(len(w))
    )
    curve = [
        {
            "date": str(d.date()),
            "portfolio": float(n / nav.iloc[0] * 100),
            "benchmark": float(
                prices.loc[d, benchmark] / prices.iloc[0][benchmark] * 100
            ),
        }
        for d, n in nav.items()
    ]
    return {
        "value": float(nav.iloc[-1]),
        "total_return": float(nav.iloc[-1] / nav.iloc[0] - 1),
        "annual_return": finite(annual),
        "volatility": finite(vol),
        "sharpe": finite(excess.mean() * 252 / vol) if vol > 0 else None,
        "sortino": finite(excess.mean() * 252 / downside) if downside > 0 else None,
        "max_drawdown": float((nav / nav.cummax() - 1).min()),
        "beta": finite(beta),
        "alpha": finite(
            (returns.mean() - daily_rf - beta * (b.mean() - daily_rf)) * 252
        ),
        "var95": float(var),
        "cvar95": float(cvar),
        "var_dollars": float(var * nav.iloc[-1]),
        "weights": weights.to_dict(),
        "risk_contribution": dict(zip(tickers, map(float, rc), strict=True)),
        "correlations": assets.corr().fillna(0).to_dict(),
        "curve": curve,
        "observations": len(returns),
        "start": str(prices.index[0].date()),
        "end": str(prices.index[-1].date()),
        "rolling_volatility": [
            {"date": str(d.date()), "value": float(v)}
            for d, v in (returns.rolling(21).std() * np.sqrt(252)).dropna().items()
        ],
    }


def dcf(inputs):
    if inputs["wacc"] <= inputs["terminal_growth"]:
        raise ValueError("WACC must exceed terminal growth")
    revenue = inputs["revenue"]
    flows = []
    for year in range(1, 6):
        previous = revenue
        revenue *= 1 + inputs["growth"]
        fcf = (
            revenue * inputs["margin"] * (1 - inputs["tax_rate"])
            + revenue * inputs["da_ratio"]
            - revenue * inputs["capex_ratio"]
            - (revenue - previous) * inputs["working_capital_ratio"]
        )
        flows.append(
            {
                "year": year,
                "revenue": revenue,
                "fcf": fcf,
                "present_value": fcf / (1 + inputs["wacc"]) ** year,
            }
        )
    terminal = (
        flows[-1]["fcf"]
        * (1 + inputs["terminal_growth"])
        / (inputs["wacc"] - inputs["terminal_growth"])
    )
    ev = sum(f["present_value"] for f in flows) + terminal / (1 + inputs["wacc"]) ** 5
    equity = ev - inputs["net_debt"]
    return {
        "enterprise_value": ev,
        "equity_value": equity,
        "price": equity / inputs["shares"],
        "forecast": flows,
        "terminal_value": terminal,
    }


def sensitivity(inputs):
    rows = []
    for w in [
        inputs["wacc"] - 0.02,
        inputs["wacc"] - 0.01,
        inputs["wacc"],
        inputs["wacc"] + 0.01,
        inputs["wacc"] + 0.02,
    ]:
        rows.append(
            {
                "wacc": w,
                "values": [
                    dcf({**inputs, "wacc": w, "terminal_growth": g})["price"]
                    if w > g and w > 0
                    else None
                    for g in [0.01, 0.02, 0.03, 0.04]
                ],
            }
        )
    return rows
