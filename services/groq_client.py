import httpx
from core.config import GROQ_API_KEY, WHISPER_MODEL

GROQ_BASE = "https://api.groq.com/openai/v1"

_headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}


async def transcribe_audio(audio_bytes: bytes, filename: str = "pitch.webm") -> str:
    """Send raw audio bytes to GROQ Whisper. Returns transcript string."""
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            f"{GROQ_BASE}/audio/transcriptions",
            headers=_headers,
            files={"file": (filename, audio_bytes, "audio/webm")},
            data={"model": WHISPER_MODEL, "response_format": "json", "language": "en"},
        )
        res.raise_for_status()
        return res.json()["text"].strip()


async def chat(model: str, system: str, user: str, max_tokens: int = 300, temperature: float | None = None) -> str:
    """Single-turn chat completion via GROQ.

    temperature is opt-in and omitted from the request by default, leaving
    Groq's own default in effect for callers that don't pass it — only
    callers that need deterministic output (e.g. Phase 1's pass/fail
    filter) should set it explicitly.
    """
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if temperature is not None:
        payload["temperature"] = temperature

    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.post(
            f"{GROQ_BASE}/chat/completions",
            headers={**_headers, "Content-Type": "application/json"},
            json=payload,
        )
        if res.status_code >= 400:
            print(f"Groq error body: {res.text}")
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()