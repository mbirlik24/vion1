"""
Vercel serverless function handler for FastAPI app.
This file is used by Vercel to serve the FastAPI application.
"""
import sys
import os

# Add the parent directory to Python path to ensure imports work
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from mangum import Mangum
from app.main import app

# Create handler for Vercel - this is what Vercel will call
handler = Mangum(app, lifespan="off")
