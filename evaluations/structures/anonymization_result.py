from pathlib import Path

from mypyc.ir.class_ir import NamedTuple

from evaluations.structures.anonymization_substitution import AnonymizationSubstitution


class AnonymizationResult(NamedTuple):
    files: list[Path]
    substitutions: list[AnonymizationSubstitution]
