# Verification record

Verified in this workspace on October 5, 2026.

- Python calculation/API/provider suite: **18 tests passed** on Python 3.14.7. This covers benchmark identity, cash-only handling, drawdown, DCF perpetuity identity, validation, duplicate holdings, cross-portfolio position access, immutable snapshots, source parsing/cache, annual fact filtering, lexical citations, deterministic numeric answers, report generation, optional model-plan validation and credential-free fallback.
- Ruff code checks: passed.
- Frontend TypeScript strict checking: passed.
- Next.js optimized production build: passed. Served using the standalone server with copied static assets.
- App-browser checks: Overview loads; company financials and synthetic filing search render; DCF produces forecast and sensitivity tables; scenario run returns per-position and portfolio impacts; analyst renders backend risk numbers and a tool trace; portfolio creation and position addition succeed; baseline/after snapshots compare value, risk, allocation and macro observations. Saved screenshots are in this directory. No warning/error console entries were reported in the checked dashboard view. Mobile Overview and Research were checked at a 390-pixel viewport and had no page-level horizontal overflow. The report button displayed its completed-download status; the browser download-event hook timed out.
- Automated Playwright suite is included and configured in CI, but could not run on this host: macOS sandbox denied Chromium's MachPortRendezvous bootstrap registration before any test started. This is a runner launch failure, not a passing E2E result. Browser workflows above were checked separately through the app browser. The browser download event check timed out; the report endpoint and content are covered by passing API tests.
- Docker/Compose and real PostgreSQL integration were **not executed locally** because Docker and PostgreSQL binaries are absent. CI includes a PostgreSQL service and persistence smoke test; the backend CI job is currently queued on GitHub.
- Live Stooq download was attempted for SPY and returned HTTP 404 from this environment. The adapter reported an explicit data-source error. Alpha Vantage is provided as a configured key-based alternative, not verified live.
- SEC, FRED and OpenAI credentialed requests are covered with mocks and missing-key checks. No real credentials were supplied, so no claim is made that those integrations were verified live.

The app remains runnable locally with SQLite and labeled synthetic demo data. External source formats, provider blocking, financial licenses and availability may change. Use your own valid credentials to verify live integrations.

## GitHub verification

The [first public CI run](https://github.com/waseemahmedshaik29-netizen/finsight/actions/runs/37369312540) passed frontend TypeScript checks, the production build and the automated desktop/mobile browser workflows on Linux. The backend/PostgreSQL job is queued; its result is not yet available.
