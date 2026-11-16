"""Resolve the published relation lines into keyed relations and join them to the OWL.

A relation line names its endpoints by label only, and labels are not unique
(``Requirement`` is in RSRO and GORO). The generator prints each relation in the
blocks of both endpoints, so an endpoint's key is the block that printed the line
in that role. The OWL then has to agree on every non-UFO relation, one for one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from processrecall.ontology.seon import DigestError
from processrecall.ontology.seon.defects import AMBIGUOUS_RELATION_ENDPOINTS, BACKSLASH_ASSOCIATIONS
from processrecall.ontology.seon.pages import RelationLine, parse_relation_line

if TYPE_CHECKING:
    from collections.abc import Mapping

    from processrecall.ontology.seon.owl import OwlModel

FOUNDATION = "UFO"
_DERIVED = "/"
_STRAY = "\\"


@dataclass(frozen=True, slots=True)
class Relation:
    """One association between two concepts, keyed by its OWL-style id."""

    association: str
    source: str
    target: str
    predicate: str | None
    composition: bool
    derived: bool
    source_multiplicity: str | None
    target_multiplicity: str | None
    stereotype: str | None


@dataclass(frozen=True, slots=True)
class PrintedLines:
    """The relation lines of every concept block, with the labels of their owners."""

    labels: Mapping[str, str]
    lines: Mapping[str, tuple[str, ...]]


@dataclass(slots=True)
class _Sighting:
    reading: RelationLine
    sources: set[str] = field(default_factory=set)
    targets: set[str] = field(default_factory=set)


def join_relations(printed: PrintedLines, owl: OwlModel) -> tuple[Relation, ...]:
    """Every relation, each endpoint keyed and each non-UFO one matched to the OWL."""
    sightings = _sightings(printed)
    if stale := AMBIGUOUS_RELATION_ENDPOINTS.keys() - sightings.keys():
        raise DigestError(f"curated relation endpoints no longer printed: {sorted(stale)}")
    backslashed = {
        association_id(s.reading) for s in sightings.values() if s.reading.verb.startswith(_STRAY)
    }
    if backslashed != BACKSLASH_ASSOCIATIONS:
        differing = sorted(backslashed ^ BACKSLASH_ASSOCIATIONS)
        raise DigestError(f"backslash verbs differ from the known defect: {differing}")
    relations = tuple(_relation(sighting) for sighting in sightings.values())
    if len({relation.association for relation in relations}) != len(relations):
        raise DigestError("two relations share an association id")
    _require_owl_agrees(relations, owl)
    return relations


def association_id(reading: RelationLine) -> str:
    """The id ``OwlWriter`` gives a relation, with the stray backslash removed."""
    verb = reading.verb.removeprefix(_STRAY)
    if not verb and reading.composition:
        verb = "composed of"
    return f"{verb.replace('/', '_')}.{reading.source}+{reading.target}".replace(" ", "_")


def ontology_of(key: str) -> str:
    """The ontology a concept key belongs to: ``SPO`` for ``SPO::Stakeholder``."""
    return key.partition("::")[0]


def _sightings(printed: PrintedLines) -> dict[str, _Sighting]:
    names = frozenset(printed.labels.values())
    printers: dict[str, set[str]] = {}
    for key, lines in printed.lines.items():
        for text in lines:
            printers.setdefault(text, set()).add(printed.labels[key])
    sightings: dict[str, _Sighting] = {}
    for key, lines in printed.lines.items():
        label = printed.labels[key]
        for text in lines:
            reading = _reading_for(text, label, names, printers[text])
            sighting = sightings.setdefault(text, _Sighting(reading))
            if sighting.reading != reading:
                raise DigestError(f"{text!r} reads differently in {key}")
            if reading.source == label:
                sighting.sources.add(key)
            if reading.target == label:
                sighting.targets.add(key)
    return sightings


def _reading_for(text: str, label: str, names: frozenset[str], printers: set[str]) -> RelationLine:
    """The one reading of *text* whose endpoints are exactly the blocks that print it.

    The generator prints a relation in the blocks of both endpoints, so a reading
    that leaves a printer unexplained, or names an endpoint that never printed
    the line, is not the relation.
    """
    readings = [
        reading
        for reading in parse_relation_line(text, names)
        if label in (reading.source, reading.target)
        and {reading.source, reading.target} == printers
    ]
    if len(readings) != 1:
        raise DigestError(f"{text!r} in the block of {label!r}: {len(readings)} readings")
    return readings[0]


def _relation(sighting: _Sighting) -> Relation:
    reading = sighting.reading
    if (
        reading.text in AMBIGUOUS_RELATION_ENDPOINTS
        and max(len(sighting.sources), len(sighting.targets)) < 2
    ):
        raise DigestError(f"{reading.text!r} is curated but no longer ambiguous")
    verb = reading.verb.removeprefix(_STRAY)
    return Relation(
        association=association_id(reading),
        source=_endpoint(reading.text, sighting.sources),
        target=_endpoint(reading.text, sighting.targets),
        predicate=verb.removeprefix(_DERIVED) or None,
        composition=reading.composition,
        derived=verb.startswith(_DERIVED),
        source_multiplicity=reading.source_multiplicity,
        target_multiplicity=reading.target_multiplicity,
        stereotype=reading.stereotype,
    )


def _endpoint(text: str, keys: set[str]) -> str:
    if len(keys) == 1:
        return next(iter(keys))
    if len(keys) > 1 and (curated := AMBIGUOUS_RELATION_ENDPOINTS.get(text)) in keys:
        return curated
    raise DigestError(f"{text!r}: endpoint printed by {sorted(keys) or 'no block'}")


def _require_owl_agrees(relations: tuple[Relation, ...], owl: OwlModel) -> None:
    declared = {
        relation.association: relation
        for relation in relations
        if FOUNDATION not in {ontology_of(relation.source), ontology_of(relation.target)}
    }
    if missing := declared.keys() - owl.associations.keys():
        raise DigestError(f"relations the OWL lacks: {sorted(missing)}")
    if extra := owl.associations.keys() - declared.keys():
        raise DigestError(f"OWL associations no page prints: {sorted(extra)}")
    for name, association in owl.associations.items():
        relation = declared[name]
        if (association.domain, association.range) != (relation.source, relation.target):
            raise DigestError(f"{name}: OWL has {association.domain} -> {association.range}")
