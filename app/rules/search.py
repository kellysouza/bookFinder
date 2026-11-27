"""How close a stored description has to be before it is shown."""

# A controlled-society description scores about 0.43 against that query.
# A banana-bread line scores about 0.27. 0.35 sits between them.
SIMILARITY_THRESHOLD = 0.35


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return the cosine similarity of two embeddings, from -1 to 1.

    A pair of different lengths, or an empty pair, scores 0.
    """
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(one * other for one, other in zip(left, right, strict=True))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def passes_threshold(score: float) -> bool:
    """Return whether a cosine similarity is high enough to show the passage."""
    return score >= SIMILARITY_THRESHOLD
