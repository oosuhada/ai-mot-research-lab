#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.request
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps/api"
API_PYTHON = API_DIR / ".venv-prod/bin/python"
T9_ROOT = Path("/Volumes/T9 SSD/server-data/ai-mot-research-lab")
META_DONE = T9_ROOT / "opencitations/meta-2026-06.completed"
DATA_ROOT = T9_ROOT / "opencitations-index/v7"
STATE = DATA_ROOT / "pipeline-state.json"
IMPORT_STATE = DATA_ROOT / "import-state.json"
FIGSHARE_API = "https://api.figshare.com/v2/articles/24356626/versions/7"
USER_AGENT = "AI-MOT-Research-Lab/1.0 OpenCitations bootstrap"


def log(event: str, **fields: object) -> None:
    payload = {
        "at": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def save_state(payload: dict[str, object]) -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    temp = STATE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(STATE)


def fetch_manifest() -> list[dict[str, object]]:
    request = urllib.request.Request(FIGSHARE_API, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, list):
        raise RuntimeError("Figshare response did not contain a file manifest")

    normalized: list[dict[str, object]] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        url = str(item.get("download_url") or "")
        size = int(item.get("size") or 0)
        if not name.endswith(".zip") or not url or size <= 0:
            continue
        normalized.append({"name": name, "url": url, "size": size})
    normalized.sort(key=lambda item: natural_key(str(item["name"])))
    return normalized


def natural_key(name: str) -> tuple[int, ...]:
    values = [int(value) for value in re.findall(r"\d+", name)]
    return tuple(values) if values else (10**9,)


def ensure_storage() -> None:
    subprocess.run(
        [str(API_PYTHON), str(ROOT / "scripts/check-private-storage.py")],
        cwd=ROOT,
        check=True,
    )


def download(file_info: dict[str, object]) -> Path:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    path = DATA_ROOT / str(file_info["name"])
    expected = int(file_info["size"])
    current = path.stat().st_size if path.exists() else 0
    if current == expected:
        return path
    if current > expected:
        path.unlink()
        current = 0
    log("download_start", file=path.name, current_bytes=current, expected_bytes=expected)
    command = [
        "/usr/bin/curl",
        "-L",
        "--fail",
        "--retry",
        "12",
        "--retry-delay",
        "10",
        "-C",
        "-",
        "-o",
        str(path),
        str(file_info["url"]),
    ]
    subprocess.run(command, check=True)
    actual = path.stat().st_size
    if actual != expected:
        raise RuntimeError(f"Shard size mismatch for {path.name}: {actual}/{expected}")
    log("download_complete", file=path.name, bytes=actual)
    return path


def import_shard(path: Path) -> dict[str, object]:
    command = [
        str(API_PYTHON),
        "-m",
        "research_lab.cli",
        "import-opencitations-index-zip",
        "--input",
        str(path),
        "--batch-size",
        "5000",
        "--state",
        str(IMPORT_STATE),
    ]
    result = subprocess.run(
        command,
        cwd=API_DIR,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Importer returned non-JSON output for {path.name}") from exc
    if not isinstance(payload, dict) or payload.get("status") != "completed":
        raise RuntimeError(f"Importer did not complete for {path.name}: {payload}")
    return payload


def main() -> int:
    if not META_DONE.exists():
        log("waiting_for_meta", marker=str(META_DONE))
        return 75
    ensure_storage()
    manifest = fetch_manifest()
    if not manifest:
        raise RuntimeError("No OpenCitations Index ZIP shards found")

    state = load_json(STATE)
    completed = set(str(value) for value in (state.get("completed_files") or []))
    totals = state.get("totals") if isinstance(state.get("totals"), dict) else {}
    aggregate = {
        "records_scanned": int(totals.get("records_scanned") or 0),
        "local_edges": int(totals.get("local_edges") or 0),
        "inserted_edges": int(totals.get("inserted_edges") or 0),
        "duplicate_edges": int(totals.get("duplicate_edges") or 0),
        "skipped_nonlocal": int(totals.get("skipped_nonlocal") or 0),
        "invalid_rows": int(totals.get("invalid_rows") or 0),
    }

    log(
        "pipeline_start",
        shards=len(manifest),
        completed=len(completed),
        compressed_bytes=sum(int(item["size"]) for item in manifest),
    )
    for index, file_info in enumerate(manifest, start=1):
        name = str(file_info["name"])
        if name in completed:
            continue
        ensure_storage()
        path = download(file_info)
        started = time.monotonic()
        payload = import_shard(path)
        elapsed = round(time.monotonic() - started, 2)
        for key in aggregate:
            aggregate[key] += int(payload.get(key) or 0)
        completed.add(name)
        save_state(
            {
                "updated_at": datetime.now(UTC).isoformat(),
                "figshare_article": "24356626.v7",
                "completed_files": sorted(completed, key=natural_key),
                "total_files": len(manifest),
                "totals": aggregate,
                "last_file": name,
            }
        )
        with suppress(FileNotFoundError):
            path.unlink()
        log(
            "shard_complete",
            file=name,
            shard_index=index,
            total_shards=len(manifest),
            elapsed_seconds=elapsed,
            local_edges=payload.get("local_edges"),
            inserted_edges=payload.get("inserted_edges"),
            completed_count=len(completed),
        )

    done = DATA_ROOT / "index-v7.completed"
    done.write_text(
        json.dumps(
            {
                "completed_at": datetime.now(UTC).isoformat(),
                "shards": len(manifest),
                "totals": aggregate,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    log("pipeline_complete", shards=len(manifest), **aggregate)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except Exception as exc:
        log("pipeline_failed", error=f"{type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc
