from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[3] / "scripts/export-neo4j-projection.py"
SPEC = importlib.util.spec_from_file_location("export_neo4j_projection", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_projection_exporter_has_expected_entrypoint() -> None:
    assert callable(MODULE.export_projection)
