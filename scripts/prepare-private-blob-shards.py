#!/usr/bin/env python3
from __future__ import annotations

import json

from research_lab.config import Settings
from research_lab.private_blob_storage import prepare_private_blob_shards, verify_private_blob_shards
from research_lab.storage_guard import ensure_private_storage_ready


def main() -> int:
    settings = Settings()
    root = ensure_private_storage_ready(settings)
    paths = prepare_private_blob_shards(root)
    payload = {
        "status": "completed" if verify_private_blob_shards(root) else "failed",
        "root": str(root),
        "shards": len(paths),
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
