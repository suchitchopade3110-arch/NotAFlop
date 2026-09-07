from nanoid import generate as _nanoid_generate

# Unambiguous, URL-safe, no look-alike chars (0/O, 1/I/l excluded) — these
# IDs get typed and shared in URLs, not just stored.
_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ"
_SIZE = 10


def generate_public_id() -> str:
    """Short, shareable, non-guessable report ID. Not a Mongo ObjectId."""
    return _nanoid_generate(alphabet=_ALPHABET, size=_SIZE)


def generate_session_id() -> str:
    return _nanoid_generate(alphabet=_ALPHABET, size=_SIZE * 2)


# Phase 2 (living verdict / evidence log): every new domain gets its own
# prefixed id — same alphabet/collision properties as generate_public_id,
# just tagged so an id is self-describing wherever it shows up (a URL, a
# log line, a support ticket) instead of being an opaque string that could
# belong to any collection.
def _prefixed(prefix: str) -> str:
    return f"{prefix}_{_nanoid_generate(alphabet=_ALPHABET, size=_SIZE)}"


def generate_idea_id() -> str:
    return _prefixed("idea")


def generate_snapshot_id() -> str:
    return _prefixed("snap")


def generate_criterion_id() -> str:
    return _prefixed("crit")


def generate_evidence_id() -> str:
    return _prefixed("ev")


def generate_account_id() -> str:
    return _prefixed("acct")


def generate_milestone_id() -> str:
    return _prefixed("mile")


def generate_share_token() -> str:
    """Deliberately longer/higher-entropy than a public_id — this token is
    the sole gate on GET /v1/share/{token}, a public no-auth route, so it
    has to resist guessing on its own rather than relying on obscurity."""
    return _nanoid_generate(alphabet=_ALPHABET, size=_SIZE * 3)


def generate_magic_link_token() -> str:
    """Single-use auth token — same high-entropy sizing as a share token,
    since it's a bearer credential (see services/auth_tokens.py)."""
    return _nanoid_generate(alphabet=_ALPHABET, size=_SIZE * 3)
