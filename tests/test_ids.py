from core.ids import generate_public_id, generate_session_id


def test_public_id_shape():
    pid = generate_public_id()
    assert len(pid) == 10
    assert all(c in "23456789abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ" for c in pid)


def test_public_id_excludes_ambiguous_chars():
    ambiguous = set("0O1Il")
    ids = {generate_public_id() for _ in range(200)}
    for pid in ids:
        assert not (set(pid) & ambiguous)


def test_public_id_uniqueness():
    ids = {generate_public_id() for _ in range(500)}
    assert len(ids) == 500


def test_session_id_longer_than_public_id():
    assert len(generate_session_id()) > len(generate_public_id())
