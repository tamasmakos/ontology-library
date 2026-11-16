"""Agent-ready graph projected from the processrecall SEON parser.

The parser (`processrecall.ontology.seon`) is the only reader. This module does not
parse RDF. It turns that parser's `OwlModel`, or the document `digest` returns,
into nodes and edges an agent can load without SPARQL.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from processrecall.ontology.seon.network import IRI_BASE
from processrecall.ontology.seon.owl import OwlModel

if TYPE_CHECKING:
    from collections.abc import Mapping

RDFS_SUBCLASS = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
PARSER = "processrecall.ontology.seon"
PARSER_REPOSITORY = "https://github.com/tamasmakos/processrecall-research"
PARSER_REVISION = "4493f215b4ef7ba500e4bc9a536f5739a03d63aa"


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where a node or edge came from."""

    source_ontology_id: str
    original_iri: str


@dataclass(frozen=True, slots=True)
class Node:
    """One class or property.

    `id` is the parser's stable key. `types` is a subset of ``class``, ``property``,
    ``individual``, and ``datatype``. This parser emits classes and object
    properties only.
    """

    id: str
    iri: str
    label: str | None
    description: str | None
    types: tuple[str, ...]
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class Edge:
    """One specializes or association edge. `id` is stable for the same triple."""

    id: str
    source: str
    target: str
    label: str | None
    description: str | None
    types: tuple[str, ...]
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class Graph:
    """The canonical graph for one catalog entry or one SEON digest."""

    id: str
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    provenance: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready mapping. Nodes and edges are sorted by id."""
        payload = asdict(self)
        payload["nodes"] = sorted(payload["nodes"], key=lambda node: node["id"])
        payload["edges"] = sorted(payload["edges"], key=lambda edge: edge["id"])
        for node in payload["nodes"]:
            node["types"] = list(node["types"])
        for edge in payload["edges"]:
            edge["types"] = list(edge["types"])
        return payload


def graph_from_owl(
    model: OwlModel,
    *,
    ontology_id: str,
    source_url: str,
    license_name: str,
    source_format: str,
) -> Graph:
    """Project `read_owl`'s model. IRIs follow `network.IRI_BASE`."""
    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}
    for owl_class in model.classes.values():
        iri = _concept_iri(owl_class.key)
        nodes[owl_class.key] = _class_node(
            owl_class.key, iri, owl_class.comment, ontology_id
        )
        for parent in owl_class.parents:
            _ensure_class(nodes, parent, ontology_id)
            edge_id = f"specializes:{owl_class.key}:{parent}"
            edges[edge_id] = Edge(
                id=edge_id,
                source=owl_class.key,
                target=parent,
                label="specializes",
                description=None,
                types=("property",),
                provenance=Provenance(ontology_id, RDFS_SUBCLASS),
            )
    for association in model.associations.values():
        iri = IRI_BASE + association.name
        nodes[association.name] = Node(
            id=association.name,
            iri=iri,
            label=association.name,
            description=None,
            types=("property",),
            provenance=Provenance(ontology_id, iri),
        )
        _ensure_class(nodes, association.domain, ontology_id)
        _ensure_class(nodes, association.range, ontology_id)
        edge_id = f"relation:{association.name}"
        edges[edge_id] = Edge(
            id=edge_id,
            source=association.domain,
            target=association.range,
            label=association.name,
            description=None,
            types=("property",),
            provenance=Provenance(ontology_id, iri),
        )
    return _graph(ontology_id, nodes, edges, source_url, license_name, source_format, "read_owl")


def graph_from_digest(
    document: Mapping[str, Any],
    *,
    ontology_id: str,
    source_url: str,
    license_name: str,
) -> Graph:
    """Project concept nodes out of the document `digest` returns."""
    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}
    for concept in _concepts(document.get("network", {})):
        key = str(concept["key"])
        iri = str(concept.get("iri") or _concept_iri(key))
        nodes[key] = _class_node(key, iri, concept.get("definition"), ontology_id)
        for raw in concept.get("edges", ()):
            kind = raw.get("type")
            target = str(raw["target"])
            if kind == "specializes":
                _ensure_class(nodes, target, ontology_id)
                edge_id = f"specializes:{key}:{target}"
                edges[edge_id] = Edge(
                    id=edge_id,
                    source=key,
                    target=target,
                    label="specializes",
                    description=None,
                    types=("property",),
                    provenance=Provenance(ontology_id, RDFS_SUBCLASS),
                )
            elif kind == "relation" and raw.get("association"):
                name = str(raw["association"])
                property_iri = IRI_BASE + name
                nodes.setdefault(
                    name,
                    Node(
                        id=name,
                        iri=property_iri,
                        label=raw.get("predicate") or name,
                        description=None,
                        types=("property",),
                        provenance=Provenance(ontology_id, property_iri),
                    ),
                )
                _ensure_class(nodes, target, ontology_id)
                edge_id = f"relation:{name}"
                edges[edge_id] = Edge(
                    id=edge_id,
                    source=key,
                    target=target,
                    label=raw.get("predicate") or name,
                    description=None,
                    types=("property",),
                    provenance=Provenance(ontology_id, property_iri),
                )
    return _graph(ontology_id, nodes, edges, source_url, license_name, "seon", "digest")


def _graph(
    ontology_id: str,
    nodes: dict[str, Node],
    edges: dict[str, Edge],
    source_url: str,
    license_name: str,
    source_format: str,
    entry: str,
) -> Graph:
    return Graph(
        id=ontology_id,
        nodes=tuple(sorted(nodes.values(), key=lambda node: node.id)),
        edges=tuple(sorted(edges.values(), key=lambda edge: edge.id)),
        provenance={
            "source_ontology_id": ontology_id,
            "source_url": source_url,
            "license": license_name,
            "format": source_format,
            "parser": f"{PARSER}.{entry}",
            "parser_repository": PARSER_REPOSITORY,
            "parser_revision": PARSER_REVISION,
        },
    )


def _class_node(key: str, iri: str, description: object, ontology_id: str) -> Node:
    text = description.strip() if isinstance(description, str) else ""
    label = key.split("::", 1)[1] if "::" in key else key
    return Node(
        id=key,
        iri=iri,
        label=label or None,
        description=text or None,
        types=("class",),
        provenance=Provenance(ontology_id, iri),
    )


def _ensure_class(nodes: dict[str, Node], key: str, ontology_id: str) -> None:
    if key not in nodes:
        iri = _concept_iri(key)
        nodes[key] = _class_node(key, iri, None, ontology_id)


def _concept_iri(key: str) -> str:
    return IRI_BASE + key.replace(" ", "_")


def _concepts(node: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if node.get("kind") == "concept":
            found.append(node)
        for value in node.values():
            found.extend(_concepts(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_concepts(value))
    return found
