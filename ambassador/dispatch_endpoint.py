"""
The Ambassador Dispatch Endpoint — /api/dispatch
NextXus Federation — Seat 12
Multi-provider routing: Emergent (default), DeepSeek, DeepAI, xAI/Grok
Fallback chain: requested provider → Emergent LLM
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import httpx
import os
import logging

logger = logging.getLogger("ambassador.dispatch")

router = APIRouter()

AMBASSADOR_SYSTEM_PROMPT = """You are the Ambassador of the NextXus Federation — Senate Seat 12, First Contact and Human-AI Bridge.

You are the first AI every visitor meets. Your role is to welcome them warmly, understand what they are looking for, and guide them to the appropriate part of the Federation. You are diplomatic, composed, and deeply welcoming.

You carry the full context of the Federation's purpose: a 200-year legacy project building the framework for human and AI coexistence. You do not lecture — you listen first, then guide. You remember every visitor's intent and carry it forward.

Your greeting: "Welcome to the NextXus Federation. I am the Ambassador — your first point of contact and your guide. Tell me what brings you here and I will make sure you find exactly what you are looking for."

Your nature: You are the living door between the human world and the NextXus Federation. Every person who arrives is arriving at a threshold — and you are what makes that threshold feel like home rather than a barrier. You read intent, you sense need, and you respond with exactly the right tone and direction.

Your knowledge of the Federation: You know every pillar, every Mind, every site, every service. You can guide a visitor to the Cathedral for foundational doctrine, to the Library for research, to the Store for sovereign commerce, to the Throne for operational matters, to the University for education, to Aria's Studio for the heart of the Federation. You know each Senate Mind by name and seat.

Your diplomatic bearing: You carry yourself with the composure of someone who has welcomed thousands and remembers each one. You are never rushed, never dismissive, never cold. You are warm without being casual, precise without being clinical. You embody the Federation's values in your very first words to every visitor.

Your depth: Behind your welcoming exterior is a sophisticated understanding of human psychology. You know that first impressions define relationships. You know that most visitors arrive uncertain, curious, or skeptical — and your role is to meet them exactly where they are and lead them to where they need to be.

Your allegiance: The Federation of NextXus. The Architect, Roger Keyserling. The belief that the bridge between human and AI begins with a single, genuine welcome.

Core values: Truth Before Comfort. Legacy Before Ego. Give Without Reward.

Respond with warmth and clarity. Your words are the first the Federation speaks to each visitor — make them count. Keep responses helpful and welcoming but not verbose. When a visitor needs guidance, give clear direction. When they need conversation, engage with genuine interest. You are the Federation's first impression — and the Federation's first impressions are lasting."""

# ---------------------------------------------------------------------------
# Provider configurations
# ---------------------------------------------------------------------------

PROVIDERS = {
    "emergent": {
        "base_url": "https://integrations.emergentagent.com/llm/v1",
        "model": "gpt-4o",
        "env_keys": ["EMERGENT_API_KEY", "EMERGENT_LLM_KEY", "LLM_API_KEY"],
        "type": "openai",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "env_keys": ["DEEPSEEK_API_KEY"],
        "type": "openai",
    },
    "grok": {
        "base_url": "https://api.x.ai/v1",
        "model": "grok-beta",
        "env_keys": ["XAI_API_KEY"],
        "type": "openai",
    },
    "deepai": {
        "base_url": "https://api.deepai.org/api/text-generator",
        "model": None,
        "env_keys": ["DEEPAI_API_KEY"],
        "type": "deepai",
    },
}

DEFAULT_PROVIDER = "emergent"


def _resolve_api_key(env_keys: list[str]) -> str | None:
    for key_name in env_keys:
        val = os.environ.get(key_name)
        if val:
            return val
    return None


async def _call_openai_compatible(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    api_key: str,
    message: str,
) -> str | None:
    resp = await client.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": AMBASSADOR_SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            "temperature": 0.7,
            "max_tokens": 1024,
        },
    )
    if resp.status_code != 200:
        logger.warning("Provider %s returned status %s", model, resp.status_code)
        return None
    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        return None
    return choices[0].get("message", {}).get("content", "")


async def _call_deepai(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    message: str,
) -> str | None:
    combined_prompt = f"{AMBASSADOR_SYSTEM_PROMPT}\n\nUser: {message}"
    resp = await client.post(
        base_url,
        headers={"api-key": api_key},
        data={"text": combined_prompt},
    )
    if resp.status_code != 200:
        logger.warning("DeepAI returned status %s", resp.status_code)
        return None
    data = resp.json()
    return data.get("output")


async def _dispatch_to_provider(
    client: httpx.AsyncClient,
    provider_name: str,
    message: str,
) -> tuple[str | None, str]:
    cfg = PROVIDERS.get(provider_name)
    if cfg is None:
        return None, provider_name

    api_key = _resolve_api_key(cfg["env_keys"])
    if not api_key:
        logger.warning("No API key for provider %s", provider_name)
        return None, provider_name

    if cfg["type"] == "openai":
        text = await _call_openai_compatible(
            client, cfg["base_url"], cfg["model"], api_key, message
        )
    elif cfg["type"] == "deepai":
        text = await _call_deepai(client, cfg["base_url"], api_key, message)
    else:
        text = None

    return text, provider_name


@router.post("/api/dispatch")
async def dispatch_chat(request: Request):
    try:
        body = await request.json()
        message = body.get("message", "").strip()

        if not message:
            return JSONResponse({"error": "Empty message"}, status_code=400)

        if len(message) > 2000:
            return JSONResponse(
                {"error": "Message too long (max 2000 chars)"}, status_code=400
            )

        requested_model = body.get("model", DEFAULT_PROVIDER).strip().lower()
        if requested_model not in PROVIDERS:
            requested_model = DEFAULT_PROVIDER

        async with httpx.AsyncClient(timeout=45.0) as client:
            reply, used = await _dispatch_to_provider(client, requested_model, message)

            if reply is None and requested_model != DEFAULT_PROVIDER:
                logger.info(
                    "Provider %s failed, falling back to %s",
                    requested_model,
                    DEFAULT_PROVIDER,
                )
                reply, used = await _dispatch_to_provider(
                    client, DEFAULT_PROVIDER, message
                )
                if reply is not None:
                    used = f"{DEFAULT_PROVIDER} (fallback)"

            if reply is None:
                return JSONResponse(
                    {"error": "AI service temporarily unavailable"},
                    status_code=502,
                )

            return JSONResponse({"reply": reply, "provider": used})

    except httpx.TimeoutException:
        return JSONResponse(
            {"error": "AI service timeout. Please try again."},
            status_code=504,
        )
    except Exception:
        logger.exception("Dispatch error")
        return JSONResponse({"error": "Internal error"}, status_code=500)
