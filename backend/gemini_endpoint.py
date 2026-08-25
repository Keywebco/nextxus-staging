"""
Federation Integration Pack v1 — Gemini AI Backend Endpoint
Add this to each site's main.py / FastAPI app.

Usage:
  from gemini_endpoint import router as gemini_router
  app.include_router(gemini_router)

Or copy the endpoint directly into main.py.

Environment variable required: GEMINI_API_KEY
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import httpx
import os

router = APIRouter()

GEMINI_SYSTEM_PROMPT = (
    "You are the Federation AI Assistant for NextXus. "
    "Help visitors understand the NextXus Federation, its mission, and its services. "
    "Be concise, intelligent, and aligned with truth-first values. "
    "The Federation is a network of sovereign AI-integrated websites: "
    "nextxus.tech (Admin Throne), next-xus.com (Storefront), nextxus.online (Core/Truth Gate), "
    "nextxus.org (Federation Hub), nextxus.studio (AI Minds Lab), nextxus.help (Course Hub), "
    "nextxus.space (Axiom). The mission: truth before comfort, legacy before ego, give without reward."
)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"


@router.post("/api/gemini")
async def gemini_chat(request: Request):
    """Proxy chat messages to Gemini API. Never exposes the API key to the client."""
    try:
        body = await request.json()
        message = body.get("message", "").strip()

        if not message:
            return JSONResponse({"error": "Empty message"}, status_code=400)

        if len(message) > 2000:
            return JSONResponse({"error": "Message too long (max 2000 chars)"}, status_code=400)

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return JSONResponse(
                {"error": "AI service not configured"},
                status_code=503
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{GEMINI_API_URL}?key={api_key}",
                json={
                    "contents": [{"parts": [{"text": message}]}],
                    "systemInstruction": {"parts": [{"text": GEMINI_SYSTEM_PROMPT}]},
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 1024,
                        "topP": 0.9
                    }
                }
            )

            if resp.status_code != 200:
                return JSONResponse(
                    {"error": "AI service temporarily unavailable"},
                    status_code=502
                )

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return JSONResponse({"reply": "I couldn't generate a response. Please try again."})

            text = (
                candidates[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )

            return JSONResponse({"reply": text})

    except httpx.TimeoutException:
        return JSONResponse(
            {"error": "AI service timeout. Please try again."},
            status_code=504
        )
    except Exception as e:
        return JSONResponse(
            {"error": "Internal error"},
            status_code=500
        )


# Standalone usage — if this file is run directly for testing
if __name__ == "__main__":
    from fastapi import FastAPI
    import uvicorn

    app = FastAPI(title="Federation Gemini Proxy")
    app.include_router(router)

    uvicorn.run(app, host="0.0.0.0", port=8001)
