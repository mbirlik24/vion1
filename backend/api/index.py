"""
Vercel serverless function handler for FastAPI app.
This file is used by Vercel to serve the FastAPI application.
"""
from mangum import Mangum
from app.main import app

# Create handler for Vercel
handler = Mangum(app, lifespan="off")
