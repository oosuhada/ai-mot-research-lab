from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[3] / "scripts/import-semantic-scholar-remote-bundles.py"
SPEC = importlib.util.spec_from_file_location("semantic_scholar_remote_import", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_process_inbox_rejects_bad_checksum(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    data = tmp_path / "2026-09-01"
    archive = tmp_path / "archive"
    inbox.mkdir()
    bundle = inbox / "papers-007.matched.jsonl.gz"
    with gzip.open(bundle, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps({"corpusid": 1}) + "\n")
    (inbox / "papers-007.manifest.json").write_text(
        json.dumps({"bundle_sha256": "bad"}), encoding="utf-8"
    )

    result = MODULE.process_inbox(inbox=inbox, data_root=data, archive=archive)

    assert result == {"processed": 0, "skipped": 0, "failed": 1}
    assert bundle.exists()


def test_process_inbox_archives_already_completed_bundle(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    data = tmp_path / "2026-09-01"
    archive = tmp_path / "archive"
    inbox.mkdir()
    data.mkdir()
    bundle = inbox / "papers-007.matched.jsonl.gz"
    with gzip.open(bundle, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps({"corpusid": 1}) + "\n")
    digest = MODULE.sha256_file(bundle)
    (inbox / "papers-007.manifest.json").write_text(
        json.dumps({"bundle_sha256": digest}), encoding="utf-8"
    )
    (data / "papers-state.json").write_text(
        json.dumps({"release": "2026-09-01", "dataset": "papers", "completed": ["007"]}),
        encoding="utf-8",
    )

    result = MODULE.process_inbox(inbox=inbox, data_root=data, archive=archive)

    assert result == {"processed": 1, "skipped": 0, "failed": 0}
    assert (archive / "papers/007/ack.json").is_file()
