"""JSON and JSONL keep the projected graph."""

from __future__ import annotations

import json
from pathlib import Path

from ontology_library import parse, to_json, to_jsonl, write_json, write_jsonl

FIXTURE = Path(__file__).parent / "fixtures" / "seon_min.owl"


def test_json_and_jsonl_round_trip(tmp_path: Path) -> None:
    graph = parse(FIXTURE, "rdfxml", ontology_id="example", source_url="https://example.test/ex")
    payload = json.loads(to_json(graph))
    assert payload["id"] == "example"
    assert payload["provenance"]["parser"] == "processrecall.ontology.seon.read_owl"
    assert {node["id"] for node in payload["nodes"]} >= {"EX::Agent", "EX::Person"}
    lines = [json.loads(line) for line in to_jsonl(graph).splitlines()]
    assert lines[0]["record"] == "ontology"
    assert {line["record"] for line in lines} == {"ontology", "node", "edge"}
    write_json(graph, tmp_path / "graph.json")
    write_jsonl(graph, tmp_path / "graph.jsonl")
    assert json.loads((tmp_path / "graph.json").read_text(encoding="utf-8"))["id"] == "example"
    assert (tmp_path / "graph.jsonl").read_text(encoding="utf-8").count("\n") == len(lines)
