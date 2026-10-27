"""LangGraph text to SQL agent: plan, compile, validate, execute, retry on failure, then explain the answer."""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ValidationError

import guard
import planner
from semantic import compile_sql

MAX_RETRIES = 2


class Answer(BaseModel):
    question: str
    sql: str
    columns: list[str]
    rows: list[list]
    summary: str
    attempts: int
    trace: list[str]


class State(TypedDict, total=False):
    question: str
    plan: dict
    sql: str
    params: list
    columns: list
    rows: list
    error: str
    attempts: int
    summary: str
    trace: list


def _t(s: State, step: str) -> list:
    return s.get("trace", []) + [step]


def plan_node(s: State) -> State:
    feedback = f"The previous attempt failed with: {s['error']}. Fix it." if s.get("error") else ""
    try:
        p = planner.plan(s["question"], feedback)
        return {"plan": p.model_dump(), "error": "", "attempts": s.get("attempts", 0) + 1, "trace": _t(s, "plan")}
    except (ValidationError, ValueError) as e:
        return {"error": str(e), "attempts": s.get("attempts", 0) + 1, "trace": _t(s, "plan_failed")}


def compile_node(s: State) -> State:
    from semantic import QueryPlan
    sql, params = compile_sql(QueryPlan(**s["plan"]))
    return {"sql": sql, "params": params, "trace": _t(s, "compile")}


def execute_node(s: State) -> State:
    try:
        cols, rows = guard.run(s["sql"], s["params"])
        return {"columns": cols, "rows": rows, "error": "", "trace": _t(s, "execute")}
    except Exception as e:
        return {"error": str(e), "trace": _t(s, "execute_failed")}


def after_plan(s: State) -> str:
    if not s.get("error"):
        return "compile"
    return "plan" if s["attempts"] <= MAX_RETRIES else "explain"


def after_execute(s: State) -> str:
    if not s.get("error"):
        return "explain"
    return "plan" if s["attempts"] <= MAX_RETRIES else "explain"


def explain_node(s: State) -> State:
    if s.get("error"):
        return {"summary": f"I could not answer this safely: {s['error']}", "trace": _t(s, "explain")}
    rows, cols = s["rows"], s["columns"]
    if not rows:
        text = "No data matched this question."
    elif len(rows) == 1:
        text = ", ".join(f"{c} is {v}" for c, v in zip(cols, rows[0]))
    else:
        top = ", ".join(f"{c} {v}" for c, v in zip(cols, rows[0]))
        text = f"Returned {len(rows)} rows. First row: {top}."
    return {"summary": text, "trace": _t(s, "explain")}


def build():
    g = StateGraph(State)
    g.add_node("plan", plan_node)
    g.add_node("compile", compile_node)
    g.add_node("execute", execute_node)
    g.add_node("explain", explain_node)
    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", after_plan, {"compile": "compile", "plan": "plan", "explain": "explain"})
    g.add_edge("compile", "execute")
    g.add_conditional_edges("execute", after_execute, {"explain": "explain", "plan": "plan"})
    g.add_edge("explain", END)
    return g.compile()


GRAPH = build()


def ask(question: str) -> Answer:
    out = GRAPH.invoke({"question": question, "trace": [], "attempts": 0})
    return Answer(question=question, sql=out.get("sql", ""), columns=out.get("columns", []), rows=out.get("rows", []),
                  summary=out["summary"], attempts=out.get("attempts", 0), trace=out["trace"])


if __name__ == "__main__":
    import sys
    qs = sys.argv[1:] or ["What is total spend by category?", "Fraud rate by channel",
                          "Monthly transaction count trend", "Top 3 merchants by spend in OH",
                          "Average ticket for Premier customers"]
    for q in qs:
        a = ask(q)
        print(f"\nQ: {q}\nSQL: {a.sql}\nA: {a.summary}")
