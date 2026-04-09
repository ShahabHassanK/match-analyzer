"""
xG Match Analyzer - Entry Point
---------------------------------
Run this file to start the FastAPI server.

Local dev:  python run.py          → http://localhost:8000
Production: Railway sets PORT automatically; the server binds to 0.0.0.0
"""

import os
import uvicorn


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    is_prod = os.environ.get("RAILWAY_ENVIRONMENT") is not None

    uvicorn.run(
        "app:app",
        host="0.0.0.0",          # Required for Railway routing
        port=port,
        reload=not is_prod,       # Disable reload in production
    )
