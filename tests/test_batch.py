"""Vendored catalog files load through the same read_owl path."""

from __future__ import annotations

import pytest

from ontology_library import list_ontologies, load_ontology

SAMPLES = (
    ("skos", "rdfxml", "http://www.w3.org/2004/02/skos/core#Concept", "class"),
    ("rdfs", "turtle", "http://www.w3.org/2000/01/rdf-schema#Resource", "class"),
    ("schemaorg", "jsonld", "https://schema.org/Person", "class"),
)


@pytest.mark.parametrize(("ontology_id", "source_format", "iri", "node_type"), SAMPLES)
def test_real_batch_file(ontology_id: str, source_format: str, iri: str, node_type: str) -> None:
    record = next(item for item in list_ontologies() if item.id == ontology_id)
    assert record.format == source_format
    assert record.distribution == "vendored"
    graph = load_ontology(ontology_id)
    match = next(node for node in graph.nodes if node.iri == iri)
    assert node_type in match.types
    assert match.provenance.source_ontology_id == ontology_id
    assert graph.provenance["parser"] == "processrecall.ontology.seon.read_owl"
    assert graph.provenance["format"] == source_format


def test_every_vendored_ontology_loads() -> None:
    for record in list_ontologies():
        graph = load_ontology(record.id)
        assert graph.id == record.id
        assert graph.nodes
        assert any("class" in node.types for node in graph.nodes)
