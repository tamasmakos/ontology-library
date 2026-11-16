# ontology-library

A Python library that collects useful public ontologies from the
[awesome-ontology](https://github.com/ozekik/awesome-ontology) list and loads them
through one existing parser into a single agent-ready graph.

The parser is `processrecall.ontology.seon` from
[processrecall-research](https://github.com/tamasmakos/processrecall-research)
(`main` at `4493f215b4ef7ba500e4bc9a536f5739a03d63aa`), copied under
`src/processrecall/ontology/seon`. This library calls `read_owl` and `digest`.
It does not add a second parser.

Files in the SEON namespace stay on the original reader. That reader accepts
four RDF/XML constructs (`owl:Ontology`, `owl:Class`, `owl:ObjectProperty`,
`owl:AnnotationProperty`) and refuses anything else. `digest` reads a pinned
SEON directory (`SEON.owl`, `info.csv`, and the HTML pages). RDF/XML, Turtle,
and JSON-LD that are not in that namespace are read by the same `read_owl`
into the same model. A file the reader cannot parse raises `OntologyLoadError`.

## Install

```bash
pip install -e .
```

Requires Python 3.12.

## Graph schema

A graph is plain data. An agent does not need SPARQL or an RDF stack.

```text
Graph
  id: str                          catalog id, or the id passed to parse()
  provenance:                      source_url, license, format, parser, parser revision
  nodes: Node[]
  edges: Edge[]

Node
  id: str                          parser key. A SEON class is "EX::Person". A SEON
                                   property is the association name, for example
                                   "knows.Person+Person". A public term uses its IRI.
  iri: str                         original IRI. SEON IRIs are built the way
                                   processrecall.ontology.seon.network builds them.
  label: str | null
  description: str | null          comment or definition the parser kept
  types: list                      "class", "property", "individual", and/or "datatype"
  provenance
    source_ontology_id: str        catalog id
    original_iri: str

Edge
  id: str                          "specializes:<child>:<parent>", "relation:<property>",
                                   "domain:<property>:<class>", "range:<property>:<class>",
                                   or "type:<individual>:<class>"
  source: str                      node id
  target: str                      node id
  label: str | null                "specializes", "domain", "range", "type", or the property label
  description: str | null
  types: ["property"]
  provenance
    source_ontology_id: str
    original_iri: str              rdfs:subClassOf, rdfs:subPropertyOf, rdfs:domain,
                                   rdfs:range, rdf:type, or the property IRI
```

`specializes` is `rdfs:subClassOf` for classes and `rdfs:subPropertyOf` for
properties. A relation edge is a property with exactly one domain and one range.
Public properties also keep a domain edge and a range edge when those ends are
IRIs. Node and edge ids are stable across repeated parses of the same file.

`format="seon"` calls `digest` on a directory and projects each concept node in
that document into the same shape.

## Load a graph

```python
from ontology_library import list_ontologies, load_ontology, parse, to_json, to_jsonl

for record in list_ontologies():
    print(record.id, record.license, record.format)

graph = parse("tests/fixtures/seon_min.owl", "rdfxml", ontology_id="example")
print(to_json(graph))
print(to_jsonl(graph))

skos = load_ontology("skos")
```

`load_ontology` raises `OntologyLoadError` when `read_owl` cannot parse the
file. `OntologyLookupError` means the id is not in the manifest.

To parse a file that is not in the manifest:

```python
from ontology_library import parse

graph = parse("local.owl", "rdfxml", ontology_id="local")
```

`rdfxml`, `turtle`, `jsonld`, `ntriples`, and `obo` are accepted as format
hints and all go to `read_owl`. `seon` goes to `digest`.

## Add an ontology

1. Confirm the license allows reuse. If it also allows redistribution, commit
   the upstream bytes under `src/ontology_library/data/vendor/` and set
   `"distribution": "vendored"`. If the license does not allow redistribution,
   leave the bytes out and set `"distribution": "remote"` with the upstream
   URL. The loader fetches a remote entry at load time.
2. Do not commit huge dumps (full knowledge graphs, OBO Foundry releases).
3. Add a row to `src/ontology_library/data/manifest.json` with `id`, `name`,
   `source_url`, `license`, `license_url`, `format`, `distribution`, and
   `path` when vendored.
4. Keep the upstream file unchanged, and add a line to `NOTICES.md`.

The new row is visible from `list_ontologies`. Loading it runs the same parser.

## License rule

Commit ontology bytes only when the upstream license allows redistribution.
Otherwise the manifest stores the URL and `load_ontology` downloads it. Skip a
candidate when the license is missing, unclear, or non-redistributable. The
MIT license on this repository covers the library code, not the vendored
ontologies and not the copied SEON parser. See `NOTICES.md`.

## First batch

| id | format | license |
| --- | --- | --- |
| skos | RDF/XML | W3C Document License |
| foaf | RDF/XML | CC BY 1.0 |
| sioc | RDF/XML | CC BY 1.0 |
| goodrelations | RDF/XML | CC BY 3.0 |
| bfo | RDF/XML | CC BY 4.0 |
| owl-time | Turtle | CC BY 4.0 |
| prov-o | Turtle | W3C Document License |
| vcard | Turtle | W3C Document License |
| dcterms | Turtle | CC BY 4.0 |
| rdfs | Turtle | W3C Document License |
| owl | Turtle | W3C Document License |
| wine | RDF/XML | W3C Document License |
| food | RDF/XML | W3C Document License |
| schemaorg | JSON-LD | CC BY-SA 3.0 |

## Skipped

License unclear or not redistributable:

- **DOLCE.** The ISTC-CNR overview does not state a redistribution license.
- **CIDOC CRM.** `https://cidoc-crm.org/license` returned 404. No standard open license was confirmed.
- **Music Ontology.** `http://purl.org/ontology/mo/` returned 503, so the license was not checked.
- **Cyc / OpenCyc.** Not redistributable. OpenCyc was withdrawn; Cyc is proprietary.
- **SUMO and MILO.** Published as SUO-KIF. A standard redistribution license was not confirmed, and the reused parser does not read KIF.

Size, not license. These are useful and, where noted, openly licensed. They are not in the manifest because a full copy is a large dump or a multi-module suite:

- **Gene Ontology, Uberon, FoodOn.** CC BY OBO Foundry releases, from tens to hundreds of megabytes. The catalog does use OBO. The reused parser does not read it, and the releases are too large to vendor.
- **DBpedia dumps, Wikidata, YAGO, ConceptNet.** Instance dumps, not small vocabularies.
- **FIBO and the Common Core Ontologies.** Large multi-file suites.
- **WordNet.** Large lexical database.

Schema.org is in the batch (about 1.5 MB, CC BY-SA 3.0). It is a vocabulary, not a dump. Derivatives of that file stay under CC BY-SA 3.0.

## Browse

`docs/` is a static site: an index of the manifest, and one page per ontology. Search a label, then read that term’s description, type, IRI, and neighbors. Schema.org stays a list plus the selected neighborhood. The graph files are this library’s JSON export, one file per ontology, written by:

```bash
python scripts/build_pages.py
```

Publish the site with GitHub Pages from the default branch only:

1. Settings → Pages.
2. Build and deployment: Deploy from a branch.
3. Branch `main`, folder `/docs`. Save.

Styles, ontology pages, and graph files use relative links, so the same `docs/` folder works at `https://tamasmakos.github.io/ontology-library/`, on the Vercel preview (`vercel.json` publishes `docs/`), and when `docs/index.html` is opened locally. Opening the folder as files cannot `fetch` JSON, so each JSON file has a sibling `.js` script for that case. Do not point Pages at a feature branch.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Tests cover the SEON fixture and one real vendored file of each format: `skos.rdf`, `rdfs.ttl`, and `schema.jsonld`. They also load every manifest entry.
