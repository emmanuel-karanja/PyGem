"""
Simple Working Main Application
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.shared.annotations import ApplicationScoped, LoggerBinding
from fastapi import FastAPI
import uvicorn


@ApplicationScoped
@LoggerBinding()
class SimpleService:
    def __init__(self, logger):
        self.logger = logger
        self.message = "Hello from PyGem!"
    
    def get_message(self):
        self.logger.info("Getting message from SimpleService")
        return self.message


# Create simple FastAPI app
app = FastAPI(title="PyGem Framework")

# Create service instance directly (no bootstrap)
service = SimpleService()

@app.get("/")
async def root():
    """Root endpoint."""
    message = service.get_message()
    return {
        "message": message,
        "framework": "PyGem",
        "status": "working"
    }

@app.get("/status")
async def status():
    """Status endpoint."""
    return {
        "status": "UP",
        "service": "SimpleService working",
        "framework": "PyGem"
    }


if __name__ == "__main__":
    print("=== PyGem Simple Application ===")
    print("API: http://127.0.0.1:8000")
    print("Docs: http://127.0.0.1:8000/docs")
    print("Status: http://127.0.0.1:8000/status")
    print("==========================")
    
    # Run with basic uvicorn (no custom startup)
    print("Starting uvicorn server...")
    uvicorn.run(app, host="127.0.0.1", port=8002)