from __future__ import annotations

import uuid
from pathlib import Path


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
    workers. New blobs therefore fan out by the first four UUID hex digits.

    Existing unsharded blob ids remain valid because readers persist and use the
    exact ``private_blob_id`` recorded on each PaperVersion; this helper changes
    only the layout of newly written blobs.
    """
    paper_key = str(paper_id)
    compact = paper_key.replace("-", "")
    extension = suffix.lstrip(".")
    relative = Path("blobs") / compact[:2] / compact[2:4] / paper_key / f"{digest}.{extension}"
    blob_id = relative.as_posix()
    return blob_id, root / relative
