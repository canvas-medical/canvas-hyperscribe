Canvas Hyperscribe
==================

This repository includes the following:

- [hyperscribe plugin](hyperscribe): a Canvas plugin to insert commands based on the content of an audio, discussion between a patient and a provider,
  read more [README.md](hyperscribe/README.md).
- [hyperscribe_tuning plugin](hyperscribe_tuning): a Canvas plugin to record the audio and context to assess and tune
  the [hyperscribe plugin](hyperscribe) in a specific environment, read more [README.md](hyperscribe_tuning/README.md).
- [evaluation](evaluations): a set of curated partial steps to assess the reliability of the [hyperscribe plugin](hyperscribe) underlying mechanisms
  and LLMs providers, read more [README.md](evaluations/README.md).
- [tests](tests): a set of unit tests intended to test all the code of the repository. 


To run the tests:
```shell
uv run pytest -vv tests/ # run all tests and fully display any failure 

uv run pytest tests/ --cov=. # run all tests and report the coverage
```