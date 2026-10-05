# FinSight

[![FinSight checks](https://github.com/waseemahmedshaik29-netizen/finsight/actions/workflows/ci.yml/badge.svg)](https://github.com/waseemahmedshaik29-netizen/finsight/actions/workflows/ci.yml)

**Portfolio intelligence with calculations you can inspect.**

Personal project built with AI-assisted development. See the [résumé entry and project notes](docs/personal-project.md) for a factual description of the work and its tested scope.

FinSight is a local finance research terminal built with Next.js, TypeScript, FastAPI, SQLAlchemy and PostgreSQL. It combines portfolio analytics, historical risk, source-linked company research, valuation, macro scenarios and a tool-based analyst. The flagship **What Changed?** view compares immutable snapshots of holdings, risk metrics, macro observations and filing IDs.

The complete demo runs without API keys. Synthetic data is labeled on every screen and report. Live integrations fail visibly rather than substitute synthetic observations.

![FinSight dashboard](docs/dashboard.jpg)

## Run with Docker

Requires Docker Desktop / Compose.

```sh
cp .env.example .env
docker compose up --build
```

Open [the terminal](http://localhost:3000), [API documentation](http://localhost:8000/docs), or [health endpoint](http://localhost:8000/health). Compose starts PostgreSQL, the backend and the production frontend. The database volume persists portfolios, cached source responses and snapshots. Ports bind to localhost. Stop with `docker compose down`; add `-v` only if you intend to delete the database.

## Run without Docker

Requires Python 3.12+ and Node.js 22+, with pnpm 11.25.0 (`corepack enable` with supported Node installations). Tested locally on Python 3.14 and the bundled Node runtime. No PostgreSQL installation is necessary for the SQLite demo.

Terminal 1, from this directory:

```sh
cp .env.example .env
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Open http://localhost:3000. A starter portfolio is seeded when the database contains no portfolios. To use a local PostgreSQL instance, set `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/finsight` in the root `.env`. Quote/URL-encode credentials containing reserved URI characters. Restart the API after changing environment settings. For a different browser-facing API address, set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` and rebuild/restart Next.js; `.env.example` documents this variable, but Next.js reads it from its own directory.

Production frontend outside Docker: `pnpm build`, then `pnpm start`. The Docker image uses Next.js standalone output. The app is a single-user local research workspace, with no authentication, user isolation, trading execution or public deployment hardening.

## Try the full workflow

1. Inspect the seeded **Core conviction** portfolio in **Overview**. Edit a holding or add your own US ticker, quantity and per-share cost basis. Create/edit/delete portfolios with the controls next to the portfolio selector.
2. Open **Risk** for one-day 95% historical VaR/CVaR, beta/alpha, correlations, covariance risk contribution and 21-day rolling volatility.
3. In **What Changed?**, capture a snapshot. Change a quantity or cash balance, capture again, and compare. The metric and allocation differences come from stored calculations; earlier captures are never overwritten.
4. In **Research**, view company statements and search filing passages. Every result has a document ID, source URL and normalized-text offset. Demo passages are explicitly synthetic, not actual SEC quotations.
5. Load available company facts into **DCF**, review assumptions, and calculate five-year cash flows plus a WACC/terminal-growth sensitivity table.
6. In **Scenarios**, apply market, rate and oil shocks. Presets are illustrative scenarios, not historical crisis replays.
7. Ask **AI Analyst** about risks, macro, filings, default valuation/scenarios or snapshot changes. Inspect its tool trace. **Export report** downloads an investment-committee Markdown memo.
8. Switch to **Live sources** only after configuring the desired integrations below. Stooq prices need no key; the Alpha Vantage alternative requires its free key; FRED and SEC research have independent requirements.

## Architecture

```mermaid
flowchart TD
  UI[Next.js / TypeScript terminal] --> API[FastAPI validated API]
  API --> Q[Pure NumPy / Pandas calculations]
  API --> A[Validated analyst tool planner]
  A --> Q
  A --> D[Source adapters / document retrieval]
  API --> DB[(SQLAlchemy: PostgreSQL or SQLite)]
  D --> DB
  D --> S[Stooq daily closes]
  D --> E[SEC EDGAR submissions / XBRL / filings]
  D --> F[FRED observations]
  Q --> R[Immutable snapshots / comparison / reports]
  A --> T[Deterministic evidence renderer]
```

```text
backend/app/
  analytics.py   Pure portfolio math, DCF and sensitivity
  data.py        Explicit demo fixtures, cached public adapters, filing chunks
  analyst.py     Local planner and optional Responses function planner
  db.py          Portfolios, positions, JSON snapshots and persistent source cache
  main.py        Validated routes, orchestrated tools, comparisons and reports
backend/tests/   Calculation identities, API workflows, adapter/provider mocks
frontend/app/    Terminal views, typed API payloads and responsive charts
frontend/e2e/    Browser workflow regression tests
.github/workflows/ci.yml  Python tests, PostgreSQL smoke, frontend build/E2E
```

Swagger at `/docs` provides every request schema. Important routes include `/portfolios`, `/portfolios/{id}/positions`, `/portfolios/{id}/analytics`, `/portfolios/{id}/ingest`, `/macro`, `/companies/{ticker}/fundamentals`, `/companies/{ticker}/filings/search`, `/valuation/dcf`, `/portfolios/{id}/stress`, `/portfolios/{id}/snapshots`, `/portfolios/{id}/changes`, `/portfolios/{id}/analyst`, and `/portfolios/{id}/report`.

## Data sources and credentials

| Integration | Credentials | Behavior and limits |
|---|---|---|
| Synthetic demo | None | Seeded, repeatable 300-business-day price series beginning 2025-01-02; illustrative financials and macro; explicitly synthetic filing document |
| [Stooq daily history](https://stooq.com/q/d/?s=spy.us) | None | Daily US close-price download, last 505 rows, 12-hour cache. No guarantee of dividend/total-return adjustments; no real-time quotes. Provider may block downloads or change format. |
| [Alpha Vantage daily API](https://www.alphavantage.co/documentation/#daily) | `MARKET_DATA_PROVIDER=alphavantage`, `ALPHA_VANTAGE_API_KEY` | Explicit alternative to Stooq. Free-key compact history (100 points), raw daily closes; split/dividend adjustments are not included. Quotas may limit ingestion; cached for 12 hours. |
| [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | `SEC_USER_AGENT` with your application name and real contact email; no paid key | Ticker/CIK mapping, company annual XBRL facts and latest three 10-K/10-Q/8-K documents; 24-hour cache. Respect [SEC fair access](https://www.sec.gov/os/accessing-edgar-data). |
| [FRED observations](https://fred.stlouisfed.org/docs/api/fred/series_observations.html) | `FRED_API_KEY` | DGS10, DGS2, UNRATE and CPIAUCSL; latest nonmissing observation and date. CPI is an index, not a YoY inflation rate. 12-hour cache. [Request a key](https://fred.stlouisfed.org/docs/api/api_key.html). |
| [OpenAI Responses function calling](https://developers.openai.com/api/docs/guides/function-calling) | `OPENAI_API_KEY`, `OPENAI_MODEL` | Optional opt-in model planner chooses a strictly validated read-only research plan. The server renders facts and numbers. Missing keys, provider errors or invalid plans return an explicit local-planner fallback. |

Optional model planning sends your question and held ticker symbols to the configured OpenAI model, with `store=false`; it does not send account identifiers or full holdings. API use may incur charges. The default planner makes no model request. No real keys are included or required. Secrets stay on the backend and are never exposed as `NEXT_PUBLIC_*` variables.

Company tags vary across issuers. Missing facts remain null; financial durations are restricted to annual 10-K observations, and ratios require matching period ends. Review per-field dates and debt definitions before valuation. Filing search uses overlapping normalized-text chunks and deterministic lexical ranking, without embeddings or external vector services. Citations link to the full filing; the offset points into the cached normalized text, not the browser HTML.

## Calculation conventions

See [methodology](docs/methodology.md) for formulas, timing and limitations. Key conventions:

- Long-only positions and nonnegative cash; prices align on their common observed dates. No forward filling.
- Portfolio history is a **constant-share reconstruction using today’s quantities**, not transaction-aware realized performance. Editing holdings changes the reconstructed history. Unrealized P/L separately uses entered per-share cost basis.
- 252 trading observations per year. Fixed 4% annual risk-free assumption; cash earns zero.
- Historical one-day 95% VaR/CVaR are nonnegative loss estimates; they are not worst-case guarantees.
- Covariance risk contribution uses current weights and annualized asset-return covariance; it differs from risk on the historical drifting-weight return series.
- Stress tests use explicit sector-duration and oil heuristics with portfolio beta, not calibrated causal macro models.
- The snapshot comparison reports observed differences and does not attribute causality or invent earnings revisions.

## Tests and verification

```sh
cd backend
.venv/bin/python -m pytest -q
# Optional real PostgreSQL persistence check on a dedicated test database:
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/finsight_test \
  .venv/bin/python scripts/postgres_smoke.py

cd ../frontend
pnpm typecheck
pnpm build
# Start backend and frontend first, then:
pnpm exec playwright install chromium
pnpm test:e2e
```

CI runs isolated unit/API tests, a real PostgreSQL service integration, frontend type/build checks and browser workflows. See [verification record](docs/verification.md) for what was actually executed in this workspace. External paid/credentialed services use mocked responses in tests and need your credentials for a live check.

## Boundaries and future extensions

This is a runnable portfolio project for research and demonstration. It implements all requested feature categories with explicit models and local fallbacks; it does not claim the depth of a commercial terminal. No authentication, transaction ledger, multi-currency accounting, historical crisis replay, earnings-estimate feed, fitted style-factor regressions, automated recommendations or vector embedding index is included. SEC field mappings and sector assumptions are intentionally conservative. Add an authentication layer, migrations for schema evolution, process-independent scheduling/rate limiting, licensed adjusted market data, and transaction-aware accounting before a shared production deployment.

Tables are created on startup for version 1.0. Persisted cache and snapshots use SQLAlchemy JSON supported by both databases. Schema changes after release need a migration; `create_all` does not migrate existing tables. Back up your database before changing versions.
