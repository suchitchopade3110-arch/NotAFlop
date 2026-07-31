"""
10-100 Lovers Test — per Paul Graham's framing: a handful of users who
would be devastated to lose the product is stronger evidence than a
large addressable market with only lukewarm interest.

Stub pass: a SpecialistAgent like the 11 core agents in
specialist_agents.py — the Reddit/HN signals it needs are already
serialized into the prompt by BaseAgent.build_user_message, so no new
plumbing is required to "consume" them. A later pass should parse
pain_frequency/sentiment/post_count directly rather than leaving the
model to read them out of the raw JSON blob.
"""
from agents.base_agent import SpecialistAgent
from core.config import ANALYSIS_MODEL

lovers_test_agent = SpecialistAgent(
    "lovers_test",
    "10-100 Lovers Test",
    "Reward strong evidence of a small group of people who would be genuinely upset to "
    "lose this product — frequent, specific, emotionally intense pain in the Reddit/Hacker "
    "News signals (high pain_frequency, frustrated sentiment, repeated posts on the same "
    "problem). Penalize ideas that look good only on TAM size or trend data but show no one "
    "desperately wants them yet.",
    ANALYSIS_MODEL,
)
