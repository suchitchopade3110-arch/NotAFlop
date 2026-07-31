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
