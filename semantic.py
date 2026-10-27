"""Loads the semantic layer and compiles a validated query plan into SQL."""
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator

LAYER = yaml.safe_load((Path(__file__).resolve().parent / "semantic_layer.yaml").read_text())


class QueryPlan(BaseModel):
    """Structured output the planner must produce. Anything outside the semantic layer is rejected."""
    metrics: list[str] = Field(min_length=1)
    dimensions: list[str] = []
    filters: dict[str, str] = {}
    order_desc: bool = True
    limit: int = Field(default=20, ge=1, le=500)

    @field_validator("metrics")
    @classmethod
    def known_metrics(cls, v):
        bad = [m for m in v if m not in LAYER["metrics"]]
        if bad:
            raise ValueError(f"Unknown metrics: {bad}")
        return v

    @field_validator("dimensions")
    @classmethod
    def known_dimensions(cls, v):
        bad = [d for d in v if d not in LAYER["dimensions"]]
        if bad:
            raise ValueError(f"Unknown dimensions: {bad}")
        return v

    @field_validator("filters")
    @classmethod
    def known_filters(cls, v):
        for k, val in v.items():
            if k not in LAYER["dimensions"]:
                raise ValueError(f"Unknown filter dimension: {k}")
            if not re.fullmatch(r"[A-Za-z0-9 _\-]+", val):
                raise ValueError("Filter values may only contain letters, numbers, spaces, dashes, and underscores")
        return v


def compile_sql(plan: QueryPlan) -> tuple[str, list]:
    dims = LAYER["dimensions"]
    joins = []
    for d in list(plan.dimensions) + list(plan.filters):
        j = dims[d]["join"]
        if j and j not in joins:
            joins.append(j)
    select = [f'{dims[d]["sql"]} AS {d}' for d in plan.dimensions]
    select += [f'{LAYER["metrics"][m]["sql"]} AS {m}' for m in plan.metrics]
    sql = f'SELECT {", ".join(select)} FROM {LAYER["fact_table"]} f ' + " ".join(joins)
    params = []
    if plan.filters:
        sql += " WHERE " + " AND ".join(f'{dims[k]["sql"]} = ?' for k in plan.filters)
        params = list(plan.filters.values())
    if plan.dimensions:
        sql += " GROUP BY " + ", ".join(dims[d]["sql"] for d in plan.dimensions)
        order = "ASC" if plan.dimensions == ["month"] else ("DESC" if plan.order_desc else "ASC")
        key = plan.dimensions[0] if plan.dimensions == ["month"] else plan.metrics[0]
        sql += f" ORDER BY {key} {order}"
    sql += f" LIMIT {plan.limit}"
    return " ".join(sql.split()), params


def catalog() -> str:
    """Plain text description of the semantic layer, given to the LLM planner as context."""
    lines = ["Metrics:"] + [f"  {k}: {v['description']}" for k, v in LAYER["metrics"].items()]
    lines += ["Dimensions:"] + [f"  {k}" for k in LAYER["dimensions"]]
    return "\n".join(lines)
