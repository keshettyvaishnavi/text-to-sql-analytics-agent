"""FastAPI endpoint for asking questions in plain English."""
from fastapi import FastAPI
from pydantic import BaseModel

from agent import Answer, ask

app = FastAPI(title="Text to SQL Analytics Agent")


class Question(BaseModel):
    question: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask", response_model=Answer)
def ask_endpoint(q: Question) -> Answer:
    return ask(q.question)
