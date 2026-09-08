#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps/api/src"
sys.path.insert(0, str(API_SRC))

from research_lab.bulk_full_text import S2OrcShardImporter  # noqa: E402
from research_lab.config import get_settings  # noqa: E402
from research_lab.db import SessionLocal  # noqa: E402
from research_lab.semantic_scholar_bulk import SemanticScholarPapersMapper  # noqa: E402

MANIFEST_PATTERN = re.compile(r"^(?P<dataset>s2orc_v2|papers)-(?P<shard>\d{3})\.manifest\.json$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def import_bundle(bundle: Path, *, dataset: str) -> dict[str, Any]:
    settings = get_settings()
    with SessionLocal() as session:
        if dataset == "s2orc_v2":
            return S2OrcShardImporter(session, settings).run(bundle)
        if dataset == "papers":
            result = SemanticScholarPapersMapper(session, commit_every=10_000).run(bundle)
            return {
                "run_id": result.run_id,
                "status": result.status,
                "records_scanned": result.records_scanned,
                "matched": result.matched,
                "updated": result.updated,
                "already_mapped": result.already_mapped,
                "conflicts": result.conflicts,
                "unmatched": result.unmatched,
                "invalid": result.invalid,
            }
    raise ValueError(f"Unsupported dataset: {dataset}")


def process_inbox(*, inbox: Path, data_root: Path, archive: Path) -> dict[str, int]:
    processed = skipped = failed = 0
    for manifest_path in sorted(inbox.glob("*.manifest.json")):
        match = MANIFEST_PATTERN.match(manifest_path.name)
        if match is None:
            skipped += 1
            continue
        dataset = match.group("dataset")
        shard = match.group("shard")
        bundle = inbox / f"{dataset}-{shard}.matched.jsonl.gz"
        if not bundle.is_file():
            skipped += 1
            continue
        manifest = load_json(manifest_path)
        expected = str(manifest.get("bundle_sha256") or "")
        if not expected or sha256_file(bundle) != expected:
            failed += 1
            continue

        state_path = data_root / f"{dataset}-state.json"
        state = load_json(state_path)
        completed = {str(value) for value in state.get("completed") or []}
        if shard in completed:
            result: dict[str, Any] = {"status": "already_completed"}
        else:
            try:
                result = import_bundle(bundle, dataset=dataset)
            except Exception as exc:
                save_json(
                    inbox / f"{dataset}-{shard}.error.json",
                    {
                        "at": datetime.now(UTC).isoformat(),
                        "dataset": dataset,
                        "shard": shard,
                        "error": f"{type(exc).__name__}: {exc}"[:2000],
                    },
                )
                failed += 1
                continue
            completed.add(shard)
            state.update(
                {
                    "release": state.get("release") or data_root.name,
                    "dataset": dataset,
                    "updated_at": datetime.now(UTC).isoformat(),
                    "completed": sorted(completed),
                    "last_result": result,
                }
            )
            save_json(state_path, state)

        destination = archive / dataset / shard
        destination.mkdir(parents=True, exist_ok=True)
        manifest_path.replace(destination / manifest_path.name)
        bundle.replace(destination / bundle.name)
        error_path = inbox / f"{dataset}-{shard}.error.json"
        error_path.unlink(missing_ok=True)
        save_json(
            destination / "ack.json",
            {
                "at": datetime.now(UTC).isoformat(),
                "dataset": dataset,
                "shard": shard,
                "result": result,
            },
        )
        processed += 1
    return {"processed": processed, "skipped": skipped, "failed": failed}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and import remote Semantic Scholar bundles")
    parser.add_argument("--inbox", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    args = parser.parse_args()

    args.lock.parent.mkdir(parents=True, exist_ok=True)
    with args.lock.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "busy"}))
            return 0
        args.inbox.mkdir(parents=True, exist_ok=True)
        result = process_inbox(inbox=args.inbox, data_root=args.data_root, archive=args.archive)
    print(json.dumps({"status": "completed", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
