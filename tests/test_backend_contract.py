"""Smoke test: confirm GeminiBackend conforms to the ChatBackend Protocol."""

from __future__ import annotations

import pytest

from brain.contract import ChatBackend, ChatRequest


def test_stub_conforms_to_protocol():
    class _Stub:
        async def reply(self, request: ChatRequest) -> str: ...
        async def aclose(self) -> None: ...

    assert isinstance(_Stub(), ChatBackend)


def test_gemini_backend_conforms_to_protocol():
    google_genai = pytest.importorskip("google.genai")  # noqa: F841
    from brain.gemini import GeminiBackend

    assert hasattr(GeminiBackend, "reply")
    assert hasattr(GeminiBackend, "aclose")
