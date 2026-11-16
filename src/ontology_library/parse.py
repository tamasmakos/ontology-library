"""Run a source through the processrecall SEON parser.

`read_owl` and `digest` are imported from that package and called as they are.
Nothing here reads triples on its own. `read_owl` keeps the strict SEON reader
for the SEON namespace and reads RDF/XML, Turtle, and JSON-LD into the same model.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from processrecall.ontology.seon import DigestError
from processrecall.ontology.seon.network import digest
from processrecall.ontology.seon.owl import read_owl

from ontology_library.graph import Graph, graph_from_digest, graph_from_owl

SEON_FORMATS = frozenset({"seon"})
# Recorded on the manifest. Every one of these is handed to read_owl.
PARSER_FORMATS = frozenset(
    {
        "rdfxml",
        "rdf/xml",
        "xml",
        "owl",
        "rdf",
        "turtle",
        "ttl",
        "jsonld",
        "json-ld",
        "ntriples",
        "n-triples",
        "nt",
        "obo",
        "oboformat",
    }
)


class OntologyLoadError(RuntimeError):
    """The SEON parser refused the source, or the format hint is unknown."""


def parse(
    source: str | Path,
    format: str,  # noqa: A002 - the manifest's format hint
    *,
    ontology_id: str,
    source_url: str = "",
    license_name: str = "",
) -> Graph:
    """Parse `source` by calling the research parser.

    `format` ``seon`` is a directory of pinned SEON inputs and calls `digest`.
    Every other known hint calls `read_owl` on the file.
    """
    hint = format.strip().lower()
    path = Path(source)
    if hint in SEON_FORMATS:
        return _digest(path, ontology_id, source_url, license_name)
    if hint not in PARSER_FORMATS:
        known = ", ".join(sorted(PARSER_FORMATS | SEON_FORMATS))
        raise OntologyLoadError(f"unknown format {format!r}; known hints: {known}")
    try:
        model = read_owl(path)
    except DigestError as exc:
        raise OntologyLoadError(
            f"{ontology_id}: processrecall.ontology.seon.read_owl refused the source: {exc}"
        ) from exc
    except ET.ParseError as exc:
        raise OntologyLoadError(
            f"{ontology_id}: processrecall.ontology.seon.read_owl could not read {path.name} "
            f"as the SEON RDF/XML dialect: {exc}"
        ) from exc
    return graph_from_owl(
        model,
        ontology_id=ontology_id,
        source_url=source_url,
        license_name=license_name,
        source_format=hint,
    )


def _digest(path: Path, ontology_id: str, source_url: str, license_name: str) -> Graph:
    if not path.is_dir():
        raise OntologyLoadError(f"{ontology_id}: seon format expects a directory, got {path}")
    try:
        document = digest(path)
    except (DigestError, OSError) as exc:
        raise OntologyLoadError(
            f"{ontology_id}: processrecall.ontology.seon.digest refused the source: {exc}"
        ) from exc
    return graph_from_digest(
        document,
        ontology_id=ontology_id,
        source_url=source_url,
        license_name=license_name,
    )
