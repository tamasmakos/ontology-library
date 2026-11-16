# Third-party notices

The library code under `src/ontology_library` is MIT. See `LICENSE`.

`src/processrecall/ontology/seon` is copied from
https://github.com/tamasmakos/processrecall-research at
`4493f215b4ef7ba500e4bc9a536f5739a03d63aa`. `owl.py` keeps that SEON reader and
also reads RDF/XML, Turtle, and JSON-LD into the same model. That repository
does not declare a license. The modules are included so this package can call them.

Vendored ontology bytes keep their upstream licenses. Do not treat them as MIT.

| File | Upstream | License |
| --- | --- | --- |
| `vendor/skos.rdf` | https://www.w3.org/2009/08/skos-reference/skos.rdf | [W3C Document License](https://www.w3.org/copyright/document-license/) |
| `vendor/foaf.rdf` | http://xmlns.com/foaf/spec/index.rdf | [CC BY 1.0](http://creativecommons.org/licenses/by/1.0/). The FOAF specification says this covers the vocabulary and the accompanying RDF. |
| `vendor/sioc.rdf` | http://rdfs.org/sioc/ns | [CC BY 1.0](http://creativecommons.org/licenses/by/1.0/), stated on http://rdfs.org/sioc/spec/ |
| `vendor/goodrelations.owl` | http://purl.org/goodrelations/v1.owl | [CC BY 3.0](http://creativecommons.org/licenses/by/3.0/). Attribute Martin Hepp and http://purl.org/goodrelations/ |
| `vendor/bfo.owl` | http://purl.obolibrary.org/obo/bfo.owl | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), stated in the file |
| `vendor/time.ttl` | https://www.w3.org/2006/time.ttl | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), stated in the file. Copyright 2006-2017 W3C and OGC. |
| `vendor/prov-o.ttl` | https://www.w3.org/ns/prov-o.ttl | [W3C Document License](https://www.w3.org/copyright/document-license/) |
| `vendor/vcard.ttl` | https://www.w3.org/2006/vcard/ns.ttl | [W3C Document License](https://www.w3.org/copyright/document-license/) |
| `vendor/dcterms.ttl` | https://www.dublincore.org/specifications/dublin-core/dcmi-terms/dublin_core_terms.ttl | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). DCMI documents use this unless a page says otherwise. |
| `vendor/rdfs.ttl` | https://www.w3.org/2000/01/rdf-schema.ttl | [W3C Document License](https://www.w3.org/copyright/document-license/) |
| `vendor/owl.ttl` | https://www.w3.org/2002/07/owl.ttl | [W3C Document License](https://www.w3.org/copyright/document-license/) |
| `vendor/wine.rdf` | https://www.w3.org/TR/owl-guide/wine.rdf | [W3C Document License](https://www.w3.org/copyright/document-license/) |
| `vendor/food.rdf` | https://www.w3.org/TR/2004/REC-owl-guide-20040210/food.rdf | [W3C Document License](https://www.w3.org/copyright/document-license/) |
| `vendor/schema.jsonld` | https://schema.org/version/latest/schemaorg-current-https.jsonld | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/), https://schema.org/docs/terms.html |

W3C documents are redistributed with their source URL. Keep that URL with any copy.
GoodRelations derivatives should say they are based on the GoodRelations ontology by Martin Hepp.
Schema.org derivatives stay under CC BY-SA 3.0.
