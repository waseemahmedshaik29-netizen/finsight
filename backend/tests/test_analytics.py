import numpy as np
import pandas as pd
import pytest

from app.analytics import analyze, dcf, sensitivity
from app.main import DCFInput


def frame(values):
    return pd.DataFrame(
        {"A": values, "SPY": values},
        index=pd.bdate_range("2025-01-01", periods=len(values)),
    )


def test_identical_benchmark_beta_and_zero_alpha():
    prices = 100 * np.cumprod(1 + np.random.default_rng(1).normal(0.001, 0.01, 100))
    a = analyze(frame(prices), {"A": 2}, 0, "SPY")
    assert a["beta"] == pytest.approx(1)
    assert a["alpha"] == pytest.approx(0, abs=1e-12)
    assert a["value"] == pytest.approx(prices[-1] * 2)
    assert a["risk_contribution"]["A"] == pytest.approx(1)
    assert a["total_return"] == pytest.approx(prices[-1] / prices[0] - 1)
    assert a["cvar95"] >= a["var95"]


def test_drawdown_and_cash_attenuate_risk():
    values = np.tile([100, 110, 99, 105, 100], 20)
    a = analyze(frame(values), {"A": 1}, 0, "SPY")
    c = analyze(frame(values), {"A": 1}, 1000, "SPY")
    assert a["max_drawdown"] == pytest.approx(-0.1)
    assert c["volatility"] < a["volatility"]
    assert c["beta"] < a["beta"]


def test_cash_only_has_no_ratios_or_tail_loss():
    a = analyze(frame(np.arange(100) + 100), {}, 1000, "SPY")
    assert a["value"] == 1000 and a["sharpe"] is None
    assert a["var95"] == 0 and a["cvar95"] == 0
    assert a["risk_contribution"] == {}


def test_invalid_empty_capital_and_short_series():
    with pytest.raises(ValueError):
        analyze(frame(range(40)), {}, 0, "SPY")
    with pytest.raises(ValueError):
        analyze(frame(range(20)), {"A": 1}, 0, "SPY")


def test_dcf_constant_fcf_perpetuity():
    # $100 revenue, 100% operating margin, no reinvestment or tax => $100 FCF.
    p = DCFInput(
        revenue=100,
        growth=0,
        margin=1,
        tax_rate=0,
        da_ratio=0,
        capex_ratio=0,
        working_capital_ratio=0,
        wacc=0.1,
        terminal_growth=0,
        net_debt=0,
        shares=10,
    ).model_dump()
    assert dcf(p)["enterprise_value"] == pytest.approx(1000)
    assert dcf(p)["price"] == pytest.approx(100)
    assert sensitivity(p)[0]["values"][0] > sensitivity(p)[-1]["values"][0]
    with pytest.raises(ValueError):
        dcf({**p, "terminal_growth": 0.1})


def test_invalid_nonfinite_and_terminal_spread():
    with pytest.raises(ValueError):
        DCFInput(wacc=0.02, terminal_growth=0.03)
    with pytest.raises(ValueError):
        DCFInput(revenue=float("nan"))
