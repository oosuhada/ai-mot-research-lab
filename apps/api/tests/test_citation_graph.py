from __future__ import annotations

import uuid

from research_lab.schemas import CitationNeighbor


def test_citation_neighbor_direction_is_explicit() -> None:
    row = CitationNeighbor(
        id=uuid.uuid4(),
        title="Paper",
        direction="backward",
        source="openalex",
    )
    assert row.direction == "backward"
