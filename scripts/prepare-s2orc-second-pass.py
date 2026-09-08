#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps/api/src"
sys.path.insert(0, str(API_SRC))

from research_lab.config import Settings  # noqa: E402

BASE_URL = "https://api.semanticscholar.org/datasets/v1"
USER_AGENT = "AI-MOT-Research-Lab/1.0 distributed-s2orc-pass2"


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def state_complete(state: dict[str, Any]) -> bool:
    completed = {str(value) for value in state.get("completed") or []}
    try:
        total = int(state.get("total") or 0)
    except (TypeError, ValueError):
        return False
    return total > 0 and len(completed) >= total


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_dataset_urls(*, release: str, dataset: str, api_key: str) -> list[str]:
    url = f"{BASE_URL}/release/{release}/dataset/{dataset}"
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT, "x-api-key": api_key}
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
                payload = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise RuntimeError("Semantic Scholar dataset API key was rejected") from exc
            if exc.code not in {408, 409, 425, 429} and exc.code < 500:
                raise
            attempt += 1
            retry_after = exc.headers.get("Retry-After")
            try:
                retry_seconds = float(retry_after) if retry_after else 0.0
            except ValueError:
                retry_seconds = 0.0
            time.sleep(max(retry_seconds, min(5 * (2 ** min(attempt - 1, 4)), 60)))
        except urllib.error.URLError:
            attempt += 1
            time.sleep(min(5 * (2 ** min(attempt - 1, 4)), 60))
    raw_files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(raw_files, list):
        raise RuntimeError(f"Semantic Scholar {dataset} manifest did not contain files")
    urls: list[str] = []
    for item in raw_files:
        if isinstance(item, str) and item.startswith("http"):
            urls.append(item)
        elif isinstance(item, dict):
            for key in ("url", "download_url", "downloadUrl", "link"):
                value = item.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    urls.append(value)
                    break
    if not urls:
        raise RuntimeError(f"Semantic Scholar {dataset} manifest returned no URLs")
    return urls


def _write_role_archive(
    *,
    phase_root: Path,
    role: str,
    shard_ids: list[int],
    urls: list[str],
    index_path: Path,
) -> Path:
    role_root = phase_root / role
    urls_root = role_root / "urls"
    urls_root.mkdir(parents=True, exist_ok=True)
    for shard in shard_ids:
        path = urls_root / f"s2orc_v2-{shard:03d}.url"
        path.write_text(urls[shard] + "\n", encoding="utf-8")
        path.chmod(0o600)
    archive = phase_root / f"{role}-work.tar"
    with tarfile.open(archive, "w") as tar:
        tar.add(index_path, arcname="index.tsv.gz")
        for shard in shard_ids:
            tar.add(urls_root / f"s2orc_v2-{shard:03d}.url", arcname=f"urls/s2orc_v2-{shard:03d}.url")
    archive.chmod(0o600)
    return archive


def prepare_second_pass(
    *,
    data_root: Path,
    phase_root: Path,
    pro_shards: int,
    api_key: str,
) -> dict[str, Any]:
    ready = phase_root / "READY.json"
    if ready.is_file():
        return {"status": "already_prepared", **load_json(ready)}

    papers_state_path = data_root / "papers-state.json"
    papers_state = load_json(papers_state_path)
    if not state_complete(papers_state):
        return {
            "status": "waiting_for_papers",
            "completed": len({str(value) for value in papers_state.get("completed") or []}),
            "total": int(papers_state.get("total") or 0),
        }

    release = str(papers_state.get("release") or data_root.name)
    s2_state_path = data_root / "s2orc_v2-state.json"
    s2_state = load_json(s2_state_path)
    pass1_backup = data_root / "s2orc_v2-state.pass1.json"
    if not pass1_backup.is_file() and not state_complete(s2_state):
        return {"status": "waiting_for_s2orc_pass1"}

    phase_root.mkdir(parents=True, exist_ok=True)
    index_path = phase_root / "index.tsv.gz"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/export-s2orc-filter-index.py"),
            "--purpose",
            "s2orc",
            "--output",
            str(index_path),
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    urls = fetch_dataset_urls(release=release, dataset="s2orc_v2", api_key=api_key)
    split = min(max(pro_shards, 1), len(urls) - 1)
    pro_ids = list(range(0, split))
    air_ids = list(range(split, len(urls)))
    pro_archive = _write_role_archive(
        phase_root=phase_root,
        role="pro",
        shard_ids=pro_ids,
        urls=urls,
        index_path=index_path,
    )
    air_archive = _write_role_archive(
        phase_root=phase_root,
        role="air",
        shard_ids=air_ids,
        urls=urls,
        index_path=index_path,
    )

    if not pass1_backup.is_file():
        shutil.copy2(s2_state_path, pass1_backup)
    save_json(
        s2_state_path,
        {
            "release": release,
            "dataset": "s2orc_v2",
            "pass": 2,
            "updated_at": datetime.now(UTC).isoformat(),
            "completed": [],
            "total": len(urls),
            "previous_state": pass1_backup.name,
        },
    )
    payload = {
        "status": "prepared",
        "release": release,
        "created_at": datetime.now(UTC).isoformat(),
        "dataset": "s2orc_v2",
        "pass": 2,
        "total": len(urls),
        "pro_shards": len(pro_ids),
        "air_shards": len(air_ids),
        "index_sha256": sha256_file(index_path),
        "pro_archive_sha256": sha256_file(pro_archive),
        "air_archive_sha256": sha256_file(air_archive),
    }
    save_json(ready, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a distributed S2ORC pass after papers mapping")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--phase-root", type=Path, required=True)
    parser.add_argument("--pro-shards", type=int, default=40)
    args = parser.parse_args()
    api_key = (Settings().semantic_scholar_api_key or os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or "").strip()
    if not api_key:
        print(json.dumps({"status": "api_key_required"}))
        return 78
    result = prepare_second_pass(
        data_root=args.data_root,
        phase_root=args.phase_root,
        pro_shards=args.pro_shards,
        api_key=api_key,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
