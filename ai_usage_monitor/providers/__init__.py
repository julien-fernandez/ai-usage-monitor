from __future__ import annotations

from . import claude_code, deepgram, elevenlabs, fireflies, gladia, groq, openrouter
from .base import Provider

PROVIDERS: list[Provider] = [
    elevenlabs.PROVIDER,
    openrouter.PROVIDER,
    deepgram.PROVIDER,
    gladia.PROVIDER,
    groq.PROVIDER,
    fireflies.PROVIDER,
    claude_code.PROVIDER,
]

__all__ = ["PROVIDERS", "Provider"]
