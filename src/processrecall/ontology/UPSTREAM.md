# Upstream

`processrecall.ontology.seon` is copied unchanged from
<https://github.com/tamasmakos/processrecall-research> `main` at
`4493f215b4ef7ba500e4bc9a536f5739a03d63aa`
(`packages/ontology/src/processrecall/ontology/seon`).

That package is the parser. ontology-library calls `read_owl` and `digest`.
It does not reimplement them. The research repository declares no license;
these modules are vendored so this library can import them.
