"""JSON and JSONL exports of a graph. No RDF library is involved."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ontology_library.graph import Graph


def to_json(graph: Graph, *, indent: int | None = 2) -> str:
    """Serialize `graph` as one JSON object."""
    return json.dumps(graph.to_dict(), ensure_ascii=False, indent=indent) + "\n"


def to_jsonl(graph: Graph) -> str:
    """One ontology record, then one node per line, then one edge per line."""
    payload = graph.to_dict()
    rows: list[dict[str, Any]] = [
        {"record": "ontology", "id": payload["id"], "provenance": payload["provenance"]}
    ]
    rows.extend({"record": "node", **node} for node in payload["nodes"])
    rows.extend({"record": "edge", **edge} for edge in payload["edges"])
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)


def write_json(graph: Graph, path: str | Path) -> None:
    """Write `to_json` to `path`."""
    Path(path).write_text(to_json(graph), encoding="utf-8")


def write_jsonl(graph: Graph, path: str | Path) -> None:
    """Write `to_jsonl` to `path`."""
    Path(path).write_text(to_jsonl(graph), encoding="utf-8")
