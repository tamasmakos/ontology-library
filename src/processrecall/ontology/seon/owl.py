"""Read OWL into classes and associations.

SEON's generator (``seon2html/parser/OwlWriter.java``) emits four constructs and
nothing else. A file in that namespace is still refused when it leaves those
constructs, so a new SEON construct fails here instead of vanishing from the
digest. Any other RDF/XML, Turtle, or JSON-LD file is read into the same model.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # nosec B405 - a pinned, vendored file
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rdflib import Graph
from rdflib import Literal as RdfLiteral
from rdflib import URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

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
    label: str = ""


@dataclass(frozen=True, slots=True)
class OwlAssociation:
    """One association: an object property with exactly one domain and one range.

    SEON fills `domain` and `range`. Public RDF fills `domains` and `ranges`
    and leaves the single-ended fields empty when an end is missing or repeated.
    """

    name: str
    domain: str
    range: str
    label: str = ""
    comment: str = ""
    domains: tuple[str, ...] = ()
    ranges: tuple[str, ...] = ()
    parents: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OwlIndividual:
    """A named individual and the class IRIs it is an instance of."""

    key: str
    label: str
    comment: str
    types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OwlModel:
    """Everything the OWL declares, keyed by class key and association name."""

    classes: Mapping[str, OwlClass]
    associations: Mapping[str, OwlAssociation]
    individuals: Mapping[str, OwlIndividual] = field(default_factory=dict)
    datatypes: Mapping[str, str] = field(default_factory=dict)


def read_owl(path: Path) -> OwlModel:
    """Read *path* into the shared class and association model.

    Bytes that use the SEON namespace stay on the generator's strict reader.
    Everything else is RDF/XML, Turtle, or JSON-LD.
    """
    if NAMESPACE.encode() in path.read_bytes():
        return _read_seon_owl(path)
    return _read_rdf_owl(path)


def _read_seon_owl(path: Path) -> OwlModel:
    """Read SEON OWL, refusing any element the generator does not emit."""
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


# -- public RDF/XML, Turtle, and JSON-LD --------------------------------------

_CLASS_TYPES = {OWL.Class, RDFS.Class}
_PROPERTY_TYPES = {
    RDF.Property,
    OWL.ObjectProperty,
    OWL.DatatypeProperty,
    OWL.AnnotationProperty,
    OWL.FunctionalProperty,
    OWL.InverseFunctionalProperty,
    OWL.TransitiveProperty,
    OWL.SymmetricProperty,
    OWL.AsymmetricProperty,
    OWL.ReflexiveProperty,
    OWL.IrreflexiveProperty,
    OWL.OntologyProperty,
}
_DATATYPE_TYPES = {RDFS.Datatype}
_SKIP_AS_CLASS = _PROPERTY_TYPES | _DATATYPE_TYPES | {OWL.Ontology, OWL.Restriction, OWL.NamedIndividual}
_LABELS = (
    RDFS.label,
    URIRef("http://www.w3.org/2004/02/skos/core#prefLabel"),
    URIRef("http://purl.org/dc/terms/title"),
    URIRef("http://purl.org/dc/elements/1.1/title"),
    URIRef("http://xmlns.com/foaf/0.1/name"),
)
_COMMENTS = (
    RDFS.comment,
    URIRef("http://www.w3.org/2004/02/skos/core#definition"),
    URIRef("http://purl.org/dc/terms/description"),
    URIRef("http://purl.org/dc/elements/1.1/description"),
)


def _read_rdf_owl(path: Path) -> OwlModel:
    """Read a public ontology file into the same model the SEON reader returns."""
    data = path.read_bytes()
    graph = Graph()
    fmt = _rdf_format(path, data)
    try:
        graph.parse(data=data, format=fmt)
    except Exception as exc:
        raise DigestError(f"{path}: {fmt} parse failed: {exc}") from exc
    classes = _class_iris(graph)
    properties = _property_iris(graph, classes)
    datatypes = _datatype_iris(graph)
    individuals = _individual_iris(graph, classes, properties, datatypes)
    return OwlModel(
        classes={
            str(iri): OwlClass(
                key=str(iri),
                ontology="",
                stereotype="",
                comment=_text_of(graph, iri, _COMMENTS),
                parents=_linked(graph, iri, RDFS.subClassOf),
                label=_text_of(graph, iri, _LABELS) or _local(str(iri)),
            )
            for iri in sorted(classes, key=str)
        },
        associations={
            str(iri): _association(graph, iri) for iri in sorted(properties, key=str)
        },
        individuals={
            str(iri): OwlIndividual(
                key=str(iri),
                label=_text_of(graph, iri, _LABELS) or _local(str(iri)),
                comment=_text_of(graph, iri, _COMMENTS),
                types=_linked(graph, iri, RDF.type, skip=_SKIP_AS_CLASS | _CLASS_TYPES),
            )
            for iri in sorted(individuals, key=str)
        },
        datatypes={
            str(iri): _text_of(graph, iri, _LABELS) or _local(str(iri))
            for iri in sorted(datatypes, key=str)
        },
    )


def _rdf_format(path: Path, data: bytes) -> str:
    suffix = path.suffix.lower()
    if suffix in {".ttl", ".turtle"}:
        return "turtle"
    if suffix in {".jsonld", ".json"}:
        return "json-ld"
    if suffix in {".rdf", ".owl", ".xml"}:
        return "xml"
    stripped = data.lstrip()
    if stripped.startswith((b"{", b"[")):
        return "json-ld"
    if stripped.startswith(b"<"):
        return "xml"
    return "turtle"


def _class_iris(graph: Graph) -> set[URIRef]:
    found: set[URIRef] = set()
    for kind in _CLASS_TYPES:
        found.update(iri for iri in graph.subjects(RDF.type, kind) if isinstance(iri, URIRef))
    for subject, obj in graph.subject_objects(RDFS.subClassOf):
        if isinstance(subject, URIRef):
            found.add(subject)
        if isinstance(obj, URIRef):
            found.add(obj)
    return found


def _property_iris(graph: Graph, classes: set[URIRef]) -> set[URIRef]:
    found: set[URIRef] = set()
    for kind in _PROPERTY_TYPES:
        found.update(iri for iri in graph.subjects(RDF.type, kind) if isinstance(iri, URIRef))
    for predicate in (RDFS.subPropertyOf, RDFS.domain, RDFS.range):
        found.update(iri for iri in graph.subjects(predicate, None) if isinstance(iri, URIRef))
    return found - classes


def _datatype_iris(graph: Graph) -> set[URIRef]:
    found = {iri for iri in graph.subjects(RDF.type, RDFS.Datatype) if isinstance(iri, URIRef)}
    xsd = str(XSD)
    for obj in graph.objects(None, RDFS.range):
        if isinstance(obj, URIRef) and (obj in found or str(obj).startswith(xsd)):
            found.add(obj)
    return found


def _individual_iris(
    graph: Graph,
    classes: set[URIRef],
    properties: set[URIRef],
    datatypes: set[URIRef],
) -> set[URIRef]:
    skip = classes | properties | datatypes
    found: set[URIRef] = set()
    for iri in graph.subjects(RDF.type, OWL.NamedIndividual):
        if isinstance(iri, URIRef) and iri not in skip:
            found.add(iri)
    meta = _SKIP_AS_CLASS | _CLASS_TYPES | _DATATYPE_TYPES
    for subject, obj in graph.subject_objects(RDF.type):
        if (
            isinstance(subject, URIRef)
            and isinstance(obj, URIRef)
            and subject not in skip
            and obj not in meta
        ):
            found.add(subject)
    return found


def _association(graph: Graph, iri: URIRef) -> OwlAssociation:
    domains = _linked(graph, iri, RDFS.domain)
    ranges = _linked(graph, iri, RDFS.range)
    return OwlAssociation(
        name=str(iri),
        domain=domains[0] if len(domains) == 1 else "",
        range=ranges[0] if len(ranges) == 1 else "",
        label=_text_of(graph, iri, _LABELS) or _local(str(iri)),
        comment=_text_of(graph, iri, _COMMENTS),
        domains=domains,
        ranges=ranges,
        parents=_linked(graph, iri, RDFS.subPropertyOf),
    )


def _linked(
    graph: Graph,
    subject: URIRef,
    predicate: URIRef,
    *,
    skip: set[URIRef] = frozenset(),
) -> tuple[str, ...]:
    values = {
        str(obj)
        for obj in graph.objects(subject, predicate)
        if isinstance(obj, URIRef) and obj not in skip
    }
    return tuple(sorted(values))


def _text_of(graph: Graph, subject: URIRef, predicates: tuple[URIRef, ...]) -> str:
    values: list[RdfLiteral] = []
    for predicate in predicates:
        values.extend(obj for obj in graph.objects(subject, predicate) if isinstance(obj, RdfLiteral))
        if values:
            break
    if not values:
        return ""

    def rank(literal: RdfLiteral) -> tuple[int, str]:
        lang = (literal.language or "").lower()
        if lang == "en":
            group = 0
        elif lang.startswith("en-"):
            group = 1
        elif not lang:
            group = 2
        else:
            group = 3
        return (group, str(literal))

    return str(sorted(values, key=rank)[0])


def _local(iri: str) -> str:
    for separator in ("#", "/"):
        if separator in iri:
            tail = iri.rsplit(separator, 1)[-1]
            if tail:
                return tail
    return iri
