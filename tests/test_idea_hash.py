from repositories.report_repository import compute_idea_hash, normalize_idea


def test_normalize_collapses_case_punctuation_whitespace():
    a = normalize_idea("Uber for Dog-Walking!!  It is great.")
    b = normalize_idea("uber for dog walking  it is great")
    assert a == b


def test_normalize_apostrophes_become_spaces_not_deleted():
    # Punctuation is replaced with a space, not deleted — "it's" becomes
    # "it s", not "its". Documented behavior, asserted explicitly so a
    # future change to this rule is a visible, intentional decision.
    assert normalize_idea("it's great") == "it s great"


def test_normalize_strips_leading_trailing_whitespace():
    assert normalize_idea("  hello world  ") == "hello world"


def test_hash_stable_for_equivalent_phrasing():
    h1 = compute_idea_hash("Uber for Dog-Walking!")
    h2 = compute_idea_hash("  uber   for dog walking ")
    assert h1 == h2


def test_hash_differs_for_different_ideas():
    h1 = compute_idea_hash("Uber for dog walking")
    h2 = compute_idea_hash("Uber for cat sitting")
    assert h1 != h2


def test_hash_is_deterministic():
    text = "Freelance invoicing automation"
    assert compute_idea_hash(text) == compute_idea_hash(text)
