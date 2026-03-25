import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text

app = FastAPI(title="myapp")
templates = Jinja2Templates(directory="templates")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://myapp:myapp@db:5432/myapp")
engine = create_engine(DATABASE_URL)


@app.on_event("startup")
def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS visitors (
                id SERIAL PRIMARY KEY,
                visited_at TIMESTAMP DEFAULT NOW()
            )
        """))


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO visitors DEFAULT VALUES"))
        result = conn.execute(text("SELECT COUNT(*) FROM visitors"))
        count = result.scalar()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "visitor_count": count,
    })


@app.get("/version")
def version():
    return {"version": "1.2.0", "status": "updated"}
