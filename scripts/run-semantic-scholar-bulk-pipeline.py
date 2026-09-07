#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps/api"
sys.path.insert(0, str(API_DIR / "src"))

from research_lab.config import Settings  # noqa: E402

API_PYTHON = API_DIR / ".venv-prod/bin/python"
DATA_ROOT = Path("/Volumes/T9 SSD/server-data/ai-mot-research-lab/semantic-scholar")
BASE_URL = "https://api.semanticscholar.org/datasets/v1"
USER_AGENT = "AI-MOT-Research-Lab/1.0 Semantic Scholar dataset bootstrap"
# Fast Graph batch mapping makes corpus IDs available first, so full text can be
# consumed immediately. The massive papers dump remains a fallback/reconciliation
# pass after S2ORC rather than blocking it.
DATASET_ORDER = ("s2orc_v2", "papers")
DOWNLOAD_WORKERS = 4
MIN_API_INTERVAL_SECONDS = 1.10
_last_api_request_at = 0.0


def log(event: str, **fields: object) -> None:
    print(
        json.dumps(
            {"at": datetime.now(UTC).isoformat(), "event": event, **fields},
            ensure_ascii=False,
        ),
        flush=True,
    )


def _wait_for_api_slot() -> None:
    """Respect the partner key's cumulative 1 request/second API limit."""
    global _last_api_request_at
    now = time.monotonic()
    remaining = MIN_API_INTERVAL_SECONDS - (now - _last_api_request_at)
    if remaining > 0:
        time.sleep(remaining)
    _last_api_request_at = time.monotonic()


def request_json(url: str, *, api_key: str) -> dict[str, Any]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "x-api-key": api_key,
    }
    for attempt in range(8):
        _wait_for_api_slot()
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise RuntimeError(
                    "Semantic Scholar full dataset access requires an authorized API key"
                ) from exc
            if exc.code != 429 or attempt == 7:
                raise
            retry_after = exc.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else min(2.0**attempt, 30.0)
            except ValueError:
                delay = min(2.0**attempt, 30.0)
            delay = max(delay, MIN_API_INTERVAL_SECONDS)
            log("api_rate_limited", attempt=attempt + 1, retry_seconds=round(delay, 2))
            time.sleep(delay)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected JSON response from {url}")
    return payload


def latest_release(api_key: str) -> str:
    payload = request_json(f"{BASE_URL}/release/latest", api_key=api_key)
    release = str(payload.get("release_id") or "").strip()
    if not release:
        raise RuntimeError("Semantic Scholar latest release did not contain release_id")
    return release


def dataset_files(release: str, dataset: str, api_key: str) -> list[str]:
    payload = request_json(
        f"{BASE_URL}/release/{release}/dataset/{dataset}",
        api_key=api_key,
    )
    raw_files = payload.get("files")
    if not isinstance(raw_files, list):
        raise RuntimeError(f"Semantic Scholar {dataset} response did not contain files")
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
        raise RuntimeError(f"Semantic Scholar {dataset} returned no download URLs")
    return urls


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def download(url: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    current = output.stat().st_size if output.exists() else 0
    log("download_start", file=output.name, current_bytes=current)
    subprocess.run(
        [
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
            str(output),
            url,
        ],
        check=True,
    )
    log("download_complete", file=output.name, bytes=output.stat().st_size)


def run_cli(arguments: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        [str(API_PYTHON), "-m", "research_lab.cli", *arguments],
        cwd=API_DIR,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict) or payload.get("status") != "completed":
        raise RuntimeError(f"Research CLI did not complete: {payload}")
    return payload


def process_dataset(
    *,
    release: str,
    dataset: str,
    urls: list[str],
    state_path: Path,
    download_workers: int = DOWNLOAD_WORKERS,
) -> None:
    state = load_state(state_path)
    completed = set(str(value) for value in (state.get("completed") or []))
    dataset_root = state_path.parent / dataset
    dataset_root.mkdir(parents=True, exist_ok=True)
    remaining = [(index, url) for index, url in enumerate(urls) if f"{index:03d}" not in completed]
    if not remaining:
        return

    workers = min(max(download_workers, 1), 6)
    iterator = iter(remaining)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures: dict[object, tuple[int, Path]] = {}

        def submit_next() -> bool:
            try:
                index, url = next(iterator)
            except StopIteration:
                return False
            shard = dataset_root / f"{dataset}-{index:03d}.jsonl.gz"
            future = pool.submit(download, url, shard)
            futures[future] = (index, shard)
            return True

        for _ in range(workers):
            if not submit_next():
                break

        while futures:
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                index, shard = futures.pop(future)
                future.result()
                # Refill the download window before local import so network I/O
                # continues while the current shard is parsed into PostgreSQL.
                submit_next()
                started = time.monotonic()
                if dataset == "papers":
                    result = run_cli(
                        [
                            "map-semantic-scholar-papers-shard",
                            "--input",
                            str(shard),
                            "--commit-every",
                            "10000",
                        ]
                    )
                elif dataset == "s2orc_v2":
                    result = run_cli(["import-s2orc-shard", "--input", str(shard)])
                else:
                    raise RuntimeError(f"Unsupported dataset: {dataset}")
                elapsed = round(time.monotonic() - started, 2)
                key = f"{index:03d}"
                completed.add(key)
                save_state(
                    state_path,
                    {
                        "release": release,
                        "dataset": dataset,
                        "updated_at": datetime.now(UTC).isoformat(),
                        "completed": sorted(completed),
                        "total": len(urls),
                        "last_result": result,
                    },
                )
                shard.unlink(missing_ok=True)
                log(
                    "shard_complete",
                    release=release,
                    dataset=dataset,
                    shard=index,
                    total=len(urls),
                    elapsed_seconds=elapsed,
                    result=result,
                )


def main() -> int:
    settings = Settings()
    api_key = (settings.semantic_scholar_api_key or "").strip()
    if not api_key:
        log(
            "api_key_required",
            env="SEMANTIC_SCHOLAR_API_KEY",
            request_page="https://www.semanticscholar.org/product/api#Partner-Form",
        )
        return 78

    subprocess.run(
        [str(API_PYTHON), str(ROOT / "scripts/check-private-storage.py")],
        cwd=ROOT,
        check=True,
    )
    fast_mapping = run_cli(
        [
            "map-semantic-scholar-batch-api",
            "--max-items",
            "200000",
            "--batch-size",
            "500",
        ]
    )
    log("fast_mapping_complete", result=fast_mapping)
    release = latest_release(api_key)
    release_root = DATA_ROOT / release
    release_root.mkdir(parents=True, exist_ok=True)
    log("pipeline_start", release=release, datasets=list(DATASET_ORDER))
    for dataset in DATASET_ORDER:
        urls = dataset_files(release, dataset, api_key)
        log("dataset_ready", release=release, dataset=dataset, shards=len(urls))
        process_dataset(
            release=release,
            dataset=dataset,
            urls=urls,
            state_path=release_root / f"{dataset}-state.json",
        )

    done = release_root / "completed.json"
    done.write_text(
        json.dumps(
            {
                "completed_at": datetime.now(UTC).isoformat(),
                "release": release,
                "datasets": list(DATASET_ORDER),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log("pipeline_complete", release=release)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        log("pipeline_failed", error=f"{type(exc).__name__}: {exc}")
        raise
