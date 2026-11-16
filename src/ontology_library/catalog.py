"""Manifest of public ontologies and the load entry point."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import as_file, files
from pathlib import Path
from tempfile import gettempdir

from ontology_library.graph import Graph
from ontology_library.parse import parse

_USER_AGENT = "ontology-library/0.1"
_REQUIRED = ("id", "name", "source_url", "license", "license_url", "format", "distribution")


@dataclass(frozen=True, slots=True)
class OntologyRecord:
    """One manifest row. `path` is set when `distribution` is ``vendored``."""

    id: str
    name: str
    source_url: str
    license: str
    license_url: str
    format: str
    distribution: str
    path: str | None
    homepage: str


def list_ontologies() -> list[OntologyRecord]:
    """Every ontology in the shipped manifest, in manifest order."""
    return [_record(row) for row in _manifest()["ontologies"]]


def load_ontology(name: str) -> Graph:
    """Load one ontology by manifest id through the SEON parser."""
    record = _by_id(name)
    if record.distribution == "vendored":
        if not record.path:
            raise OntologyLookupError(f"{name}: vendored entry has no path")
        resource = files("ontology_library").joinpath("data", record.path)
        with as_file(resource) as path:
            return _parse(path, record)
    if record.distribution == "remote":
        return _parse(_fetch(record), record)
    raise OntologyLookupError(f"{name}: unknown distribution {record.distribution!r}")


class OntologyLookupError(KeyError):
    """The manifest has no ontology under this id."""


def _parse(path: Path, record: OntologyRecord) -> Graph:
    return parse(
        path,
        record.format,
        ontology_id=record.id,
        source_url=record.source_url,
        license_name=record.license,
    )


def _by_id(name: str) -> OntologyRecord:
    matches = [record for record in list_ontologies() if record.id == name]
    if not matches:
        known = ", ".join(record.id for record in list_ontologies())
        raise OntologyLookupError(f"no ontology {name!r}; known ids: {known}")
    return matches[0]


def _record(row: dict[str, str]) -> OntologyRecord:
    missing = [key for key in _REQUIRED if not row.get(key)]
    if missing:
        raise ValueError(f"manifest entry {row.get('id', '?')!r} missing {missing}")
    if row["distribution"] not in {"vendored", "remote"}:
        raise ValueError(f"{row['id']}: distribution must be vendored or remote")
    if row["distribution"] == "vendored" and not row.get("path"):
        raise ValueError(f"{row['id']}: vendored entry needs path")
    return OntologyRecord(
        id=row["id"],
        name=row["name"],
        source_url=row["source_url"],
        license=row["license"],
        license_url=row["license_url"],
        format=row["format"],
        distribution=row["distribution"],
        path=row.get("path") or None,
        homepage=row.get("homepage", ""),
    )


def _manifest() -> dict[str, list[dict[str, str]]]:
    text = files("ontology_library").joinpath("data", "manifest.json").read_text(encoding="utf-8")
    return json.loads(text)


def _fetch(record: OntologyRecord) -> Path:
    digest = sha256(record.source_url.encode()).hexdigest()[:16]
    destination = Path(gettempdir()) / "ontology-library" / f"{record.id}-{digest}"
    if destination.is_file() and destination.stat().st_size > 0:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(record.source_url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - manifest URLs
        destination.write_bytes(response.read())
    return destination
