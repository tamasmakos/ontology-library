"""The load path calls the research parser and projects its model."""

from __future__ import annotations

from pathlib import Path

import pytest
from processrecall.ontology.seon.owl import read_owl

from ontology_library import parse
from ontology_library.parse import OntologyLoadError, read_owl as bound_reader

FIXTURES = Path(__file__).parent / "fixtures"


def test_reader_is_the_research_parser() -> None:
    assert bound_reader is read_owl


def test_seon_fixture_projects_classes_and_associations() -> None:
    graph = parse(FIXTURES / "seon_min.owl", "rdfxml", ontology_id="example")
    again = parse(FIXTURES / "seon_min.owl", "owl", ontology_id="example")
    assert graph.nodes == again.nodes
    assert graph.edges == again.edges
    by_id = {node.id: node for node in graph.nodes}
    assert by_id["EX::Person"].types == ("class",)
    assert by_id["EX::Person"].label == "Person"
    assert by_id["EX::Person"].description == "A person."
    assert by_id["EX::Person"].provenance.source_ontology_id == "example"
    assert by_id["EX::Person"].provenance.original_iri.endswith("EX::Person")
    assert by_id["knows.Person+Person"].types == ("property",)
    edge_ids = {edge.id for edge in graph.edges}
    assert "specializes:EX::Person:EX::Agent" in edge_ids
    assert "relation:knows.Person+Person" in edge_ids
    specializes = next(edge for edge in graph.edges if edge.id.startswith("specializes:"))
    assert specializes.types == ("property",)
    assert specializes.provenance.original_iri.endswith("subClassOf")


def test_plain_owl_uses_the_same_reader() -> None:
    graph = parse(FIXTURES / "not_seon.owl", "rdfxml", ontology_id="example")
    by_id = {node.id: node for node in graph.nodes}
    person = by_id["http://example.org/Person"]
    assert person.types == ("class",)
    assert person.iri == "http://example.org/Person"
    assert person.provenance.source_ontology_id == "example"
    assert graph.provenance["parser"] == "processrecall.ontology.seon.read_owl"


def test_turtle_uses_the_same_reader() -> None:
    graph = parse(FIXTURES / "not_xml.ttl", "turtle", ontology_id="example")
    by_id = {node.id: node for node in graph.nodes}
    person = by_id["http://example.org/Person"]
    assert "individual" in person.types
    assert person.provenance.original_iri == "http://example.org/Person"


def test_seon_directory_calls_digest(tmp_path: Path) -> None:
    with pytest.raises(OntologyLoadError) as caught:
        parse(tmp_path, "seon", ontology_id="seon")
    assert "digest" in str(caught.value)


def test_unknown_format() -> None:
    with pytest.raises(OntologyLoadError, match="unknown format"):
        parse(FIXTURES / "seon_min.owl", "kif", ontology_id="example")
