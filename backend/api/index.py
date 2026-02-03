"""
Vercel serverless function handler for FastAPI app.
This file is used by Vercel to serve the FastAPI application.
"""
import sys
import os

# Add the parent directory to Python path to ensure imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mangum import Mangum
from app.main import app

# Create handler for Vercel
handler = Mangum(app, lifespan="off")
