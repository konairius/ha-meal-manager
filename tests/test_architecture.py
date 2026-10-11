"""The core must stay independent of Home Assistant."""

from __future__ import annotations

import ast
from pathlib import Path

CORE = Path(__file__).parents[1] / "custom_components" / "meal_manager" / "core"


def test_core_has_no_homeassistant_imports() -> None:
    offenders = []
    for path in CORE.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            offenders += [
                f"{path.name}: {n}" for n in names if n.split(".")[0] in {"homeassistant", "voluptuous"}
            ]
    assert offenders == []
