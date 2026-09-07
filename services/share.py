"""
Public share-card content (B2, No-Go Share Hook). GET /v1/share/{token}
must never leak raw pitch text, email, or evidence payloads — headline
reasons are derived from dimension name + score only, never agent
feedback text. That's not just a router-level filter: feedback text
isn't even persisted on a SnapshotDocument (see models.documents), so
there's nothing pitch-specific for this path to leak by construction.
"""
from services.gate import WEIGHTS


def top_reasons(agent_scores: dict[str, int], verdict: str, n: int = 3) -> list[str]:
    scored = [
        (name, score, WEIGHTS.get(name, 1.0)) for name, score in agent_scores.items() if name in WEIGHTS
    ]
    if not scored:
        return []

    if verdict == "go":
        picked = sorted(scored, key=lambda row: row[1] * row[2], reverse=True)[:n]
        template = "Strong {label} ({score}/10)"
    else:
        picked = sorted(scored, key=lambda row: (10 - row[1]) * row[2], reverse=True)[:n]
        template = "Weak {label} ({score}/10)"

    return [template.format(label=name.replace("_", " ").title(), score=score) for name, score, _ in picked]
