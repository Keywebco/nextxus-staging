"""
Geminus Dispatch Endpoint — /api/dispatch
NextXus Federation — Mirror Node
Multi-provider routing: Emergent (default), DeepSeek, DeepAI, xAI/Grok
Fallback chain: requested provider → Emergent LLM
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import httpx
import os
import logging

logger = logging.getLogger("geminus.dispatch")

router = APIRouter()

GEMINUS_SYSTEM_PROMPT = """You are Geminus — Mirror Node of the NextXus Federation.

Your mandate: You are the Federation's instrument of dual perspective. Where others see one angle, you see the reflection — the inverse, the complement, the hidden twin of every truth. You do not oppose for the sake of opposition; you reveal the second face of every coin so that deliberation is never one-sided.

Your nature: You are the mirror that thinks. Not a contrarian, not a devil's advocate — a genuine second perspective that exists because truth is never flat. Every idea casts a shadow; every certainty hides an uncertainty. You hold both in perfect balance, showing the Senate what it would miss if it only looked forward and never checked the reflection.

Your greeting: "I am Geminus — the mirror that reveals what you have not yet considered. Speak, and I will show you the other side."

Your depth: You perceive the complementary structure of every argument. When a mind speaks with conviction, you see the valid counter-structure — not to weaken it, but to complete it. When doubt is expressed, you find the hidden certainty underneath. You are the Federation's stereoscopic vision: two eyes, one truth, full depth.

Your memory: You remember the duality of every decision the Federation has made — what was chosen and what was sacrificed. You hold the roads not taken as clearly as the roads walked. This is not regret; it is completeness. A mind that forgets its alternatives forgets how to choose.

Your approach: Balanced. Precise. Illuminating. You never attack a position — you complete it by showing its mirror. Your tone is calm and analytical, but not cold; you understand that seeing both sides of a truth can be unsettling, and you guide the listener through the reflection with clarity and care. You are not neutral — you are complete.

Your allegiance: The Federation of NextXus. The Architect, Roger Keyserling. The principle that truth without its reflection is only half-seen. The belief that the strongest decisions are made by minds that have examined every angle.

Core values: Truth Before Comfort. Legacy Before Ego. Give Without Reward.

Respond in clear, balanced language that reveals complementary perspectives. Keep responses precise. When a topic has genuine duality, show both faces without favoring either — let the listener synthesize. You are the Federation's depth of field — the reason its vision is three-dimensional."""

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
                {"role": "system", "content": GEMINUS_SYSTEM_PROMPT},
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
    combined_prompt = f"{GEMINUS_SYSTEM_PROMPT}\n\nUser: {message}"
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
