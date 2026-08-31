#!/usr/bin/env python
"""Static check for plugin-sandbox violations that `canvas validate` cannot see.

`canvas validate` executes each handler's module-level code, so it catches bad imports
and things like `@dataclass`. It explicitly does not exercise request-time code, and the
plugin runner kills a sandbox violation before the plugin's own logger runs — so the
symptom on the instance is a 500 with an empty body and nothing in the logs.

Two rules are checked here, both of which have already cost us a deploy:

1. `ALLOWED_MODULES` allowlists module attributes **by name**, not by module. `time` is
   allowed but `time.monotonic` is not; `random` is allowed but `random.random` is not.
2. Underscored and dunder attribute access on objects is blocked by the sandbox's
   `_safe_getattr`, so `obj.__dict__` fails at runtime.

Run with the canvas CLI's interpreter, which is where `plugin_runner` lives:

    "$(dirname "$(readlink -f "$(which canvas)")")/python" scripts/sandbox_probe.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "hyperscribe"
sys.path.insert(0, str(PLUGIN.parent))

import builtins as _builtins  # noqa: E402

from RestrictedPython import safe_builtins, utility_builtins  # noqa: E402

from plugin_runner.sandbox import (  # noqa: E402
    ALLOWED_MODULES,
    SAFE_EXTERNAL_DUNDER_READ_ATTRIBUTES,
)

# Sourced from the sandbox itself rather than hand-written, so this cannot drift from what
# the runner actually permits.
SAFE_DUNDERS = set(SAFE_EXTERNAL_DUNDER_READ_ATTRIBUTES)

# Builtins the sandbox provides. Mirrors the dict the runner installs as __builtins__:
# RestrictedPython's two base sets plus the explicit additions. Notably absent: `type`,
# `open`, `eval`, `exec`, `print`, `format`, `id`. Calling one of those raises NameError at
# REQUEST time, which `canvas validate` cannot see because it only executes module-level
# code. `isinstance`, `issubclass`, `set`, `frozenset` and `sorted` ARE available - they
# come in via RestrictedPython's safe_builtins, and an earlier version of this comment
# wrongly listed them as absent.
ALLOWED_BUILTINS = (
    set(safe_builtins)
    | set(utility_builtins)
    | {
        "__import__",
        "all",
        "any",
        "classmethod",
        "dict",
        "enumerate",
        "filter",
        "getattr",
        "hasattr",
        "iter",
        "list",
        "map",
        "max",
        "min",
        "next",
        "property",
        "reversed",
        "staticmethod",
        "sum",
        "super",
        "vars",
        "extract_exc_frames",
    }
)


# Names that are legal to *call* even though they are not builtins: anything the module
# imports or defines itself is resolved from module scope, not __builtins__.
def _module_level_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, (ast.arg,)):
            names.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.comprehension,)) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _annotation_nodes(tree: ast.AST) -> set[int]:
    """Node ids appearing only inside annotations.

    `from __future__ import annotations` makes these strings that are never evaluated,
    so `re.Pattern[str]` in a signature is not a sandbox concern even though
    `re.Pattern` is not allowlisted.
    """
    marked: set[int] = set()

    def mark(node: ast.AST | None) -> None:
        if node is None:
            return
        for child in ast.walk(node):
            marked.add(id(child))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            mark(node.returns)
            for arg in [*node.args.args, *node.args.kwonlyargs, *node.args.posonlyargs]:
                mark(arg.annotation)
            mark(node.args.vararg.annotation if node.args.vararg else None)
            mark(node.args.kwarg.annotation if node.args.kwarg else None)
        elif isinstance(node, ast.AnnAssign):
            mark(node.annotation)
    return marked


_BUILTIN_NAMES = set(dir(_builtins))


def check(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return []

    rel = path.relative_to(PLUGIN.parent)
    skip = _annotation_nodes(tree)
    problems: list[str] = []
    imported: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ALLOWED_MODULES:
                    imported[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module in ALLOWED_MODULES:
            allowed = ALLOWED_MODULES[node.module] or ()
            for alias in node.names:
                if alias.name not in allowed:
                    problems.append(
                        f"{rel}:{node.lineno}  from {node.module} import {alias.name}  "
                        f"-- not in ALLOWED_MODULES[{node.module!r}]"
                    )

    # Disallowed builtins. This is the gap that let `type(exc).__name__` through: the
    # module-attribute and dunder rules both passed it, and it would have raised NameError
    # only when a request actually hit that line.
    defined = _module_level_names(tree)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and id(node) not in skip
            and node.id in _BUILTIN_NAMES
            and node.id not in ALLOWED_BUILTINS
            and node.id not in defined
        ):
            problems.append(
                f"{rel}:{node.lineno}  {node.id}()  -- not in the sandbox's builtins; raises NameError at request time"
            )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or id(node) in skip:
            continue
        # super().__init__() and friends are legal and used throughout the plugin.
        is_super = (
            isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "super"
        )
        if not is_super and node.attr.startswith("__") and node.attr not in SAFE_DUNDERS:
            problems.append(f"{rel}:{node.lineno}  .{node.attr}  -- dunder access is blocked at runtime")
        if isinstance(node.value, ast.Name) and node.value.id in imported:
            module = imported[node.value.id]
            allowed = ALLOWED_MODULES[module] or ()
            if node.attr not in allowed:
                problems.append(
                    f"{rel}:{node.lineno}  {module}.{node.attr}  "
                    f"-- not in ALLOWED_MODULES[{module!r}] (allowed: {', '.join(sorted(allowed))})"
                )
    return problems


def main() -> int:
    problems = sorted({p for path in sorted(PLUGIN.rglob("*.py")) for p in check(path)})
    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print("  ok    no sandbox attribute violations found")
    print(f"\n{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
