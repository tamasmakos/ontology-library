"""Read ``SEON.owl``: the core and domain classes, generalizations and associations.

The generator (``seon2html/parser/OwlWriter.java``) emits four constructs and
nothing else, so anything outside them is refused rather than skipped. A new
construct in a future release must fail here, not vanish from the digest.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # nosec B405 - a pinned, vendored file
from dataclasses import dataclass
from typing import TYPE_CHECKING

from processrecall.ontology.seon import DigestError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

#: The generator's namespace. It has no scheme, so it is not an absolute IRI.
NAMESPACE = "dev.nemo.inf.ufes.br/seon/SEON.owl#"

_RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
_RDFS = "{http://www.w3.org/2000/01/rdf-schema#}"
_OWL = "{http://www.w3.org/2002/07/owl#}"
_SEON = "{" + NAMESPACE + "}"

_ABOUT = _RDF + "about"
_RESOURCE = _RDF + "resource"
_ANNOTATIONS = {"ontology", "stereotype"}
_CLASS_CHILDREN = {
    _RDFS + "subClassOf",
    _RDFS + "comment",
    _SEON + "ontology",
    _SEON + "stereotype",
}
_PROPERTY_CHILDREN = {_RDFS + "domain", _RDFS + "range"}


@dataclass(frozen=True, slots=True)
class OwlClass:
    """One class, keyed the way SEON prints it: ``SPO::Stakeholder Allocation``."""

    key: str
    ontology: str
    stereotype: str
    comment: str
    parents: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OwlAssociation:
    """One association: an object property with exactly one domain and one range."""

    name: str
    domain: str
    range: str


@dataclass(frozen=True, slots=True)
class OwlModel:
    """Everything the OWL declares, keyed by class key and association name."""

    classes: Mapping[str, OwlClass]
    associations: Mapping[str, OwlAssociation]


def read_owl(path: Path) -> OwlModel:
    """Read *path*, refusing any element the generator does not emit."""
    # The only input is the pinned SEON.owl vendored in seon-1.0.5/, read at build time by
    # `python -m processrecall.ontology.seon`; nothing at runtime parses XML.
    root = ET.parse(path).getroot()  # noqa: S314  # the vendored SEON.owl only
    classes: dict[str, OwlClass] = {}
    associations: dict[str, OwlAssociation] = {}
    for element in root:
        if element.tag == _OWL + "Class":
            owl_class = _read_class(element)
            classes[owl_class.key] = owl_class
        elif element.tag == _OWL + "ObjectProperty":
            association = _read_association(element)
            associations[association.name] = association
        elif element.tag == _OWL + "AnnotationProperty":
            _require_annotation(element)
        elif element.tag != _OWL + "Ontology" or element.get(_ABOUT) != NAMESPACE:
            raise DigestError(f"{path}: unexpected element {element.tag} {element.attrib}")
    return OwlModel(classes=classes, associations=associations)


def class_key(fragment: str) -> str:
    """Turn an OWL fragment (``SPO::Stakeholder_Allocation``) into a concept key."""
    ontology, separator, name = fragment.partition("::")
    if not separator or not ontology or not name:
        raise DigestError(f"not a qualified class name: {fragment!r}")
    return f"{ontology}::{name.replace('_', ' ')}"


def _fragment(iri: str | None) -> str:
    if iri is None or not iri.startswith(NAMESPACE):
        raise DigestError(f"IRI outside the SEON namespace: {iri!r}")
    return iri.removeprefix(NAMESPACE)


def _read_class(element: ET.Element) -> OwlClass:
    key = class_key(_fragment(element.get(_ABOUT)))
    _require_children(element, _CLASS_CHILDREN)
    ontology = _text(element, _SEON + "ontology", required=True)
    if key.partition("::")[0] != ontology:
        raise DigestError(f"{key}: annotated with ontology {ontology!r}")
    return OwlClass(
        key=key,
        ontology=ontology,
        stereotype=_text(element, _SEON + "stereotype", required=False),
        comment=_text(element, _RDFS + "comment", required=True),
        parents=tuple(
            class_key(_fragment(parent.get(_RESOURCE)))
            for parent in element.findall(_RDFS + "subClassOf")
        ),
    )


def _read_association(element: ET.Element) -> OwlAssociation:
    name = _fragment(element.get(_ABOUT))
    _require_children(element, _PROPERTY_CHILDREN)
    domains = element.findall(_RDFS + "domain")
    ranges = element.findall(_RDFS + "range")
    if len(domains) != 1 or len(ranges) != 1:
        raise DigestError(f"{name}: expected one domain and one range")
    return OwlAssociation(
        name=name,
        domain=class_key(_fragment(domains[0].get(_RESOURCE))),
        range=class_key(_fragment(ranges[0].get(_RESOURCE))),
    )


def _require_annotation(element: ET.Element) -> None:
    if _fragment(element.get(_ABOUT)) not in _ANNOTATIONS or len(element):
        raise DigestError(f"unexpected annotation property {element.attrib}")


def _require_children(element: ET.Element, allowed: set[str]) -> None:
    if unknown := {child.tag for child in element} - allowed:
        raise DigestError(f"{element.get(_ABOUT)}: unexpected children {sorted(unknown)}")


def _text(element: ET.Element, tag: str, *, required: bool) -> str:
    found = element.findall(tag)
    if len(found) > 1 or (required and not found):
        raise DigestError(
            f"{element.get(_ABOUT)}: expected {'one' if required else 'at most one'} {tag}"
        )
    return (found[0].text or "") if found else ""
