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
RDFS_SUBPROPERTY = "http://www.w3.org/2000/01/rdf-schema#subPropertyOf"
RDFS_DOMAIN = "http://www.w3.org/2000/01/rdf-schema#domain"
RDFS_RANGE = "http://www.w3.org/2000/01/rdf-schema#range"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
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
    ``individual``, and ``datatype``.
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
    """Project `read_owl`'s model. SEON keys still use `network.IRI_BASE`."""
    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}
    datatypes = dict(model.datatypes)
    for iri, label in datatypes.items():
        nodes[iri] = _term_node(iri, label, None, ("datatype",), ontology_id)
    for owl_class in model.classes.values():
        iri = _absolute(owl_class.key)
        nodes[owl_class.key] = _class_node(
            owl_class.key,
            iri,
            owl_class.comment,
            ontology_id,
            label=owl_class.label or None,
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
        if _is_iri(association.name):
            _project_property(nodes, edges, association, datatypes, ontology_id)
            continue
        iri = IRI_BASE + association.name
        nodes[association.name] = Node(
            id=association.name,
            iri=iri,
            label=association.label or association.name,
            description=association.comment or None,
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
            label=association.label or association.name,
            description=None,
            types=("property",),
            provenance=Provenance(ontology_id, iri),
        )
    for individual in model.individuals.values():
        _project_individual(nodes, edges, individual, datatypes, ontology_id)
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


def _project_property(
    nodes: dict[str, Node],
    edges: dict[str, Edge],
    association: Any,
    datatypes: Mapping[str, str],
    ontology_id: str,
) -> None:
    iri = association.name
    nodes[iri] = _term_node(
        iri,
        association.label or _local(iri),
        association.comment,
        ("property",),
        ontology_id,
    )
    for parent in association.parents:
        _ensure_term(nodes, parent, datatypes, ontology_id, ("property",))
        edges[f"specializes:{iri}:{parent}"] = Edge(
            id=f"specializes:{iri}:{parent}",
            source=iri,
            target=parent,
            label="specializes",
            description=None,
            types=("property",),
            provenance=Provenance(ontology_id, RDFS_SUBPROPERTY),
        )
    for domain in association.domains:
        _ensure_term(nodes, domain, datatypes, ontology_id, ("class",))
        edges[f"domain:{iri}:{domain}"] = Edge(
            id=f"domain:{iri}:{domain}",
            source=iri,
            target=domain,
            label="domain",
            description=None,
            types=("property",),
            provenance=Provenance(ontology_id, RDFS_DOMAIN),
        )
    for range_iri in association.ranges:
        kind = ("datatype",) if range_iri in datatypes else ("class",)
        _ensure_term(nodes, range_iri, datatypes, ontology_id, kind)
        edges[f"range:{iri}:{range_iri}"] = Edge(
            id=f"range:{iri}:{range_iri}",
            source=iri,
            target=range_iri,
            label="range",
            description=None,
            types=("property",),
            provenance=Provenance(ontology_id, RDFS_RANGE),
        )
    if len(association.domains) == 1 and len(association.ranges) == 1:
        edges[f"relation:{iri}"] = Edge(
            id=f"relation:{iri}",
            source=association.domains[0],
            target=association.ranges[0],
            label=association.label or _local(iri),
            description=None,
            types=("property",),
            provenance=Provenance(ontology_id, iri),
        )


def _project_individual(
    nodes: dict[str, Node],
    edges: dict[str, Edge],
    individual: Any,
    datatypes: Mapping[str, str],
    ontology_id: str,
) -> None:
    iri = individual.key
    label = individual.label or _local(iri)
    description = individual.comment or None
    existing = nodes.get(iri)
    types = ("individual",) if existing is None else tuple(dict.fromkeys((*existing.types, "individual")))
    nodes[iri] = Node(
        id=iri,
        iri=_absolute(iri),
        label=label or (existing.label if existing else None),
        description=description or (existing.description if existing else None),
        types=types,
        provenance=Provenance(ontology_id, _absolute(iri)),
    )
    for type_iri in individual.types:
        _ensure_term(nodes, type_iri, datatypes, ontology_id, ("class",))
        edges[f"type:{iri}:{type_iri}"] = Edge(
            id=f"type:{iri}:{type_iri}",
            source=iri,
            target=type_iri,
            label="type",
            description=None,
            types=("property",),
            provenance=Provenance(ontology_id, RDF_TYPE),
        )


def _class_node(
    key: str,
    iri: str,
    description: object,
    ontology_id: str,
    *,
    label: str | None = None,
) -> Node:
    text = description.strip() if isinstance(description, str) else ""
    if not label:
        label = key.split("::", 1)[1] if "::" in key else key
    return Node(
        id=key,
        iri=iri,
        label=label or None,
        description=text or None,
        types=("class",),
        provenance=Provenance(ontology_id, iri),
    )


def _term_node(
    iri: str,
    label: str | None,
    description: object,
    types: tuple[str, ...],
    ontology_id: str,
) -> Node:
    text = description.strip() if isinstance(description, str) else ""
    return Node(
        id=iri,
        iri=iri,
        label=label or _local(iri),
        description=text or None,
        types=types,
        provenance=Provenance(ontology_id, iri),
    )


def _ensure_class(nodes: dict[str, Node], key: str, ontology_id: str) -> None:
    if key and key not in nodes:
        nodes[key] = _class_node(key, _absolute(key), None, ontology_id)


def _ensure_term(
    nodes: dict[str, Node],
    key: str,
    datatypes: Mapping[str, str],
    ontology_id: str,
    types: tuple[str, ...],
) -> None:
    if not key or key in nodes:
        return
    if key in datatypes or types == ("datatype",):
        nodes[key] = _term_node(key, datatypes.get(key) or _local(key), None, ("datatype",), ontology_id)
    else:
        nodes[key] = _class_node(key, _absolute(key), None, ontology_id, label=_local(key) if _is_iri(key) else None)


def _concept_iri(key: str) -> str:
    return IRI_BASE + key.replace(" ", "_")


def _absolute(key: str) -> str:
    if _is_iri(key):
        return key
    return _concept_iri(key)


def _is_iri(key: str) -> bool:
    return key.startswith(("http://", "https://", "urn:"))


def _local(iri: str) -> str:
    for separator in ("#", "/"):
        if separator in iri:
            tail = iri.rsplit(separator, 1)[-1]
            if tail:
                return tail
    return iri


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
