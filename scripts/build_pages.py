"""Write the GitHub Pages catalog and one JSON graph per ontology.

The graph files are the library's own JSON export. Run this after the
manifest or the parser changes, then commit ``docs/``.
"""

from __future__ import annotations

import json
from pathlib import Path

from ontology_library import list_ontologies, load_ontology, to_json

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
GRAPHS = DOCS / "graphs"

SUMMARIES = {
    "skos": "A model for thesauri, taxonomies, and other knowledge organization systems.",
    "foaf": "A vocabulary for people, groups, documents, and the links between them.",
    "sioc": "Terms for online communities: forums, posts, users, and their connections.",
    "goodrelations": "An e-commerce vocabulary for products, offers, prices, and businesses.",
    "bfo": "An upper ontology that divides entities into continuants and occurrents.",
    "owl-time": "A vocabulary for instants, intervals, durations, and temporal relations.",
    "prov-o": "A model of provenance: entities, activities, and the agents that act on them.",
    "vcard": "Contact information: names, addresses, and communication channels.",
    "dcterms": "Dublin Core terms for describing resources, such as title, creator, and date.",
    "rdfs": "The RDF Schema vocabulary: classes, properties, and their relationships.",
    "owl": "The OWL 2 schema: the classes and properties used to define ontologies.",
    "wine": "The OWL guide's wine example: wines, wineries, grapes, and regions.",
    "food": "The OWL guide's food example: courses, dishes, and what they contain.",
    "schemaorg": "The Schema.org vocabulary for structured data about people, places, works, and other things.",
}


def main() -> None:
    GRAPHS.mkdir(parents=True, exist_ok=True)
    rows = []
    for record in list_ontologies():
        summary = SUMMARIES.get(record.id)
        if not summary:
            raise SystemExit(f"no page summary for {record.id}")
        graph = load_ontology(record.id)
        (GRAPHS / f"{record.id}.json").write_text(to_json(graph, indent=None), encoding="utf-8")
        counts = {"class": 0, "property": 0, "individual": 0, "datatype": 0}
        for node in graph.nodes:
            for kind in node.types:
                if kind in counts:
                    counts[kind] += 1
        rows.append(
            {
                "id": record.id,
                "name": record.name,
                "summary": summary,
                "license": record.license,
                "license_url": record.license_url,
                "homepage": record.homepage,
                "source_url": record.source_url,
                "format": record.format,
                "nodes": len(graph.nodes),
                "edges": len(graph.edges),
                "counts": counts,
            }
        )
        print(f"{record.id}: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    (DOCS / "catalog.json").write_text(
        json.dumps({"ontologies": rows}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
