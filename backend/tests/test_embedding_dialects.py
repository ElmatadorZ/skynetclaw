"""
test_embedding_dialects.py — embeddings must work with Ollama AND with an API
============================================================================
The requirement is that SkynetClaw runs against a local Ollama or against an API
on every machine it is installed on. Embeddings were the one path that did not.

Ollama and OpenAI disagree on every detail:

    Ollama   POST /api/embeddings  {"model","prompt"}  →  {"embedding": [...]}
    OpenAI   POST /embeddings      {"model","input"}   →  {"data":[{"embedding":[...]}]}

Three endpoints — vault indexing, semantic note search, and chat context recall —
spoke only Ollama's dialect and read r.json()["embedding"] directly. On an
API-only install those returned 404 and then raised on the missing key.
runtime_plugins/openai_driver.py had the OpenAI shape right all along; the call
sites simply bypassed it.

    python -m pytest tests/test_embedding_dialects.py -q
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

import main  # noqa: E402


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload

    def json(self):
        return self._p


class _Client:
    """Records the call so the test can assert the DIALECT, not just the result."""

    def __init__(self, status=200, payload=None):
        self.status, self.payload, self.calls = status, payload, []

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers or {}})
        return _Resp(self.status, self.payload)


def _run(coro):
    # asyncio.run, not get_event_loop: the latter raises on 3.14+.
    return asyncio.run(coro)


@pytest.fixture()
def client(monkeypatch):
    c = _Client()
    monkeypatch.setattr(main, "_client", c)
    return c


# ── Ollama dialect ───────────────────────────────────────────────────────────
def test_ollama_connection_uses_ollama_route_and_fields(client):
    client.payload = {"embedding": [0.1, 0.2, 0.3]}
    out = _run(main.embed_text("hello", "nomic-embed-text", conn={
        "base_url": "http://127.0.0.1:11434", "api_key": "", "api_type": "ollama"}))
    assert out == [0.1, 0.2, 0.3]
    call = client.calls[0]
    assert call["url"].endswith("/api/embeddings")
    assert call["json"]["prompt"] == "hello"     # Ollama's field
    assert "input" not in call["json"]


# ── OpenAI / cloud dialect ───────────────────────────────────────────────────
def test_openai_connection_uses_openai_route_and_fields(client):
    client.payload = {"data": [{"embedding": [0.4, 0.5]}]}
    out = _run(main.embed_text("hello", "text-embedding-3-small", conn={
        "base_url": "https://api.openai.com/v1", "api_key": "sk-x",
        "api_type": "openai"}))
    assert out == [0.4, 0.5], "the OpenAI response shape must be unwrapped"
    call = client.calls[0]
    assert call["url"] == "https://api.openai.com/v1/embeddings"
    assert call["json"]["input"] == "hello"      # OpenAI's field
    assert "prompt" not in call["json"]
    assert call["headers"]["Authorization"] == "Bearer sk-x"


def test_any_non_ollama_api_type_takes_the_openai_path(client):
    """llama.cpp, LM Studio, vLLM and the cloud adapters all speak this shape."""
    client.payload = {"data": [{"embedding": [1.0]}]}
    for api in ("openai", "custom", "groq", "together", "deepseek"):
        client.calls.clear()
        out = _run(main.embed_text("x", "m", conn={
            "base_url": "http://h/v1", "api_key": "k", "api_type": api}))
        assert out == [1.0]
        assert client.calls[0]["url"].endswith("/embeddings")
        assert not client.calls[0]["url"].endswith("/api/embeddings")


def test_no_key_sends_no_authorization_header(client):
    client.payload = {"embedding": [1.0]}
    _run(main.embed_text("x", "m", conn={
        "base_url": "http://127.0.0.1:11434", "api_key": "", "api_type": "ollama"}))
    assert "Authorization" not in client.calls[0]["headers"]


# ── honest degradation ───────────────────────────────────────────────────────
def test_a_non_200_returns_empty_not_a_zero_vector(client):
    """An empty list lets the caller fall back to keyword search. A zero vector
    would make every cosine similarity identical and look like a working search."""
    client.status, client.payload = 404, {}
    out = _run(main.embed_text("x", "m", conn={
        "base_url": "http://h/v1", "api_key": "", "api_type": "openai"}))
    assert out == []


def test_a_transport_failure_returns_empty_and_does_not_raise(monkeypatch):
    class _Boom:
        async def post(self, *a, **k):
            raise OSError("connection refused")
    monkeypatch.setattr(main, "_client", _Boom())
    assert _run(main.embed_text("x", "m", conn={
        "base_url": "http://nope", "api_key": "", "api_type": "ollama"})) == []


def test_a_malformed_response_returns_empty(client):
    client.payload = {"unexpected": "shape"}
    assert _run(main.embed_text("x", "m", conn={
        "base_url": "http://h/v1", "api_key": "", "api_type": "openai"})) == []


def test_no_call_site_still_speaks_ollama_directly():
    """Regression guard: the three endpoints must go through embed_text()."""
    src = (_BASE / "main.py").read_text(encoding="utf-8")
    # Only the helper itself may name Ollama's embedding route: once in its
    # docstring, once in its ollama branch.
    assert src.count("/api/embeddings") == 2, (
        "a call site is speaking Ollama's embedding dialect again — route it "
        "through embed_text() so an API-only install keeps working")
