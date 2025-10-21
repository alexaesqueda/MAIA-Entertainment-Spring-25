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


from sqlalchemy.engine.url import make_url

@app.get("/db-debug")
def db_debug():
    import os, socket
    raw = os.getenv("DATABASE_URL")
    try:
        u = make_url(raw)
        host = u.host
        # try DNS resolution to surface the exact error here
        try:
            socket.getaddrinfo(host, u.port or 5432)
            dns_ok = True
            dns_err = None
        except Exception as e:
            dns_ok = False
            dns_err = str(e)
        return {
            "env_loaded": bool(raw),
            "driver": u.drivername,
            "host": host,
            "port": u.port,
            "database": u.database,
            "query": u.query,
            "dns_ok": dns_ok,
            "dns_err": dns_err,
        }
    except Exception as e:
        return {"env_loaded": bool(raw), "parse_error": str(e), "raw": raw}
