from __future__ import annotations

import shutil
from pathlib import Path

from research_lab.config import Settings


class PrivateStorageUnavailable(RuntimeError):
    """Raised when the configured private blob store is unsafe to use."""


def ensure_private_storage_ready(settings: Settings) -> Path:
    root = settings.private_data_root.expanduser()
    if not settings.private_data_require_external:
        root.mkdir(parents=True, exist_ok=True)
        return root

    mount = settings.private_data_expected_mount
    sentinel = settings.private_data_sentinel
    if mount is None or sentinel is None:
        raise PrivateStorageUnavailable("external private storage guard is not fully configured")

    mount = mount.expanduser()
    sentinel = sentinel.expanduser()
    if not mount.is_mount():
        raise PrivateStorageUnavailable(f"expected external mount is unavailable: {mount}")
    if not sentinel.is_file():
        raise PrivateStorageUnavailable(f"storage sentinel is missing: {sentinel}")
    if not root.is_absolute():
        raise PrivateStorageUnavailable("external private_data_root must be an absolute path")
    try:
        root.relative_to(mount)
    except ValueError as exc:
        raise PrivateStorageUnavailable("private_data_root is outside the expected external mount") from exc

    root.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(root).free
    minimum = settings.private_data_min_free_gb * 1024**3
    if free_bytes < minimum:
        raise PrivateStorageUnavailable(
            f"private storage free space is below reserve: {free_bytes / 1024**3:.1f} GiB < "
            f"{settings.private_data_min_free_gb} GiB"
        )
    return root
