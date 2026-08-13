from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import HTTPException

from research_lab.library import BrowseCursor, decode_browse_cursor, encode_browse_cursor


def test_browse_cursor_round_trip_preserves_stable_ordering_key() -> None:
    cursor = BrowseCursor(
        created_at=datetime(2026, 8, 23, 12, 30, tzinfo=UTC),
        paper_id=UUID("00000000-0000-4000-8000-000000000123"),
        offset=110,
        direction="after",
    )

    encoded = encode_browse_cursor(cursor)

    assert "+" not in encoded
    assert "/" not in encoded
    assert "=" not in encoded
    assert decode_browse_cursor(encoded) == cursor


@pytest.mark.parametrize("value", ["not-base64", "e30", "eyJvZmZzZXQiOi0xfQ"])
def test_invalid_browse_cursor_is_rejected_as_validation_error(value: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        decode_browse_cursor(value)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Invalid paper browse cursor"
