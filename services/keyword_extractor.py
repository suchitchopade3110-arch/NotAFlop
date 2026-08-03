import logging
from core.config import FILTER_MODEL
from services.groq_client import chat

logger = logging.getLogger("notaflop.keyword_extractor")


class KeywordExtractionError(Exception):
    """Raised when keyword extraction produces an invalid or unparseable result."""
    pass


KEYWORD_PROMPT = """You are a search term extractor for a market intelligence tool.
Read this founder's pitch transcript and extract a concise 2 to 5 word search phrase that best captures the core product, industry, or problem topic.
Rules:
- Respond ONLY with the 2-5 word search phrase.
- No punctuation, quotes, markdown, or explanation.
- Example pitch: "We built an AI platform that writes unit tests for Python developers." -> "AI unit test generator"
"""


async def extract_keyword(transcript: str) -> str:
    """Extract a 2-5 word topic search phrase from pitch transcript using cheap FILTER_MODEL."""
    if not transcript or not transcript.strip():
        raise KeywordExtractionError("Transcript is empty.")

    raw = await chat(FILTER_MODEL, KEYWORD_PROMPT, transcript.strip(), max_tokens=50)
    keyword = raw.strip().strip('"\'`')

    # Validation: empty, under 3 chars, or over 8 words
    word_count = len(keyword.split())
    if not keyword or len(keyword) < 3 or word_count > 8:
        logger.warning(
            "extracted_keyword_rejected transcript_excerpt=%r keyword=%r word_count=%d",
            transcript[:50],
            keyword,
            word_count,
        )
        raise KeywordExtractionError(
            f"Extracted keyword '{keyword}' is invalid (length: {len(keyword)}, words: {word_count})."
        )

    logger.info("extracted_keyword transcript_excerpt=%r keyword=%r", transcript[:50], keyword)
    return keyword
