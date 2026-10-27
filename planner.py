"""Turns a natural language question into a QueryPlan.
Uses an LLM with structured output when OPENAI_API_KEY is set, otherwise a deterministic keyword planner."""
import json
import os
import re
import sqlite3

from semantic import LAYER, QueryPlan, catalog
from warehouse import DB_PATH

FILTER_VALUES = {
    "segment": "SELECT DISTINCT segment FROM dim_customer",
    "state": "SELECT DISTINCT state FROM dim_customer",
    "category": "SELECT DISTINCT category FROM dim_merchant",
    "merchant": "SELECT DISTINCT merchant_name FROM dim_merchant",
    "channel": "SELECT DISTINCT channel FROM fact_transactions",
    "month": "SELECT DISTINCT month FROM dim_date",
}


def _known_values() -> dict[str, list[str]]:
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:
        return {k: [r[0] for r in con.execute(q)] for k, q in FILTER_VALUES.items()}


def _match(text: str, synonyms: list[str]) -> int:
    return max((len(s) for s in synonyms if re.search(rf"\b{re.escape(s)}\b", text)), default=0)


def keyword_plan(question: str) -> QueryPlan:
    q = question.lower()
    values = _known_values()
    filters = {}
    for dim, vals in values.items():
        for v in vals:
            pretty = v.replace("_", " ").lower()
            if dim == "state" and not re.search(rf"\b{v}\b", question):
                continue
            if dim != "state" and not re.search(rf"\b{re.escape(pretty)}\b", q):
                continue
            filters[dim] = v
    metric_scores = {m: _match(q, d["synonyms"]) for m, d in LAYER["metrics"].items()}
    ranked = [m for m, s in sorted(metric_scores.items(), key=lambda x: -x[1]) if s]
    metrics = ranked[: 2 if re.search(r"\band\b", q) else 1] or ["total_spend"]
    if "fraud_rate" in metrics:
        metrics = ["fraud_rate"] + [m for m in metrics if m != "fraud_rate"][:1]
    dims = []
    for d, spec in LAYER["dimensions"].items():
        if d in filters:
            continue
        if _match(q, spec["synonyms"]) and re.search(rf"\b(by|per|each|across|which|top|trend|monthly)\b", q):
            dims.append(d)
    limit = int(m.group(1)) if (m := re.search(r"\btop (\d+)", q)) else 20
    order_desc = not re.search(r"\b(lowest|least|bottom)\b", q)
    return QueryPlan(metrics=metrics, dimensions=dims[:2], filters=filters, limit=limit, order_desc=order_desc)


def llm_plan(question: str, feedback: str = "") -> QueryPlan:
    from openai import OpenAI
    schema = json.dumps(QueryPlan.model_json_schema())
    prompt = (f"Map the question to a query plan using only this semantic layer.\n{catalog()}\n"
              f"Return JSON matching this schema: {schema}\n{feedback}\nQuestion: {question}")
    resp = OpenAI().chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0,
        response_format={"type": "json_object"}, messages=[{"role": "user", "content": prompt}])
    return QueryPlan.model_validate_json(resp.choices[0].message.content)


def plan(question: str, feedback: str = "") -> QueryPlan:
    if os.getenv("OPENAI_API_KEY"):
        return llm_plan(question, feedback)
    return keyword_plan(question)
