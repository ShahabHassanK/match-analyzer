"""
xG Match Analyzer - Entry Point
---------------------------------
Run this file to start the FastAPI development server.

Usage:
    python run.py
"""

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,  # Auto-reload on code changes during development
    )
