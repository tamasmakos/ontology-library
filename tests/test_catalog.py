"""Manifest rows stay complete, and vendored bytes are the files they name."""

from __future__ import annotations

from importlib.resources import files

import pytest

from ontology_library import list_ontologies, load_ontology
from ontology_library.catalog import OntologyLookupError


def test_manifest_lists_licensed_ontologies() -> None:
    records = list_ontologies()
    ids = [record.id for record in records]
    assert len(ids) == len(set(ids))
    assert "skos" in ids
    assert "bfo" in ids
    assert "schemaorg" in ids
    root = files("ontology_library").joinpath("data")
    for record in records:
        assert record.name
        assert record.source_url.startswith("http")
        assert record.license
        assert record.license_url.startswith("http")
        assert record.format
        assert record.distribution == "vendored"
        assert record.path
        assert root.joinpath(record.path).is_file()


def test_unknown_ontology_names_the_known_ids() -> None:
    with pytest.raises(OntologyLookupError, match="skos"):
        load_ontology("missing")
