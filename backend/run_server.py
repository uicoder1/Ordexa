import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import uvicorn
from app.main import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0" if os.getenv("PORT") else "127.0.0.1")
    workers = int(os.getenv("WEB_CONCURRENCY", "1"))
    print(f"Starting Ordexa FastAPI Backend Server on {host}:{port} with {workers} worker(s)...")
    uvicorn.run("app.main:app", host=host, port=port, workers=workers, proxy_headers=True, forwarded_allow_ips="*")
