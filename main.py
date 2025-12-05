# main.py (root of repo)

from src.app.main import app  # import the Apple backend FastAPI instance

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
