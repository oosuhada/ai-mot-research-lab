from pathlib import Path
from types import SimpleNamespace

import pytest

from research_lab.storage_guard import PrivateStorageUnavailable, ensure_private_storage_ready


def settings(tmp_path: Path, **overrides):
    values = dict(
        private_data_root=tmp_path / "private",
        private_data_require_external=False,
        private_data_expected_mount=None,
        private_data_sentinel=None,
        private_data_min_free_gb=1,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_local_storage_remains_supported_for_development(tmp_path):
    root = ensure_private_storage_ready(settings(tmp_path))
    assert root.is_dir()


def test_external_guard_requires_mount_configuration(tmp_path):
    with pytest.raises(PrivateStorageUnavailable, match="not fully configured"):
        ensure_private_storage_ready(settings(tmp_path, private_data_require_external=True))
