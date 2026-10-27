"""SQL guardrails: only one read only SELECT, only approved tables, checked with EXPLAIN before running."""
import re
import sqlite3

from warehouse import DB_PATH, build_warehouse

ALLOWED = {"fact_transactions", "dim_customer", "dim_merchant", "dim_date"}
BLOCKED = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|pragma|replace|vacuum)\b", re.I)


class SqlRejected(ValueError):
    pass


def check(sql: str) -> None:
    s = sql.strip()
    if not s.lower().startswith("select") or ";" in s.rstrip(";") or BLOCKED.search(s):
        raise SqlRejected("Only a single read only SELECT statement is allowed")
    tables = set(re.findall(r"\b(?:from|join)\s+([a-zA-Z_]+)", s, re.I))
    if not tables or not tables <= ALLOWED:
        raise SqlRejected(f"Tables not allowed: {sorted(tables - ALLOWED)}")


def run(sql: str, params: list) -> tuple[list[str], list[list]]:
    check(sql)
    if not DB_PATH.exists():
        build_warehouse()
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:
        con.execute(f"EXPLAIN QUERY PLAN {sql}", params)
        cur = con.execute(sql, params)
        return [c[0] for c in cur.description], [list(r) for r in cur.fetchall()]
