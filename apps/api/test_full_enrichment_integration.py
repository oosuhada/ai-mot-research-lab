#!/usr/bin/env python3
"""Integration test for FullTextEnrichmentWorker with Sci-Hub and LibGen resolvers."""

from __future__ import annotations

import sys
sys.path.insert(0, 'src')

from datetime import datetime, timezone
from typing import cast

from research_lab.config import Settings
from research_lab.full_text_enrichment import FullTextEnrichmentWorker
from research_lab.models import Paper


def test_full_enrichment_worker_with_scihub_libgen() -> None:
    """Test that FullTextEnrichmentWorker properly initializes Sci-Hub and LibGen resolvers."""
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        sci_hub_base_urls=["https://sci-hub.se", "https://sci-hub.st"],
        libgen_api_base_url="http://libgen.rs",
        request_timeout_seconds=30,
    )
    
    worker = FullTextEnrichmentWorker(
        session=None,  # type: ignore
        settings=settings,
    )
    
    # Verify all expected resolvers are registered
    resolver_names = [type(r).__name__ for r in worker.resolvers]
    
    expected_resolvers = [
        'OpenAlexSourceResolver',
        'EuropePmcSourceResolver', 
        'ArxivResolver',
        'UnpaywallSourceResolver',
        'CoreSourceResolver',
        'PreprintSourceResolver',
        'SciHubSourceResolver',
        'LibGenSourceResolver',
    ]
    
    print(f"Registered resolvers: {resolver_names}")
    
    for expected in expected_resolvers:
        assert expected in resolver_names, f"Missing resolver: {expected}"
        print(f"✓ {expected} is registered")
    
    # Verify SciHub and LibGen are properly initialized as attributes
    assert hasattr(worker, 'sci_hub_resolver'), "SciHubSourceResolver not initialized"
    assert hasattr(worker, 'libgen_resolver'), "LibGenSourceResolver not initialized"
    print("✓ SciHubSourceResolver and LibGenSourceResolver are accessible as worker attributes")
    
    # Test paper creation with DOI
    paper = Paper(
        title="Test Paper with DOI",
        doi="10.1038/nature12345",
        is_oa=True,
        primary_source="doi",
        source_record_id="nature12345",
        retrieved_at=datetime.now(timezone.utc),
        provenance={},
    )
    
    # Test that resolver methods exist
    sci_hub_candidates = worker.sci_hub_resolver.resolve(paper)
    libgen_candidates = worker.libgen_resolver.resolve(paper)
    
    print(f"✓ SciHub resolved {len(sci_hub_candidates)} candidates")
    print(f"✓ LibGen resolved {len(libgen_candidates)} candidates")
    
    # Verify that resolvers implement FullTextSourceResolver protocol (by checking resolve method)
    assert hasattr(worker.sci_hub_resolver, 'resolve'), "SciHubSourceResolver missing resolve method"
    assert hasattr(worker.libgen_resolver, 'resolve'), "LibGenSourceResolver missing resolve method"
    print("✓ SciHubSourceResolver and LibGenSourceResolver implement FullTextSourceResolver protocol")


if __name__ == "__main__":
    print("=" * 60)
    print("Full Enrichment Worker Integration Test")
    print("=" * 60)
    
    test_full_enrichment_worker_with_scihub_libgen()
    
    print("\n" + "=" * 60)
    print("All integration tests passed!")
    print("=" * 60)
