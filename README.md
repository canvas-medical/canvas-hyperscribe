Canvas Hyperscribe
==================

This repository includes the following:

- [hyperscribe plugin](hyperscribe): a Canvas plugin to insert commands based on the content of an audio, discussion between a patient and a provider,
  read more [README.md](hyperscribe/README.md)
- [Canvas Scribe](hyperscribe/scribe): the AI scribe built into the same plugin: a Scribe tab to record a visit, review recommendations by SOAP section,
  and chart from them, including a charge matrix
- [evaluation](evaluations): a set of curated partial steps to assess the reliability of the [hyperscribe plugin](hyperscribe) underlying mechanisms
  and LLMs providers, read more [README.md](evaluations/README.md).
- [tests](tests): a set of unit tests intended to test all the code of the repository. 

Branches and tags
-----------------

`main` is the Canvas Scribe offering, the only one maintained.
The legacy Hyperscribe offering is kept as the `hyperscribe-v1` tag.


To run the tests:
```shell
uv run pytest -vv tests/ # run all tests and fully display any failure 

uv run pytest tests/ --cov=. # run all tests and report the coverage
```

Static checks of types and code analyzes can be done with:
```shell
uv run mypy --config-file=mypy.ini .
```