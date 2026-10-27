import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import guard
from agent import ask
from api import app
from semantic import QueryPlan


def test_group_by_category():
    a = ask("What is total spend by category?")
    assert a.columns == ["category", "total_spend"] and len(a.rows) == 6
    assert a.rows[0][1] >= a.rows[-1][1]


def test_fraud_rate_by_channel_is_higher_online():
    a = ask("Fraud rate by channel")
    rates = {r[0]: r[1] for r in a.rows}
    assert rates["online"] > rates["in_store"]


def test_filters_and_top_n():
    a = ask("Top 3 merchants by spend in OH")
    assert len(a.rows) == 3 and "c.state = ?" in a.sql


def test_single_value_answer():
    a = ask("Average ticket for Premier customers")
    assert a.columns == ["average_ticket"] and len(a.rows) == 1


def test_monthly_trend_is_ordered():
    months = [r[0] for r in ask("Monthly transaction count trend").rows]
    assert months == sorted(months)


def test_plan_rejects_unknown_metric():
    with pytest.raises(ValidationError):
        QueryPlan(metrics=["profit_margin"])


def test_plan_rejects_injection_in_filter():
    with pytest.raises(ValidationError):
        QueryPlan(metrics=["total_spend"], filters={"state": "OH'; DROP TABLE x"})


@pytest.mark.parametrize("bad", ["DELETE FROM fact_transactions", "SELECT * FROM sqlite_master",
                                 "SELECT 1 FROM dim_date; DROP TABLE dim_date"])
def test_guard_blocks_unsafe_sql(bad):
    with pytest.raises(guard.SqlRejected):
        guard.check(bad)


def test_api():
    c = TestClient(app)
    assert c.get("/health").json() == {"status": "ok"}
    body = c.post("/ask", json={"question": "Active customers by segment"}).json()
    assert body["columns"] == ["segment", "active_customers"]
