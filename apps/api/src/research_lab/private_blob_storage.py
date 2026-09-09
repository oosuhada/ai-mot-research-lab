from __future__ import annotations

import uuid
from pathlib import Path

PRIVATE_BLOB_SHARD_NAMES: tuple[str, ...] = tuple(f"{index:02x}" for index in range(256))


def prepare_private_blob_shards(root: Path) -> list[Path]:
    """Create the fixed 256-way blob fan-out used by full-text workers."""
    blobs_root = root / "blobs"
    blobs_root.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for shard_name in PRIVATE_BLOB_SHARD_NAMES:
        shard = blobs_root / shard_name
        shard.mkdir(exist_ok=True)
        paths.append(shard)
    return paths


def verify_private_blob_shards(root: Path) -> bool:
    blobs_root = root / "blobs"
    return blobs_root.is_dir() and all((blobs_root / name).is_dir() for name in PRIVATE_BLOB_SHARD_NAMES)


def require_private_blob_shard(shard: Path) -> None:
    if not shard.is_dir():
        raise RuntimeError(
            "Private blob shard is not prepared; run scripts/prepare-private-blob-shards.py before workers"
        )


def sharded_private_blob(
    root: Path,
    paper_id: uuid.UUID,
    digest: str,
    suffix: str,
) -> tuple[str, Path]:
    """Return a stable, fan-out-safe relative blob id and absolute path.

    The production private corpus lives on an ExFAT volume. Keeping tens of
    thousands of paper directories immediately under one parent makes metadata
    operations increasingly expensive and can stall concurrent full-text
    workers. New blobs therefore use one of 256 pre-created shard directories.

    Existing unsharded blob ids remain valid because readers persist and use the
    exact ``private_blob_id`` recorded on each PaperVersion; this helper changes
    only the layout of newly written blobs.
    """
    paper_key = str(paper_id)
    compact = paper_key.replace("-", "")
    extension = suffix.lstrip(".")
    relative = Path("blobs") / compact[:2] / f"{paper_key}_{digest}.{extension}"
    blob_id = relative.as_posix()
    return blob_id, root / relative
