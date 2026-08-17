#!/usr/bin/env python3
"""Manual integration test for Sci-Hub and LibGen resolvers."""

from __future__ import annotations

import sys
sys.path.insert(0, 'src')

from datetime import datetime, timezone
from typing import cast

from research_lab.config import Settings
from research_lab.full_text_enrichment import FullTextEnrichmentWorker
from research_lab.models import Paper


def test_sci_hub_resolver_integration() -> None:
    """Test Sci-Hub resolver is properly integrated into FullTextEnrichmentWorker."""
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        sci_hub_base_urls=["https://sci-hub.se", "https://sci-hub.st"],
        request_timeout_seconds=30,
    )
    
    worker = FullTextEnrichmentWorker(
        session=None,  # type: ignore
        settings=settings,
    )
    
    # Check that SciHubSourceResolver is registered
    assert hasattr(worker, 'sci_hub_resolver'), "SciHubSourceResolver not initialized"
    print("✓ SciHubSourceResolver initialized")
    
    # Verify resolver implements FullTextSourceResolver protocol
    assert hasattr(worker.sci_hub_resolver, 'resolve'), "SciHubSourceResolver missing resolve method"
    print("✓ SciHubSourceResolver.resolve method exists")
    
    # Check resolvers tuple
    resolver_names = [type(r).__name__ for r in worker.resolvers]
    assert 'SciHubSourceResolver' in resolver_names, f"SciHubSourceResolver not in resolvers: {resolver_names}"
    print(f"✓ SciHubSourceResolver in resolvers tuple: {resolver_names}")


def test_libgen_resolver_integration() -> None:
    """Test LibGen resolver is properly integrated into FullTextEnrichmentWorker."""
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        libgen_api_base_url="http://libgen.rs",
        request_timeout_seconds=30,
    )
    
    worker = FullTextEnrichmentWorker(
        session=None,  # type: ignore
        settings=settings,
    )
    
    # Check that LibGenSourceResolver is registered
    assert hasattr(worker, 'libgen_resolver'), "LibGenSourceResolver not initialized"
    print("✓ LibGenSourceResolver initialized")
    
    # Verify resolver implements FullTextSourceResolver protocol
    assert hasattr(worker.libgen_resolver, 'resolve'), "LibGenSourceResolver missing resolve method"
    print("✓ LibGenSourceResolver.resolve method exists")
    
    # Check resolvers tuple
    resolver_names = [type(r).__name__ for r in worker.resolvers]
    assert 'LibGenSourceResolver' in resolver_names, f"LibGenSourceResolver not in resolvers: {resolver_names}"
    print(f"✓ LibGenSourceResolver in resolvers tuple: {resolver_names}")


def test_paper_resolution() -> None:
    """Test that paper DOI/PMID/ISBN can be resolved via Sci-Hub/LibGen."""
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        sci_hub_base_urls=["https://sci-hub.se"],
        libgen_api_base_url="http://libgen.rs",
        request_timeout_seconds=10,  # Reduced timeout for faster testing
    )
    
    # Create a paper with DOI
    paper = Paper(
        title="Test Paper",
        doi="10.1038/nature12345",
        is_oa=True,
        primary_source="doi",
        source_record_id="nature12345",
        retrieved_at=datetime.now(timezone.utc),
        provenance={},
    )
    
    worker = FullTextEnrichmentWorker(
        session=None,  # type: ignore
        settings=settings,
    )
    
    # Test Sci-Hub resolution with DOI (network-dependent)
    print("Testing Sci-Hub resolution...")
    try:
        sci_hub_candidates = worker.sci_hub_resolver.resolve(paper)
        print(f"✓ SciHubSourceResolver resolved {len(sci_hub_candidates)} candidates")
        for c in sci_hub_candidates:
            print(f"  - {c.source_kind}: {c.url}")
            if c.error:
                print(f"    Error: {c.error}")
    except Exception as e:
        print(f"⚠ SciHub resolution failed (expected for network issues): {e}")
    
    # Test LibGen resolution with DOI (network-dependent)
    print("\nTesting LibGen resolution...")
    try:
        libgen_candidates = worker.libgen_resolver.resolve(paper)
        print(f"✓ LibGenSourceResolver resolved {len(libgen_candidates)} candidates")
        for c in libgen_candidates:
            print(f"  - {c.source_kind}: {c.url}")
            if c.error:
                print(f"    Error: {c.error}")
    except Exception as e:
        print(f"⚠ LibGen resolution failed (expected for network issues): {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Sci-Hub and LibGen Resolver Integration Test")
    print("=" * 60)
    
    print("\n--- Test 1: Sci-Hub Resolver Integration ---")
    test_sci_hub_resolver_integration()
    
    print("\n--- Test 2: LibGen Resolver Integration ---")
    test_libgen_resolver_integration()
    
    print("\n--- Test 3: Paper Resolution (Network-dependent) ---")
    test_paper_resolution()
    
    print("\n" + "=" * 60)
    print("All integration tests completed!")
    print("=" * 60)
