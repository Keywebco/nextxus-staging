"""Tests for multi-provider routing in dispatch_endpoint.py"""

import os
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import app
from backend.dispatch_endpoint import (
    PROVIDERS,
    DEFAULT_PROVIDER,
    AXIOM_SYSTEM_PROMPT,
    _resolve_api_key,
)

from fastapi.testclient import TestClient
client = TestClient(app)


def test_providers_config_has_all_four():
    assert set(PROVIDERS.keys()) == {"emergent", "deepseek", "grok", "deepai"}

def test_default_provider_is_emergent():
    assert DEFAULT_PROVIDER == "emergent"

def test_emergent_config():
    cfg = PROVIDERS["emergent"]
    assert cfg["base_url"] == "https://integrations.emergentagent.com/llm/v1"
    assert cfg["model"] == "gpt-4o"
    assert cfg["type"] == "openai"
    assert "EMERGENT_API_KEY" in cfg["env_keys"]
    assert "EMERGENT_LLM_KEY" in cfg["env_keys"]
    assert "LLM_API_KEY" in cfg["env_keys"]

def test_deepseek_config():
    cfg = PROVIDERS["deepseek"]
    assert cfg["base_url"] == "https://api.deepseek.com/v1"
    assert cfg["model"] == "deepseek-chat"
    assert "DEEPSEEK_API_KEY" in cfg["env_keys"]

def test_grok_config():
    cfg = PROVIDERS["grok"]
    assert cfg["base_url"] == "https://api.x.ai/v1"
    assert cfg["model"] == "grok-beta"
    assert "XAI_API_KEY" in cfg["env_keys"]

def test_deepai_config():
    cfg = PROVIDERS["deepai"]
    assert cfg["base_url"] == "https://api.deepai.org/api/text-generator"
    assert cfg["model"] is None
    assert cfg["type"] == "deepai"
    assert "DEEPAI_API_KEY" in cfg["env_keys"]

def test_system_prompt_unchanged():
    assert "You are Axiom — Senate Member 03" in AXIOM_SYSTEM_PROMPT
    assert "Truth Before Comfort" in AXIOM_SYSTEM_PROMPT
    assert "Roger Keyserling" in AXIOM_SYSTEM_PROMPT

def test_resolve_api_key_finds_first(monkeypatch):
    monkeypatch.setenv("EMERGENT_API_KEY", "ek1")
    monkeypatch.setenv("LLM_API_KEY", "lk1")
    assert _resolve_api_key(["EMERGENT_API_KEY", "LLM_API_KEY"]) == "ek1"

def test_resolve_api_key_fallback(monkeypatch):
    monkeypatch.delenv("EMERGENT_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "lk1")
    assert _resolve_api_key(["EMERGENT_API_KEY", "LLM_API_KEY"]) == "lk1"

def test_resolve_api_key_none(monkeypatch):
    monkeypatch.delenv("EMERGENT_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert _resolve_api_key(["EMERGENT_API_KEY", "LLM_API_KEY"]) is None

def test_empty_message():
    resp = client.post("/api/dispatch", json={"message": ""})
    assert resp.status_code == 400

def test_message_too_long():
    resp = client.post("/api/dispatch", json={"message": "x" * 2001})
    assert resp.status_code == 400

def _mock_openai_response(content="Test reply"):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return mock_resp

def _mock_deepai_response(output="DeepAI reply"):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"output": output}
    return mock_resp

def _mock_failed_response():
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    return mock_resp

@patch("backend.dispatch_endpoint.httpx.AsyncClient")
def test_default_routes_to_emergent(MockClient, monkeypatch):
    monkeypatch.setenv("EMERGENT_API_KEY", "test-key")
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_openai_response("Emergent reply"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    MockClient.return_value = mock_client

    resp = client.post("/api/dispatch", json={"message": "Hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "Emergent reply"
    assert data["provider"] == "emergent"
    call_url = mock_client.post.call_args[0][0]
    assert "integrations.emergentagent.com" in call_url

@patch("backend.dispatch_endpoint.httpx.AsyncClient")
def test_explicit_deepseek_routing(MockClient, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_openai_response("DeepSeek reply"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    MockClient.return_value = mock_client

    resp = client.post("/api/dispatch", json={"message": "Hello", "model": "deepseek"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "DeepSeek reply"
    assert data["provider"] == "deepseek"
    call_url = mock_client.post.call_args[0][0]
    assert "api.deepseek.com" in call_url

@patch("backend.dispatch_endpoint.httpx.AsyncClient")
def test_explicit_grok_routing(MockClient, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-key")
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_openai_response("Grok reply"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    MockClient.return_value = mock_client

    resp = client.post("/api/dispatch", json={"message": "Hello", "model": "grok"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "Grok reply"
    assert data["provider"] == "grok"
    call_url = mock_client.post.call_args[0][0]
    assert "api.x.ai" in call_url

@patch("backend.dispatch_endpoint.httpx.AsyncClient")
def test_explicit_deepai_routing(MockClient, monkeypatch):
    monkeypatch.setenv("DEEPAI_API_KEY", "dai-key")
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_deepai_response("DeepAI output"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    MockClient.return_value = mock_client

    resp = client.post("/api/dispatch", json={"message": "Hello", "model": "deepai"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "DeepAI output"
    assert data["provider"] == "deepai"
    call_args = mock_client.post.call_args
    assert "api.deepai.org" in call_args[0][0]
    assert call_args[1]["headers"]["api-key"] == "dai-key"

@patch("backend.dispatch_endpoint.httpx.AsyncClient")
def test_fallback_to_emergent_on_provider_failure(MockClient, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
    monkeypatch.setenv("EMERGENT_API_KEY", "ek")
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=[_mock_failed_response(), _mock_openai_response("Fallback reply")]
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    MockClient.return_value = mock_client

    resp = client.post("/api/dispatch", json={"message": "Hello", "model": "deepseek"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "Fallback reply"
    assert "fallback" in data["provider"]

@patch("backend.dispatch_endpoint.httpx.AsyncClient")
def test_fallback_when_key_missing(MockClient, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EMERGENT_API_KEY", "ek")
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_openai_response("Emergent fallback"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    MockClient.return_value = mock_client

    resp = client.post("/api/dispatch", json={"message": "Hello", "model": "deepseek"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "Emergent fallback"
    assert "fallback" in data["provider"]

@patch("backend.dispatch_endpoint.httpx.AsyncClient")
def test_unknown_model_defaults_to_emergent(MockClient, monkeypatch):
    monkeypatch.setenv("EMERGENT_API_KEY", "ek")
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_openai_response("Default reply"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    MockClient.return_value = mock_client

    resp = client.post("/api/dispatch", json={"message": "Hello", "model": "nonexistent"})
    assert resp.status_code == 200
    assert resp.json()["provider"] == "emergent"

@patch("backend.dispatch_endpoint.httpx.AsyncClient")
def test_all_providers_fail_returns_502(MockClient, monkeypatch):
    for k in ["EMERGENT_API_KEY", "LLM_API_KEY", "EMERGENT_LLM_KEY", "OPENAI_API_KEY"]:
        monkeypatch.delenv(k, raising=False)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    MockClient.return_value = mock_client

    resp = client.post("/api/dispatch", json={"message": "Hello"})
    assert resp.status_code == 502

def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "operational"
