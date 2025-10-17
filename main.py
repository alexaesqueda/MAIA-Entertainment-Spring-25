import os
from fastapi import FastAPI
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# 1. Load environment variables from .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# 2. Create a connection to your Supabase PostgreSQL database
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# 3. Initialize your FastAPI app
app = FastAPI()

# 4. Basic route to test that FastAPI runs
@app.get("/health")
def health():
    return {"ok": True}

# 5. Route to check if your database + pgvector work
@app.get("/db-ok")
def db_ok():
    with engine.connect() as conn:
        res = conn.execute(text("select extname from pg_extension where extname='vector';")).fetchone()
        return {"pgvector_installed": bool(res)}
    
@app.get("/routes")
def routes():
    return [r.path for r in app.routes]

print("DB URL repr:", repr(os.getenv("DATABASE_URL")))