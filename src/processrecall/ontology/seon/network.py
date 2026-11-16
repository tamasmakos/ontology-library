"""Assemble SEON into one nested adjacency list: layers, ontologies, packages, concepts.

Containment is the nesting; every other connection is an outgoing ``edges`` entry on
its source node. Concepts carry ``specializes`` and ``relation`` edges. Ontologies
carry what their authors declared (``declares_dependency``) apart from what the
concepts actually do (``depends_on``, ``specializes_from``), and the two are never
reconciled.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from processrecall.ontology.seon import DigestError
from processrecall.ontology.seon.concepts import ConceptRow, read_concepts
from processrecall.ontology.seon.defects import (
    AMBIGUOUS_GENERALIZATIONS,
    DUPLICATE_CONCEPTS,
    KNOWN_DEFECTS,
    UNGROUNDED_CONCEPTS,
)
from processrecall.ontology.seon.owl import NAMESPACE, OwlModel, read_owl
from processrecall.ontology.seon.pages import (
    ConceptBlock,
    MenuEntry,
    OntologyPage,
    Section,
    read_menu,
    read_page,
)
from processrecall.ontology.seon.relations import (
    FOUNDATION,
    PrintedLines,
    Relation,
    join_relations,
    ontology_of,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

VERSION = "1.0.5"
IRI_BASE = f"https://{NAMESPACE}"
_LEFTOVER_PAGE = (
    "June 2017 page left from an earlier build; absent from the 1.0.5 menu, OWL and exports."
)
PROVENANCE = {
    "seon_version": VERSION,
    "site": "https://dev.nemo.inf.ufes.br/seon/",
    "repository": "https://github.com/fabianoruy/SEON",
    "commit": "521df2591ad1e29d399030f6b34ada0b65d42068",
    "owl_namespace": NAMESPACE,
    "iri_base": IRI_BASE,
    "excluded": [
        {"ontology": "SwAO", "reason": _LEFTOVER_PAGE},
        {"ontology": "IntO", "reason": _LEFTOVER_PAGE},
    ],
}

Node = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Sources:
    """The pinned inputs, read."""

    owl: OwlModel
    rows: tuple[ConceptRow, ...]
    menu: tuple[MenuEntry, ...]
    pages: Mapping[str, OntologyPage]

    @classmethod
    def read(cls, root: Path) -> Sources:
        """Read every input under *root* (``packages/ontology/seon-1.0.5``)."""
        menu = read_menu(root / "pages" / "menu.html")
        return cls(
            owl=read_owl(root / "SEON.owl"),
            rows=read_concepts(root / "data" / "info.csv"),
            menu=menu,
            pages={
                entry.short_name: read_page(root / "pages" / f"{entry.short_name}.html")
                for entry in menu
            },
        )


@dataclass(frozen=True, slots=True)
class Concept:
    """A concept joined across ``info.csv``, its page block and (outside UFO) the OWL."""

    key: str
    ontology: str
    packages: tuple[str, ...]
    label: str
    stereotype: str | None
    definition: str | None
    example: str | None
    parents: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Network:
    """Every concept and relation, before it is laid out as a tree."""

    sources: Sources
    concepts: Mapping[str, Concept]
    relations: tuple[Relation, ...]


def digest(root: Path) -> Node:
    """Read the inputs under *root* and return the network as JSON-ready data."""
    sources = Sources.read(root)
    blocks = _join_blocks(sources)
    concepts = {
        concept.key: concept for concept in (_concept(key, pair) for key, pair in blocks.items())
    }
    _require_owl_classes(concepts, blocks, sources.owl)
    printed = PrintedLines(
        labels={key: concept.label for key, concept in concepts.items()},
        lines={key: block.relation_lines for key, (_, block) in blocks.items()},
    )
    network = Network(
        sources=sources, concepts=concepts, relations=join_relations(printed, sources.owl)
    )
    _require_hierarchy(concepts)
    document = {
        "provenance": {
            **PROVENANCE,
            "known_defects": [
                {"key": d.key, "description": d.description, "resolution": d.resolution}
                for d in KNOWN_DEFECTS
            ],
        },
        "network": _network_node(network),
        "predicates": _predicates(network.relations),
    }
    _require_closed(document)
    return document


def concept_key(row: ConceptRow) -> str:
    """The row's qualified name, suffixed with its package when SEON publishes it twice."""
    if row.qualified_name in DUPLICATE_CONCEPTS:
        return f"{row.qualified_name}@{row.packages[-1]}"
    return row.qualified_name


def owl_comment(definition: str) -> str:
    """Normalize a definition the way ``OwlWriter`` does for ``rdfs:comment``."""
    text = unicodedata.normalize("NFD", definition.replace('"', ""))
    return text.encode("ascii", "ignore").decode("ascii").replace("\n", " ")


# -- the concept join -------------------------------------------------------------


def _join_blocks(sources: Sources) -> dict[str, tuple[ConceptRow, ConceptBlock]]:
    counts = Counter(row.qualified_name for row in sources.rows)
    duplicates = {name for name, count in counts.items() if count > 1}
    if duplicates != DUPLICATE_CONCEPTS.keys():
        raise DigestError(f"duplicate concepts differ from the known defect: {sorted(duplicates)}")
    blocks = {
        (b.qualified_name, b.parents): b for page in sources.pages.values() for b in page.blocks
    }
    if len(blocks) != sum(len(page.blocks) for page in sources.pages.values()):
        raise DigestError("two concept blocks share a name and generalizations")
    joined = {
        concept_key(row): (row, blocks.pop((row.qualified_name, row.parents), None))
        for row in sources.rows
    }
    if blocks or len(joined) != len(sources.rows):
        raise DigestError(
            f"blocks without an info.csv row: {sorted(b.qualified_name for b in blocks.values())}"
        )
    for key, (row, block) in joined.items():
        if block is None:
            raise DigestError(f"{key}: no concept block on the {row.ontology} page")
        _require_row_agrees(row, block)
    return {key: (row, block) for key, (row, block) in joined.items() if block is not None}


def _require_row_agrees(row: ConceptRow, block: ConceptBlock) -> None:
    exported = (block.stereotype or "", _csv_text(block.definition), _csv_text(block.example or ""))
    if (row.stereotype, row.definition, row.example) != exported:
        raise DigestError(f"{row.qualified_name}: info.csv and the page disagree")


def _csv_text(text: str) -> str:
    return text.replace("\n", " ").replace(";", ",")


def _concept(key: str, pair: tuple[ConceptRow, ConceptBlock]) -> Concept:
    row, block = pair
    return Concept(
        key=key,
        ontology=row.ontology,
        packages=row.packages,
        label=row.name,
        stereotype=block.stereotype,
        definition=block.definition.strip() or None,
        example=(block.example or "").strip() or None,
        parents=tuple(_resolve_parent(key, parent) for parent in row.parents),
    )


def _resolve_parent(key: str, parent: str) -> str:
    if parent not in DUPLICATE_CONCEPTS:
        return parent
    if (curated := AMBIGUOUS_GENERALIZATIONS.get((key, parent))) is None:
        raise DigestError(f"{key} specializes the ambiguous {parent}; curate it in defects.py")
    return curated


def _require_owl_classes(
    concepts: Mapping[str, Concept],
    blocks: Mapping[str, tuple[ConceptRow, ConceptBlock]],
    owl: OwlModel,
) -> None:
    used = {(key, parent) for key, (row, _) in blocks.items() for parent in row.parents}
    if stale := AMBIGUOUS_GENERALIZATIONS.keys() - used:
        raise DigestError(f"curated generalizations no longer published: {sorted(stale)}")
    outside = {key for key, concept in concepts.items() if concept.ontology != FOUNDATION}
    if outside != owl.classes.keys():
        raise DigestError(
            f"OWL classes differ from the pages: {sorted(outside ^ owl.classes.keys())}"
        )
    for key, owl_class in owl.classes.items():
        concept, (_, block) = concepts[key], blocks[key]
        agrees = (
            owl_class.stereotype == (concept.stereotype or ""),
            owl_class.comment == owl_comment(block.definition),
            set(owl_class.parents) == {p for p in concept.parents if ontology_of(p) != FOUNDATION},
        )
        if not all(agrees):
            raise DigestError(
                f"{key}: the OWL disagrees on (stereotype, comment, parents) {agrees}"
            )


# -- invariants -------------------------------------------------------------------


def _require_hierarchy(concepts: Mapping[str, Concept]) -> None:
    """Generalization is acyclic, and only the known concepts fail to reach UFO."""
    grounded: dict[str, bool] = {}

    def grounds(key: str, trail: tuple[str, ...]) -> bool:
        if key in trail:
            raise DigestError(f"generalization cycle: {' -> '.join((*trail, key))}")
        if key not in grounded:
            parents = concepts[key].parents
            grounded[key] = concepts[key].ontology == FOUNDATION or any(
                grounds(parent, (*trail, key)) for parent in parents
            )
        return grounded[key]

    if unknown := sorted(
        key for key, concept in concepts.items() if not set(concept.parents) <= concepts.keys()
    ):
        raise DigestError(f"concepts specializing unknown concepts: {unknown}")
    ungrounded = {key for key in concepts if not grounds(key, ())}
    if ungrounded != UNGROUNDED_CONCEPTS:
        differing = sorted(ungrounded ^ UNGROUNDED_CONCEPTS)
        raise DigestError(f"ungrounded concepts differ from the known defect: {differing}")


def _require_closed(document: Node) -> None:
    """Every key is unique and every edge lands on a node of the document."""
    keys: list[str] = []
    targets: set[str] = set()
    for node in _walk(document["network"]):
        keys.append(node["key"])
        targets.update(edge["target"] for edge in node.get("edges", ()))
    if duplicates := [key for key, count in Counter(keys).items() if count > 1]:
        raise DigestError(f"duplicate keys: {duplicates}")
    if dangling := targets - set(keys):
        raise DigestError(f"edges to nothing: {sorted(dangling)}")


def _walk(node: Node) -> Iterable[Node]:
    yield node
    for children in ("layers", "ontologies", "packages", "concepts"):
        for child in node.get(children, ()):
            yield from _walk(child)


# -- the tree ---------------------------------------------------------------------


def _network_node(network: Network) -> Node:
    layers: dict[str, list[Node]] = {}
    for entry in network.sources.menu:
        layers.setdefault(entry.layer, []).append(_ontology_node(entry, network))
    return {
        "key": "SEON",
        "kind": "network",
        "name": "SEON: A Software Engineering Ontology Network",
        "version": VERSION,
        "layers": [
            {"key": layer, "kind": "layer", "name": f"{layer} Layer", "ontologies": nodes}
            for layer, nodes in layers.items()
        ],
    }


def _ontology_node(entry: MenuEntry, network: Network) -> Node:
    page = network.sources.pages[entry.short_name]
    if (page.short_name, page.full_name) != (entry.short_name, _page_title(entry)):
        raise DigestError(f"{entry.short_name}: the page is titled {page.full_name!r}")
    node: Node = {
        "key": entry.short_name,
        "kind": "subnetwork" if entry.subnetwork else "ontology",
        "name": entry.full_name,
        "external": entry.external,
        "description": page.description.strip() or None,
        "edges": _ontology_edges(entry, network),
    }
    if not entry.subnetwork:
        tree = _SectionTree(
            ontology=entry.short_name,
            sections=page.sections,
            concepts=tuple(c for c in network.concepts.values() if c.ontology == entry.short_name),
            network=network,
        )
        node["concepts"] = _concept_nodes((c for c in tree.concepts if not c.packages), network)
        node["packages"] = tree.package_nodes((), ())
        tree.require_placed(node)
    return node


def _page_title(entry: MenuEntry) -> str:
    return f"{entry.full_name} (external)" if entry.external else entry.full_name


@dataclass(frozen=True, slots=True)
class _SectionTree:
    """One page's sections, filled with the concepts ``info.csv`` puts in them."""

    ontology: str
    sections: tuple[Section, ...]
    concepts: tuple[Concept, ...]
    network: Network

    def package_nodes(self, number: tuple[int, ...], path: tuple[str, ...]) -> list[Node]:
        """The nodes of the sections directly under section *number*, named by *path*."""
        nodes = []
        for section in (s for s in self.sections if s.number[:-1] == number):
            section_path = (*path, section.name)
            nodes.append(
                {
                    "key": "/".join((self.ontology, *section_path)),
                    "kind": "subontology" if section.subontology else "package",
                    "name": section.name,
                    "number": ".".join(str(part) for part in (3, *section.number)),
                    "concepts": _concept_nodes(
                        (c for c in self.concepts if c.packages == section_path), self.network
                    ),
                    "packages": self.package_nodes(section.number, section_path),
                }
            )
        return nodes

    def require_placed(self, node: Node) -> None:
        """Every concept of the ontology landed in some section, or the root."""
        placed = sum(1 for child in _walk(node) if child["kind"] == "concept")
        if placed != len(self.concepts):
            raise DigestError(
                f"{self.ontology}: {len(self.concepts) - placed} concepts in no section"
            )


def _concept_nodes(concepts: Iterable[Concept], network: Network) -> list[Node]:
    return [
        {
            "key": concept.key,
            "kind": "concept",
            "label": concept.label,
            "iri": IRI_BASE + concept.key.replace(" ", "_"),
            "stereotype": concept.stereotype,
            "definition": concept.definition,
            "example": concept.example,
            "edges": _concept_edges(concept, network),
        }
        for concept in sorted(concepts, key=lambda concept: concept.key)
    ]


def _concept_edges(concept: Concept, network: Network) -> list[Node]:
    generalizations = [
        {"type": "specializes", "target": parent, "scope": _scope(concept.key, parent)}
        for parent in concept.parents
    ]
    relations = [
        {
            "type": "relation",
            "target": relation.target,
            "scope": _scope(relation.source, relation.target),
            "predicate": relation.predicate,
            "association": relation.association,
            "source_multiplicity": relation.source_multiplicity,
            "target_multiplicity": relation.target_multiplicity,
            "stereotype": relation.stereotype,
            "composition": relation.composition,
            "derived": relation.derived,
        }
        for relation in sorted(network.relations, key=lambda relation: relation.association)
        if relation.source == concept.key
    ]
    return sorted(generalizations, key=lambda edge: edge["target"]) + relations


def _scope(source: str, target: str) -> str:
    return "internal" if ontology_of(source) == ontology_of(target) else "external"


def _ontology_edges(entry: MenuEntry, network: Network) -> list[Node]:
    known = {e.short_name for e in network.sources.menu}
    declared = network.sources.pages[entry.short_name].dependencies
    if unknown := {dependency.target for dependency in declared} - known:
        raise DigestError(f"{entry.short_name} declares dependencies on unknown {sorted(unknown)}")
    edges: list[Node] = [
        {
            "type": "declares_dependency",
            "target": d.target,
            "level": d.level,
            "rationale": d.rationale,
        }
        for d in declared
    ]
    edges += _counted("depends_on", _crossings(entry.short_name, network.relations))
    edges += _counted("specializes_from", _crossings(entry.short_name, _generalizations(network)))
    if entry.member_of:
        edges.append({"type": "member_of", "target": entry.member_of})
    return edges


def _generalizations(network: Network) -> list[tuple[str, str]]:
    return [
        (concept.key, parent) for concept in network.concepts.values() for parent in concept.parents
    ]


def _crossings(
    ontology: str, links: Iterable[Relation] | Iterable[tuple[str, str]]
) -> Counter[str]:
    pairs = ((link.source, link.target) if isinstance(link, Relation) else link for link in links)
    return Counter(
        ontology_of(target)
        for source, target in pairs
        if ontology_of(source) == ontology and ontology_of(target) != ontology
    )


def _counted(edge_type: str, counts: Counter[str]) -> list[Node]:
    return [
        {"type": edge_type, "target": target, "count": count}
        for target, count in sorted(counts.items())
    ]


def _predicates(relations: Iterable[Relation]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for relation in relations:
        if relation.predicate is not None:
            index.setdefault(relation.predicate, []).append(relation.association)
    return {predicate: sorted(index[predicate]) for predicate in sorted(index)}
