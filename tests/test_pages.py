"""The Pages catalog matches the graphs exported by the library."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REQUIRED = ("foaf", "bfo", "owl-time", "schemaorg")


def test_pages_files_exist() -> None:
    for name in ("index.html", "ontology.html", "site.js", "site.css", "catalog.json", "catalog.js", ".nojekyll"):
        assert (DOCS / name).is_file()
    html = (DOCS / "index.html").read_text(encoding="utf-8") + (DOCS / "ontology.html").read_text(encoding="utf-8")
    assert 'href="/' not in html
    assert 'src="/' not in html
    script = (DOCS / "site.js").read_text(encoding="utf-8")
    assert 'fetch("/' not in script
    assert '"/graphs/' not in script


def test_catalog_matches_exported_graphs() -> None:
    catalog = json.loads((DOCS / "catalog.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "src/ontology_library/data/manifest.json").read_text(encoding="utf-8")
    )
    rows = catalog["ontologies"]
    assert [row["id"] for row in rows] == [row["id"] for row in manifest["ontologies"]]
    for row in rows:
        assert row["summary"]
        assert row["nodes"] > 0
        graph = json.loads((DOCS / "graphs" / f"{row['id']}.json").read_text(encoding="utf-8"))
        assert graph["id"] == row["id"]
        assert len(graph["nodes"]) == row["nodes"]
        assert len(graph["edges"]) == row["edges"]
        assert {"id", "iri", "label", "description", "types", "provenance"} <= graph["nodes"][0].keys()
        script = (DOCS / "graphs" / f"{row['id']}.js").read_text(encoding="utf-8")
        assert script.startswith("globalThis.ONTOLOGY_GRAPH = ")
        assert f'"id": "{row["id"]}"' in script[:80]
    exported = {row["id"] for row in rows}
    assert set(REQUIRED) <= exported
