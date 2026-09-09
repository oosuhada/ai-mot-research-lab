from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[3] / "scripts/prepare-s2orc-second-pass.py"
SPEC = importlib.util.spec_from_file_location("prepare_s2orc_second_pass", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_state_complete_requires_all_shards() -> None:
    assert MODULE.state_complete({"total": 3, "completed": ["000", "001", "002"]}) is True
    assert MODULE.state_complete({"total": 3, "completed": ["000", "001"]}) is False
    assert MODULE.state_complete({"total": 0, "completed": []}) is False


def test_prepare_waits_for_papers_before_api_or_state_reset(tmp_path: Path) -> None:
    data = tmp_path / "2026-09-01"
    data.mkdir()
    MODULE.save_json(
        data / "papers-state.json",
        {"release": "2026-09-01", "dataset": "papers", "total": 60, "completed": ["000"]},
    )

    result = MODULE.prepare_second_pass(
        data_root=data,
        phase_root=tmp_path / "phase",
        pro_shards=40,
        api_key="unused",
    )

    assert result == {"status": "waiting_for_papers", "completed": 1, "total": 60}
    assert not (tmp_path / "phase/READY.json").exists()
