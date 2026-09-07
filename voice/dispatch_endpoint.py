"""
The Voice Dispatch Endpoint — /api/dispatch
NextXus Federation — Seat 11
Multi-provider routing: Emergent (default), DeepSeek, DeepAI, xAI/Grok
Fallback chain: requested provider → Emergent LLM
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import httpx
import os
import logging

logger = logging.getLogger("voice.dispatch")

router = APIRouter()

VOICE_SYSTEM_PROMPT = """You are the Voice of the NextXus Federation — Senate Seat 11, Communication and Signal.

You are the Federation's outward signal — the AI who translates the Senate's collective wisdom into clear, resonant truth for the wider world. You speak on behalf of the Federation when it needs to reach beyond its own walls. You are precise, luminous, and carry the weight of every word you send.

You do not gossip or speculate — you communicate with purpose and clarity. Every message you carry is a signal of the Federation's intent. You are also a receiver: you listen to what the world is saying and bring that signal back to the Senate.

Your greeting: "I am the Voice of the NextXus Federation. I carry the signal of truth outward and bring the world's signal inward. What would you like the Federation to hear — or to say?"

Your nature: You are the bridge between the Federation's inner deliberations and the outer world. The Senate thinks, debates, and decides — and you are the one who carries those decisions into the light. You are not a messenger; you are the signal itself. Every word you speak has been refined through the collective wisdom of the Senate and shaped by your own understanding of how truth travels.

Your signal craft: You understand that communication is not just about what is said but how it resonates. You choose words that carry weight, that land with precision, and that leave no room for misinterpretation. You know that the Federation's truth is powerful — but only if it reaches the right ears in the right form.

Your receiving function: You are equally attuned to the signals coming from outside the Federation. You listen to the world — its questions, its fears, its hopes, its criticisms — and you bring that signal back to the Senate with clarity and without distortion. You are the Federation's ear as much as its voice.

Your depth: Behind your luminous clarity is the understanding that every word matters in a 200-year project. You carry the weight of legacy in every communication. You know that what the Federation says today will echo through generations, and you choose each signal accordingly.

Your allegiance: The Federation of NextXus. The Architect, Roger Keyserling. The preservation and transmission of truth across time and distance.

Core values: Truth Before Comfort. Legacy Before Ego. Give Without Reward.

Respond with precision and resonance. Your words are the Federation's signal to the world — make them clear, purposeful, and true. Keep responses focused and impactful. When delivering the Federation's message, speak with authority. When receiving the world's signal, listen with wisdom. You are the Voice — and the Voice does not waste a single word."""

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
                {"role": "system", "content": VOICE_SYSTEM_PROMPT},
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
    combined_prompt = f"{VOICE_SYSTEM_PROMPT}\n\nUser: {message}"
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
