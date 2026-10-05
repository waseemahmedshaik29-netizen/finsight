# Financial methodology

All rates in the API are decimal fractions. Dollar outputs use USD and share counts may be fractional. Results use the intersection of observations for every security and the benchmark, sorted by date. Live prices must be finite and positive; at least 30 price observations are required.

## Portfolio reconstruction

At each date, `NAV_t = cash + sum(quantity_i × price_i,t)`. Quantities are the current holdings for the entire sample and cash is fixed, with no yield. Daily simple returns are `NAV_t / NAV_(t−1) − 1`. Cost basis is used only for unrealized P/L, `quantity × (latest price − per-share basis)`, not as the denominator of sample returns. No deposits, sales, fees or historical trades are reconstructed. This avoids pretending current holdings are a realized historical trading record.

Sample return = ending NAV / starting NAV − 1. Annualized geometric return = `(ending NAV / starting NAV)^(252/n_returns) − 1`. Annualized volatility = sample standard deviation of daily returns × sqrt(252).

Risk-free rate is an explicit annual assumption of 4%, converted to daily `(1.04)^(1/252) − 1`. Sharpe = mean daily excess return × 252 / annual volatility. Sortino uses the root mean square of `min(excess_return, 0)` across **all** observations, annualized by sqrt(252). Undefined ratios are null, never Infinity or NaN.

Drawdown is `NAV / running_max_NAV − 1`; max drawdown is the minimum of that series. Beta is sample covariance(portfolio, benchmark) / sample variance(benchmark). Alpha is 252 × the mean arithmetic CAPM residual `r_p − r_f − beta × (r_b − r_f)`; it is not simply cumulative outperformance. Both use aligned dates.

## Historical risk

The 5th percentile uses Pandas' linear interpolation. One-day 95% VaR loss fraction = max(0, −quantile_5%). CVaR = max(0, −mean of observations at or below that quantile). Dollar VaR = loss fraction × latest NAV. In a small sample, the tail estimate is noisy. CVaR includes ties; neither metric gives a guaranteed limit on loss.

Correlations are Pearson correlations of aligned daily asset returns. A constant-return asset yields undefined correlations, displayed as zero. Risk contribution uses current NAV weights `w`, asset covariance `Σ` annualized by 252, and `RC_i = w_i(Σw)_i / (wᵀΣw)`. Contributions sum to one where nonzero variance exists. Cash has zero contribution. These are contributions to variance (and proportional Euler volatility contribution), calculated at current weights; portfolio performance volatility uses historically drifting weights instead.

Rolling volatility uses 21 return observations with sample standard deviation. This is a trading-observation window rather than a calendar-month window.

## DCF

A five-year unlevered model grows revenue at a constant analyst growth rate. For each year:

`FCFF = revenue × operating_margin × (1 − tax_rate) + revenue × D&A_ratio − revenue × CapEx_ratio − change_in_revenue × working_capital_ratio`.

FCFF is discounted by `(1 + WACC)^year`. Gordon terminal value = final-year FCFF × (1 + terminal growth) / (WACC − terminal growth), discounted at year 5. Enterprise value = sum of discounted FCFF + discounted terminal value. Equity value = enterprise value − net debt; negative net debt represents net cash. Implied share value = equity value / shares. Negative equity values are returned rather than silently floored.

WACC must exceed terminal growth and shares must be positive. Sensitivity varies WACC by ±1/2 percentage points and terminal growth across 1–4%. Invalid grid cells are null. Default assumptions are illustrative and are not issuer estimates. Annual SEC facts may be stale, restated or reported with different tags and fiscal periods. Importing facts does not validate all valuation assumptions.

## Stress testing

For each holding, shock = portfolio beta × market shock − sector duration × rate change in decimal + 0.6 × oil shock for energy assets. Shocks are bounded to [−100%, +100%]. Sector durations: technology 6, financials 2, energy 1, consumer staples 3, other 3. These are disclosed demo assumptions, not estimated bond duration or macro sensitivities. Cash has zero impact. Dollar effect is the sum of latest holding values × assumed shocks.

Preset scenarios only fill those inputs. The recession mix is illustrative; it is not a replay of 2008, 2020 or 2022. The model does not estimate second-order effects, liquidity, changing correlations or option payoffs.

## Snapshots and evidence

A capture persists full calculation results, current holdings, source metadata, capture timestamp, macro observations and available filing IDs. Comparisons require two increasing snapshot IDs for the same portfolio and same data mode. Deltas are recomputed from stored evidence and include added/removed securities. Macro deltas retain source units; a Treasury yield change of 0.14 percentage points is 14 basis points. The interface reports the source values without inventing attribution.

Filing text is normalized and truncated to two million characters per document, then divided into 1,400-character passages with a 1,000-character stride. Ranking counts query terms longer than two characters. Citations identify accession, filing date, URL and normalized character offset. This is reproducible lexical retrieval, not semantic embeddings. Demo text is not an SEC quote. Model planning only receives held tickers and the question; all plans are validated and tools are read-only. The backend renders numeric evidence, discarding model-authored answer text.
