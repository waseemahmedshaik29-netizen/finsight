"""Run on an isolated PostgreSQL database (CI); exercise real API persistence."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient

from app.main import app

with TestClient(app) as c:
    p = c.post(
        "/portfolios", json={"name": "PostgreSQL integration", "cash": 10000}
    ).json()
    id = p["id"]
    assert (
        c.post(
            f"/portfolios/{id}/positions",
            json={"ticker": "MSFT", "quantity": 10, "cost_basis": 320},
        ).status_code
        == 201
    )
    assert c.get(f"/portfolios/{id}/analytics").status_code == 200
    first = c.post(f"/portfolios/{id}/snapshots").json()["id"]
    last = c.post(f"/portfolios/{id}/snapshots").json()["id"]
    assert (
        c.get(f"/portfolios/{id}/changes?before={first}&after={last}").status_code
        == 200
    )
    assert c.delete(f"/portfolios/{id}").status_code == 204
print("PostgreSQL persistence and JSON snapshots passed")
