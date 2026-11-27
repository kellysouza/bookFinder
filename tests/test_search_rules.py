from app.embeddings import FakeEmbedder
from app.rules.search import passes_threshold


def test_a_related_description_passes_and_an_unrelated_one_does_not():
    embedder = FakeEmbedder()
    query, related, unrelated = embedder.embed([
        "a book about a controlled society",
        "A controlled society assigns people to castes and bans old books.",
        "a recipe for banana bread with walnuts",
    ])
    related_score = sum(left * right for left, right in zip(query, related, strict=True))
    unrelated_score = sum(left * right for left, right in zip(query, unrelated, strict=True))
    assert passes_threshold(related_score)
    assert not passes_threshold(unrelated_score)
