"""
Convenience entrypoint for running the FastAPI app locally.

This allows commands like:
  python -m uvicorn main:app --reload

The actual FastAPI application lives in `app/main.py`.
"""

from app.main import app  # re-export for uvicorn

