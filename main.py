"""
NextXus.Space — Axiom & Roger AI Simulation
Main FastAPI server entry point.
Includes Axiom dispatch (LLM-wired) and Gemini endpoints.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="NEXTXUS.SPACE — Axiom & Roger AI Simulation")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from backend.dispatch_endpoint import router as dispatch_router
from backend.gemini_endpoint import router as gemini_router

app.include_router(dispatch_router)
app.include_router(gemini_router)


@app.get("/api/health")
async def health_check():
    return {"status": "operational", "site": "nextxus.space", "mind": "Axiom"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
