# TODO

## Loading/Formatting

- [ ] loaders for stand-off format (BioNLP/brat)
- [ ] loader for PubAnnotation
- [ ] loader for EuropePMC
- [ ] accept CoNLL without offsets
- [ ] extend pubmed/pmc fetchers to include BioC API
- [ ] fetcher for [PubTator Central](https://www.ncbi.nlm.nih.gov/research/pubtator/tutorial.html)


## Representation

- [x] support discontinuous spans
- [x] support relations (BioC and PubTator)


## Usability

- [ ] flattening strategies for overlapping entities (eg. for CoNLL output)
- [ ] convenience wrappers for directory-wise loading and serialising of standoff+text
- [ ] support the same range of sources for all input formats (path, url, file)
- [ ] loaders and formatters indicate if the format represents text and/or annotations
- [ ] iterator-compatible dump mechanism


## Development

- [ ] add type hints
- [ ] add a test file with non-ASCII characters to verify proper offsets
- [ ] test format-specific parameters
