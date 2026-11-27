from app.openlibrary import matching_doc, parse_description, record_from_doc
from app.rules.catalog import CatalogRecord


def test_a_string_description_and_an_object_description_both_parse():
    assert parse_description({"description": "A ship sinks."}) == "A ship sinks."
    assert parse_description({"description": {"value": "A ship sinks."}}) == "A ship sinks."
    assert parse_description({}) is None


def test_a_search_document_becomes_a_record():
    record = record_from_doc(
        {
            "title": "Dead Wake",
            "author_name": ["Erik Larson"],
            "first_publish_year": 2015,
            "number_of_pages_median": 430,
            "isbn": ["9780804194617"],
        },
        "The last crossing.",
    )
    assert record == CatalogRecord(
        "Dead Wake", "Erik Larson", 2015, 430, "9780804194617", "The last crossing."
    )


def test_matching_doc_skips_a_different_book():
    docs = [
        {"title": "The Bear and the Nightingale", "author_name": ["Katherine Arden"]},
        {"title": "Blood Music", "author_name": ["Greg Bear"]},
    ]
    found = matching_doc(docs, "Blood Music", "Greg Bear")
    assert found is not None
    assert found["title"] == "Blood Music"
