"""Read ``info.csv``: every concept, UFO included, with its package path.

The export is lossy (``;`` became ``,`` and newlines became spaces in definitions),
so the digest takes from it only what no other source has: the package each
concept sits in, and UFO's generalizations and stereotypes.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import TYPE_CHECKING

from processrecall.ontology.seon import DigestError

if TYPE_CHECKING:
    from pathlib import Path

_HEADER = [
    "Layer",
    "Ontology",
    "Path",
    "Concept",
    "Stereotype",
    "Generalizations",
    "Definition",
    "Example",
    "Relations",
]
_LAYERS = {"FOUNDATIONAL": "1.Foundational", "CORE": "2.Core", "DOMAIN": "3.Domain"}
_PARENT_SEPARATOR = "   "


@dataclass(frozen=True, slots=True)
class ConceptRow:
    """One ``info.csv`` row: a concept as the exporter saw it."""

    layer: str
    ontology: str
    packages: tuple[str, ...]
    name: str
    stereotype: str
    parents: tuple[str, ...]
    definition: str
    example: str
    relation_count: int

    @property
    def qualified_name(self) -> str:
        """The name SEON prints: ``SPO::Stakeholder Allocation``."""
        return f"{self.ontology}::{self.name}"


def read_concepts(path: Path) -> tuple[ConceptRow, ...]:
    """Read *path*, refusing a header or a path that does not match the export."""
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream, delimiter=";", quoting=csv.QUOTE_NONE)
        if (header := next(reader, None)) != _HEADER:
            raise DigestError(f"{path}: unexpected header {header!r}")
        return tuple(_read_row(row) for row in reader)


def _read_row(row: list[str]) -> ConceptRow:
    if len(row) != len(_HEADER):
        raise DigestError(f"expected {len(_HEADER)} fields: {row!r}")
    layer, ontology, path, name, stereotype, parents, definition, example, relations = row
    prefix, _, packages = path.partition(f":{ontology}")
    if layer not in _LAYERS or prefix != _LAYERS[layer] or packages[:1] not in {"", ":"}:
        raise DigestError(f"{ontology}::{name}: path {path!r} does not match layer {layer!r}")
    return ConceptRow(
        layer=layer,
        ontology=ontology,
        packages=tuple(packages.split(":")[1:]),
        name=name,
        stereotype=stereotype,
        parents=tuple(_qualify(parent) for parent in parents.split(_PARENT_SEPARATOR) if parent),
        definition=definition,
        example=example,
        relation_count=int(relations),
    )


def _qualify(parent: str) -> str:
    ontology, separator, name = parent.partition(":")
    if not separator or not ontology or not name:
        raise DigestError(f"not a qualified generalization: {parent!r}")
    return f"{ontology}::{name}"
