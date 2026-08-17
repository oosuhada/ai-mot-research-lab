"""Manual test script for Sci-Hub and LibGen adapter functions."""

import sys
sys.path.insert(0, '/Users/gabrieljang/Services/ai-mot-research-lab/apps/api/src')

from datetime import timezone

# Test SciHubResult conversion
def test_scihub_result_conversion():
    """Test SciHubResult → OpenAccessPdfCandidate conversion."""
    from research_lab.full_text_sources import convert_resolver_result_to_candidate
    
    # Mock SciHubResult with valid PDF URL
    class MockSciHubResult:
        pdf_url = "https://sci-hub.se/download/10.1038/s41586-020-2649-2"
        source_kind = "sci_hub_pdf"
        retrieved_at = None  # datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        doi = "10.1038/s41586-020-2649-2"
        domain_used = "sci-hub.se"
        error = None

    result = MockSciHubResult()
    candidate = convert_resolver_result_to_candidate(result)

    print("Test 1: Sci-Hub with valid PDF URL")
    if candidate is not None:
        print(f"  ✓ PASS - url: {candidate.url}")
        print(f"  ✓ source_kind: {candidate.source_kind}")
        print(f"  ✓ license: {candidate.license}")
        print(f"  ✓ source_record_id: {candidate.source_record_id}")
    else:
        print("  ✗ FAIL - candidate is None")


def test_scihub_result_without_pdf():
    """Test SciHubResult → OpenAccessPdfCandidate conversion without PDF URL."""
    from research_lab.full_text_sources import convert_resolver_result_to_candidate
    
    # Mock SciHubResult without PDF
    class MockSciHubResultNoPdf:
        pdf_url = None
        source_kind = "sci_hub_error"
        retrieved_at = None
        doi = "10.1038/s41586-020-2649-2"
        domain_used = "sci-hub.se"
        error = "PDF not found"

    result = MockSciHubResultNoPdf()
    candidate = convert_resolver_result_to_candidate(result)

    print("\nTest 2: Sci-Hub without PDF URL")
    if candidate is None:
        print("  ✓ PASS - candidate is None as expected")
    else:
        print(f"  ✗ FAIL - candidate should be None but got {candidate}")


def test_libgen_result_conversion():
    """Test LibGenResult → OpenAccessPdfCandidate conversion."""
    from research_lab.full_text_sources import convert_resolver_result_to_candidate
    
    # Mock LibGenResult
    class MockLibGenResult:
        pdf_url = "https://libgen.rs/download/book/123456"
        source_kind = "libgen_pdf"
        retrieved_at = None
        identifier = "123456"
        doi = None
        isbn = "978-0-123456-78-9"
        error = None

    result = MockLibGenResult()
    candidate = convert_resolver_result_to_candidate(result)

    print("\nTest 3: LibGen with valid PDF URL")
    if candidate is not None:
        print(f"  ✓ PASS - url: {candidate.url}")
        print(f"  ✓ source_kind: {candidate.source_kind}")
        print(f"  ✓ license: {candidate.license}")
        print(f"  ✓ source_record_id: {candidate.source_record_id}")
    else:
        print("  ✗ FAIL - candidate is None")


def test_libgen_result_without_pdf():
    """Test LibGenResult → OpenAccessPdfCandidate conversion without PDF URL."""
    from research_lab.full_text_sources import convert_resolver_result_to_candidate
    
    # Mock LibGenResult without PDF
    class MockLibGenResultNoPdf:
        pdf_url = None
        source_kind = "libgen_error"
        retrieved_at = None
        identifier = "123456"
        doi = None
        isbn = "978-0-123456-78-9"
        error = "File not found"

    result = MockLibGenResultNoPdf()
    candidate = convert_resolver_result_to_candidate(result)

    print("\nTest 4: LibGen without PDF URL")
    if candidate is None:
        print("  ✓ PASS - candidate is None as expected")
    else:
        print(f"  ✗ FAIL - candidate should be None but got {candidate}")


if __name__ == "__main__":
    print("=" * 70)
    print("Adapter Function Tests for Sci-Hub and LibGen Results")
    print("=" * 70)
    
    test_scihub_result_conversion()
    test_scihub_result_without_pdf()
    test_libgen_result_conversion()
    test_libgen_result_without_pdf()
    
    print("\n" + "=" * 70)
    print("All tests completed!")
    print("=" * 70)
