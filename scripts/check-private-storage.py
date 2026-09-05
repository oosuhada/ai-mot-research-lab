#!/usr/bin/env python3
from __future__ import annotations

import sys

from research_lab.config import Settings
from research_lab.storage_guard import PrivateStorageUnavailable, ensure_private_storage_ready


def main() -> int:
    settings = Settings()
    try:
        root = ensure_private_storage_ready(settings)
    except PrivateStorageUnavailable as exc:
        print(f"Private storage unavailable: {exc}", file=sys.stderr)
        return 75
    print(f"Private storage ready: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
