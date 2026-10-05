# FinSight — personal project

## Résumé entry

**FinSight — Portfolio Intelligence Platform**
Personal project | Next.js, TypeScript, Python, FastAPI, SQLAlchemy, PostgreSQL, NumPy, Pandas, Docker, GitHub Actions

- Built a financial research terminal with portfolio management, return and risk analytics, DCF valuation, macro stress tests and source-linked SEC filing search.
- Implemented a “What Changed?” engine that compares stored portfolio snapshots across value, risk, allocation, macro observations and filing IDs.
- Added a validated analyst tool layer that renders numbers from deterministic backend calculations, with optional model planning and a credential-free local demo.
- Verified the calculation and API layer with 18 tests and included Docker configuration, CI checks and browser workflow tests.

## Short project description

FinSight is a personal finance/AI application for exploring portfolio performance, risk, company filings and valuation assumptions. I built the interface, backend calculations, data adapters and snapshot comparison workflow, using AI-assisted development. The demo works locally without API keys and labels its synthetic data.

## Interview discussion points

Explain why financial calculations are separated from the model: the model can select tools, but the backend calculates and renders numeric evidence. Walk through a snapshot comparison and show how changing a holding affects value, covariance risk contribution and the reconstructed return series.

Be explicit that the portfolio history uses current share quantities over the sample, rather than a transaction ledger. Discuss the difference between historical VaR and a guaranteed loss limit, and why scenario heuristics require disclosed assumptions.

Describe the tests actually executed: backend tests, static checks, production frontend build and app-browser workflows. Docker/PostgreSQL and credentialed live integrations were not verified locally. Automated Playwright execution was blocked by the local browser sandbox; GitHub CI has passed the frontend production build and automated desktop/mobile browser workflows. The backend/PostgreSQL CI job is queued.

This is an independent personal project, not employment experience, a deployed trading system or a claim of profitable investment performance.
