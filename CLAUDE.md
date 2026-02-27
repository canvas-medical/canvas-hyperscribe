# Canvas Hyperscribe

A Canvas Medical plugin that transforms audio conversations between patients and providers into structured Canvas medical commands. Uses an LLM pipeline: audio transcription -> instruction extraction -> parameter identification -> command generation.

## Tech Stack

- Python 3.11-3.12 (Canvas SDK constraint)
- Canvas SDK (plugin framework, ASGI handlers, data layer)
- LLM vendors: OpenAI, Anthropic, Google, ElevenLabs (configurable per deployment)
- Synchronous Python with `ThreadPoolExecutor` for parallelism (no async/await)
- `requests` for HTTP (no httpx, no aiohttp)
- `uv` for package management, `hatch` as build backend
- Pre-commit: ruff check, ruff format, mypy (strict), pytest

## Project Layout

```
hyperscribe/
  commands/       # 38+ command types, all inherit from Base
  handlers/       # Canvas plugin entry points (buttons, views, protocols)
  libraries/      # Core logic: commander, audio_interpreter, caching, S3, auth
  llms/           # LLM vendor implementations, all inherit from LlmBase
  structures/     # Data types (NamedTuples and plain classes)
  templates/      # LLM prompt templates (Jinja-style)
  static/         # Frontend assets
evaluations/      # Evaluation framework: situational tests, end-to-end cases
scripts/          # Operational utilities (case building, analysis, S3 tools)
tests/            # Mirrors hyperscribe/ and evaluations/ structure exactly
```

## Architecture

### Command Pattern
Every command inherits from `Base` and implements: `schema_key()`, `note_section()`, `command_from_json()`, `command_parameters()`, `instruction_description()`, `instruction_constraints()`, `is_available()`, `staged_command_extract()`. All are `@classmethod` except `command_from_json` and `is_available`. Commands should provide a `command_parameters_schemas` method with JSON Schema including `description` keys for each property -- this improves LLM response quality.

### LLM Abstraction
Every LLM vendor inherits from `LlmBase` and implements `request()`. Vendor selection happens via `Helper.chatter()` factory. Retry logic lives in the base class (`attempt_requests`, `chat`). Use `single_conversation` and `chat` methods -- they handle JSON Schema validation and retry automatically.

### Data Flow
`Instruction` -> `InstructionWithParameters` -> `InstructionWithCommand` -> `InstructionWithSummary`. Each level adds data via a `@classmethod` factory (`add_parameters`, `add_command`, `add_summary`).

### Configuration
`Settings` is an immutable `NamedTuple` built from Canvas plugin secrets via `Settings.from_dictionary()`. All secret key names live in `Constants.SECRET_*`. Bump `CANVAS_MANIFEST.json` `plugin_version` when making changes.

## Coding Conventions

### Code Organization
- **One class per file** (except tests). No standalone functions outside of classes.
- File names must match class names: `limited_cache.py` for `LimitedCache`, `capture_view.py` for `CaptureView`.
- `if __name__ == "__main__":` sections should be minimal -- ideally a single line calling a class method:
  ```python
  if __name__ == "__main__":
      ChartGenerator.main()
  ```
- Use `ArgumentParser` for scripts that accept arguments.
- All SQL queries belong in dedicated datastore classes, not scattered in scripts or handlers.
- All database access goes through `LimitedCache`, not directly in commands.

### Data Structures
- **Use `NamedTuple`** for immutable value objects. No `@dataclass` (explicitly reverted in history).
- **Use plain classes** with `__init__` for mutable state or inheritance hierarchies.
- Every structure should have `to_json()` for serialization and `@classmethod load_from_json()` for deserialization. These methods handle the camelCase (JSON/JavaScript) to snake_case (Python) conversion.
- Never use `_asdict()` -- it's a private method with no control over the conversion. Never use `MyClass(**my_dict)` for construction -- use `load_from_json()`.
- Prefer `NamedTuple` or plain classes over raw dictionaries and tuples. Named fields help humans, tools, and type checkers alike.

### Type Annotations
- Mypy strict mode is enforced (see `mypy.ini`). Tests opt out via `# mypy: allow-untyped-defs` at file top.
- Use PEP 604 union syntax: `str | None`, not `Optional[str]`.
- Use lowercase generics: `list[str]`, `dict[str, str]`, not `List`, `Dict`.
- Use `from __future__ import annotations` when forward references are needed.

### Naming
- Classes: `PascalCase` (`LlmOpenai`, `InstructionWithCommand`)
- Methods/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`, defined as class attributes on the `Constants` class in `hyperscribe/libraries/constants.py` -- never as module-level globals
- Private attributes: single underscore prefix (`self._conditions`)
- **No abbreviations** unless widely recognized (HTTP, URL, UUID, SQL). Write `system_prompt` not `sys_prompt`, `specification` not `spec`, `low` not `lo`, `criterion` not `crit`.
- camelCase for JSON keys, snake_case for Python attributes. The conversion happens in `to_json()`/`load_from_json()`.

### Methods
- Prefer `@classmethod` over `@staticmethod`. Use `@classmethod` even for utility functions (see `Helper`). `@classmethod` can access other class methods through `cls`.
- Use `raise NotImplementedError` in base classes for abstract methods (no `abc.ABC`).
- Use factory classmethods for construction: `from_dictionary()`, `load_from_json()`, `add_parameters()`.
- Standard return variable: build up a `result` variable and return it at the end.
- **No optional/default parameters.** Create explicit wrappers instead (see "Explicit over implicit" in Design Principles):
  ```python
  @classmethod
  def standard_detector(cls) -> TimestampAnomalyDetector:
      return cls(cls.STANDARD_CONSECUTIVE_IDENTICAL, cls.STANDARD_WORD_DURATION)
  ```

### Style
- f-strings everywhere. No `.format()` or `%` formatting. Be consistent -- don't mix f-strings and concatenation in the same context.
- Walrus operator (`:=`) for conditional extraction: `if response := chatter.single_conversation(...):`
- Dict merge with `|` operator: `return { ... } | extras`
- `HTTPStatus` enum for HTTP status codes, never raw integers.
- No docstrings (code is self-documenting through naming and types). Only inline `#` comments where logic is non-obvious.
- Avoid magic values -- define named constants in `Constants`.
- Use `Path` over strings for file system paths. `Path` offers an `open` method that is easier to mock.
- Avoid recursive functions -- there is always a loop alternative in Python.
- Prefer `while condition:` over `while True:` with a `break`.

### Error Handling
- Defensive `.get()` with defaults for dict access. But consider whether a missing key should crash -- silent `.get()` with a fallback can hide bugs.
- Return `None` for failures rather than raising exceptions (command methods return `X | None`).
- Minimal try/except; let errors propagate. No custom exception classes.
- `for/else` pattern for retry-exhaustion handling.
- When tests break, question the code first before changing the tests.

### Imports
- Standard library, then third-party (canvas_sdk, requests), then local project.
- Specific imports preferred: `from requests import post as requests_post`.
- No wildcard imports. Imports always at the top of the file.

### Design Principles

**Delete over abstract.** When an intermediary system creates indirection, delete the entire layer rather than improving its abstraction. The copilot Task mechanism, FHIR REST calls, audio server, and Canvas service secrets were all removed outright -- not refactored. If a mixin or helper only extends one base class, merge them into the base. Fewer files, fewer hops, fewer things to understand.

**Database isolation is a hard architectural constraint.** All database access must go through `LimitedCache`, loaded at the beginning of each cycle. Breaking this isolation makes it impossible to run the evaluation harness in a synthetic context. This is not a preference -- it is a structural requirement that the entire test/evaluation framework depends on.

**Explicit over implicit.** No optional parameters, no default arguments, no lazy instantiation, no `getattr`/`setattr`. Optional parameters hide information from the reader and contradict Python's "be explicit" mantra. When calls commonly use the same values, create a named wrapper (`standard_detector()`, `instanced()`, `registered()`). Mutable default arguments (`def f(x={})`) are especially dangerous.

**Centralize state in the class that owns it.** Logic that manages state should live in the class that owns that state. Stuck-session detection belongs in `StopAndGo.get()`, not in `CaptureView`. Recovery should be transparent -- called automatically on retrieval. Don't scatter state management across handlers.

**Soft recovery over hard reset.** Prefer continuing a session over discarding all previous state. Hard resets (deleting the `StopAndGo` object, clearing caches) are "more harmful than helpful" -- they lose work.

**Investigate root causes before patching symptoms.** Don't implement workarounds without understanding *why* something is broken. A recovery mechanism is helpful but investigating and addressing the root causes of crashes is necessary. If questionnaire options have empty labels, investigate why -- don't just mark them as unlabeled.

**Types over strings.** Use typed structures (`NamedTuple`, concrete classes) over raw dicts and tuples. Use concrete types as method parameters (`hyperscribe_class: Base`) instead of string identifiers (`hyperscribe_class_name: str`). Avoid `Any` -- if you know it's `None | Cache`, say so. Forcing information through required type implementation helps catch errors.

**Fail early, check early.** If a command's fields cannot be edited or a command is not applicable, detect that in `is_available()` -- not deep in the processing pipeline after expensive work has been done. Early rejection removes the command from consideration in more than half of the flow.

**Abstract methods force correctness.** Providing a default implementation to 90% of subclasses is a convenience that may lead to errors on the first new command that doesn't follow the pattern. Making a method abstract (`raise NotImplementedError`) forces every subclass to provide the correct value.

**Every domain concept gets a class.** Even disabled or unrecognized concepts should have a representation in the code. For an unsupported command type, create the class with `def is_available(self) -> bool: return False` rather than ignoring it with a silent skip. This makes the concept visible and discoverable.

**Domain correctness matters more than code correctness.** Even when code is technically correct, the domain model must be right. A resolved condition being re-diagnosed should produce a new `Diagnose` command, not a new `Assess`. Question whether the *behavior* is medically correct, not just whether the code runs.

**Lightweight before heavyweight.** When something is wrong, first try better wording or prompts (lightweight). Only escalate to multi-pass detection or architectural changes (heavyweight) if the lightweight approach fails.

**Singleton for shared state within a scope.** When N command instances all retrieve and hold the same data for the same note/cycle, use a singleton keyed by the appropriate scope (`note_uuid`). Clean it up with `__del__`. Lazy instantiation without a singleton "adds complexity while not saving much."

**One thread, simple loop.** Prefer a straightforward `while True` loop inside a single thread over callbacks and multi-thread event chains. Commander was refactored from a callback/executor pattern to a single-threaded loop: read from `StopAndGo`, process cycle, store effects, render, repeat.

**Data bag + separate loader.** Separate pure data containers from the logic that populates them. `LimitedCache` holds cached data (no ORM imports, no queries). `LimitedCacheLoader` handles all the ORM query logic. The data bag is easy to construct in tests and evaluations.

**JSON Schema as contract.** Every command defines a JSON Schema for its parameters with `additionalProperties: false` and `description` keys on every property. The schema is the source of truth for LLM parameter extraction. Adding `id` fields to array items removes ordering constraints from the LLM.

**No dead code.** Remove unused methods, unreachable branches, uncalled functions, and unused parameters immediately. Dead code adds noise and distraction. If `raise_on_anomaly` is never used and there's no plan to use it, delete it.

**No circular imports via tricks.** `if TYPE_CHECKING:` is a dirty way to circumvent a design issue. Fix the design instead -- move methods to the right class so the circular dependency disappears.

**Consistency is a design feature.** The benefit of conventions and similar patterns is that exceptions -- valid, justified, intentional, or not -- are easier to pinpoint, making reviews and maintenance easier. If some commands use one approach and others use another, pick one and apply it everywhere.

**Block review on foundational issues.** If the architecture is wrong, stop reviewing tests and details -- "It does not make sense to continue the review before they are addressed as we can anticipate some important changes." Fix the foundation first.

**Revert fast when an approach doesn't work.** `@dataclass` was adopted and reverted the same day when it introduced test friction. Write more explicit boilerplate (manual `__init__`, `__eq__`) rather than fight with framework behavior. Transparent code beats clever code.

**Pragmatic temporary solutions are fine if flagged.** When the ideal solution depends on future SDK capabilities, ship the pragmatic version (S3 document instead of database) but document what the ideal long-term solution would be.

## LLM Prompt Engineering

- Build prompts as `list[str]` joined with newlines. System and user prompts are always separate.
- Use JSON Markdown blocks (` ```json `) in prompts for structured output -- they prevent interference from LLM commentary and work with `extract_json_from`.
- **Include the JSON Schema in the first user prompt** -- it helps the LLM comply immediately.
- Add `"description"` keys to JSON Schema properties -- this significantly helps LLMs understand intent.
- Set `"additionalProperties": false` in all JSON Schemas.
- Add an `id` or identifier field to each object in array responses -- this lets you match objects regardless of order and removes the `in the same order` constraint from the LLM.
- The less you ask of LLMs, the less they hallucinate. Remove unnecessary constraints.
- Use ASCII characters in prompts, not Unicode dashes or special characters -- they add nothing for the LLM while making prompts harder to read for humans.
- For proprietary data (e.g., FDB codes), don't ask the LLM directly. Use a multi-step approach: get keywords from LLM -> query the service -> let LLM pick from real results.
- **Token economics matter.** Reduce input/output tokens aggressively -- CSV format for flat data reduced tokens 50-80% vs JSON. Route "complex" requests (speaker identification, section detection) to capable models and "simple" requests (parameter extraction, command generation) to cheaper/faster models.
- Wording matters enormously. "Cannot include" can be misread as a prohibition; "Only document...for conditions outside the following list" is unambiguous. Test prompt changes against real scenarios.

## Testing Conventions

### Structure
- Function-based tests only (no test classes).
- One test file per source file: `hyperscribe/commands/diagnose.py` -> `tests/hyperscribe/commands/test_diagnose.py`.
- Test methods must appear in the same order as the source methods they test.
- Every public method must have at least one test.
- 100% test coverage is the expectation. From 2% missing it becomes 3, then 7, 11, 17... and tests won't matter anymore. 100% coverage helps quickly identify what tests/scenarios are missing.
- Tests must be part of every PR. No merging without tests.

### Naming
- Test function naming: `test_<method_name>__<scenario>` (note the **double underscore** between method and scenario). For dunder methods: `test___init__`.
- `helper_instance()` factory function at the top of each test file to construct the system under test.
- `tested` variable for the class or instance under test: `tested = Diagnose` or `tested = helper_instance()`.
- `the_` prefix for pytest fixtures: `the_client`, `the_session`, `the_audio_file`.

### Assertions
- Plain `assert` statements only (no `assertEqual`, `assertIn`).
- `assert result is True`, `assert result is None` for identity checks (use `is`, not `==`).
- `assert result == expected` for value comparison.
- `assert isinstance(result, X)` is useless after `assert result == expected` where `expected` is already of type `X`.
- Index debugging: `assert result == expected, f"---> {idx}"` in loops.
- Schema stability: `md5(json.dumps(schema, sort_keys=True).encode()).hexdigest()` to detect unintentional changes.
- LLM prompt stability: hash the full prompt string rather than spot-checking a few words.
- **Never use constants for expected output values** -- use their literal values. Constants are fine for test *inputs*.

### Mocking
- Use `@patch.object(Class, "method")` for class method patches. Use `@patch("module.path")` for module-level patches.
- **Always verify mock calls** with `.mock_calls` against explicit `call(...)` lists. Never use `assert_called_once_with` or similar -- `mock_calls` comparison is stricter. An unchecked mock is a risk.
- Use `mock_object.mock_calls` (on the object), not `mock_object.method.mock_calls` (on a specific method) -- the former catches unexpected method calls on the same object.
- Prefer `side_effect` over `return_value`. `side_effect` controls the exact sequence of return values and breaks if the mock is called more times than expected. `return_value` silently returns the same value no matter how many times it's called.
- Define a local `reset_mocks()` function inside each test to reset all mocks between scenarios. Create `MagicMock` instances *before* the `reset_mocks` definition.
- Keep mocks in consistent order everywhere: decorator list -> `reset_mocks` -> `side_effect` setup -> calls check section.
- Use `MagicMock()` for dependencies that need method chaining. Simplify where possible: `MagicMock(llm_text=VendorKey(...))` instead of assigning attributes separately.
- Reserve `monkeypatch` for cases where `@patch` is impossible or difficult (e.g., environment variables). Prefer `@patch` / `@patch.object` for everything else.
- Never use `ANY` in mock call assertions -- mock the dependency to control the value instead.
- Mock called methods to prevent duplicating their tests -- check the call arguments instead.

### Test Data
- **Never compute expected values** from the same logic being tested. Hard-code them. If the test uses the same code as the source, it's equivalent to `assert 2 == 2`.
- Use clearly fake, descriptive values prefixed with "the": `"thePatientId"`, `"theNoteId"`, `"textVendor"`.
- Use varied/random-looking dates and values -- always using "perfect" values can mask hardcoded bugs.
- Use `tests = [(input, expected), ...]` lists iterated with `for` loops for multi-scenario coverage (or `@pytest.mark.parametrize`).
- Every `NamedTuple` structure should have a `test_class()` test verifying its fields using `is_namedtuple()` from `tests/helper.py`.

## SQL Conventions

- All SQL queries belong in dedicated datastore classes (`evaluations/datastores/postgres/`), not in scripts or handlers.
- Always use `ORDER BY` with `LIMIT` -- without it, results are unpredictable.
- Prefer JOINs over subqueries-as-fields for efficiency and correctness.
- Sort results for predictability: `ORDER BY 1, 2, 3`.
- Field names in SQL must match the actual column names (snake_case) -- mocks can mask mismatches that break in production.

## Commit Messages
- Lowercase, no period at the end.
- Action verb at the start: `add`, `remove`, `refactor`, `fix`, `prevent`, `use`, `bump`.
- Single line. GitHub issue references in parentheses: `(issue #NNN)`.
- Multiple changes separated with ` / `: `"remove audio server / allow customer to enter free text (issue #192)"`.

## Running

```bash
# install pre-commit hooks (required)
uv run pre-commit install --install-hooks
# tests
uv run pytest tests/ --cov=hyperscribe --cov-report term-missing
# type checking
uv run mypy .
# linting
uv run ruff check . && uv run ruff format --check .
# evaluations (requires env vars for LLM keys)
uv run pytest evaluations/ --evaluation-difference-levels minor moderate severe critical
```
