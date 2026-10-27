# Text to SQL Analytics Agent

Ask business questions in plain English and get trusted answers from a data warehouse. The agent is built with LangGraph and answers only through a governed semantic layer, so every metric means the same thing every time, and every query is checked by SQL guardrails before it runs. All data is synthetic.

## Why this project

Most text to SQL demos let the model write any SQL it wants against raw tables. That breaks in real companies: metrics drift, joins go wrong, and nobody can trust the numbers. This agent takes the approach used with semantic layers like dbt Semantic Layer and Snowflake semantic views. The model only chooses metrics, dimensions, and filters that are already defined, and the SQL is compiled from those definitions.

## How it works

```
question
  -> plan      (LLM or keyword planner returns a structured QueryPlan, validated by Pydantic)
  -> compile   (semantic layer turns the plan into SQL with the right joins and parameters)
  -> execute   (guardrails: single read only SELECT, table allow list, EXPLAIN check)
  -> retry     (on failure, the error goes back to the planner, up to 2 times)
  -> explain   (short plain language answer)
```

Every answer returns the SQL, the result rows, the number of attempts, and the full execution trace.

## Example

```
Q: Top 3 merchants by spend in OH
SQL: SELECT m.merchant_name AS merchant, SUM(f.amount) AS total_spend
     FROM fact_transactions f
     JOIN dim_merchant m ON f.merchant_id = m.merchant_id
     JOIN dim_customer c ON f.customer_id = c.customer_id
     WHERE c.state = ? GROUP BY m.merchant_name ORDER BY total_spend DESC LIMIT 3
```

Other questions to try: "Fraud rate by channel", "Monthly transaction count trend", "Average ticket for Premier customers", "Which category has the lowest fraud rate", "Total spend and transaction count by state".

## Key features

* Governed semantic layer in YAML: metrics, dimensions, joins, and synonyms
* Star schema warehouse: fact_transactions with customer, merchant, and date dimensions
* Structured output: the planner must return a valid QueryPlan, unknown metrics are rejected
* SQL guardrails: read only connection, single SELECT only, table allow list, parameterized filters
* Self correcting loop: failed plans or queries are retried with the error as feedback
* Works fully offline with a keyword planner; set `OPENAI_API_KEY` to use an LLM planner
* FastAPI service, Docker image, pytest suite, and GitHub Actions CI

## Quick start

```bash
pip install -r requirements.txt
python warehouse.py
python agent.py "Fraud rate by channel"
uvicorn api:app --reload
curl -X POST localhost:8000/ask -H "Content-Type: application/json" -d '{"question": "Total spend by category"}'
pytest -q
```

## Project files

| File | Purpose |
|---|---|
| agent.py | LangGraph workflow with plan, compile, execute, retry, and explain |
| semantic_layer.yaml | Governed metric and dimension definitions |
| semantic.py | QueryPlan model and SQL compiler |
| planner.py | LLM planner with a keyword fallback |
| guard.py | SQL safety checks and execution |
| warehouse.py | Builds the synthetic star schema |
| api.py | FastAPI service |
| test_agent.py | pytest suite |

## Tech stack

Python, LangGraph, Pydantic, YAML semantic layer, SQLite, FastAPI, OpenAI API (optional), Docker, pytest, GitHub Actions

## Next steps

* Point the compiler at Snowflake and generate Snowflake semantic views from the YAML
* Add an evaluation set of questions with expected SQL results
* Add charts to the answers
