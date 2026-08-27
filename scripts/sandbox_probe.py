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

from plugin_runner.sandbox import ALLOWED_MODULES  # noqa: E402

# Dunders the sandbox permits on ordinary objects. Anything else raises at runtime.
SAFE_DUNDERS = {"__class__", "__name__", "__doc__", "__len__", "__iter__", "__next__"}


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
