"""Adapters to convert external provider results to OpenAccessPdfCandidate."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from research_lab.full_text_sources import OpenAccessPdfCandidate


@dataclass
class SciHubAdapterResult:
    """Result from Sci-Hub adapter."""
    pdf_url: str | None
    source_kind: str = "sci_hub_adapter"
    retrieved_at: datetime | None = None
    domain_used: str | None = None
    error: str | None = None

    def to_open_access_candidate(self) -> OpenAccessPdfCandidate:
        """Convert to OpenAccessPdfCandidate."""
        return OpenAccessPdfCandidate(
            pdf_url=self.pdf_url or "",
            source_kind=self.source_kind,
            retrieved_at=self.retrieved_at or datetime.now(),
            metadata={
                "domain_used": self.domain_used,
                "error": self.error,
            },
        )


@dataclass
class LibGenAdapterResult:
    """Result from LibGen adapter."""
    pdf_url: str | None
    source_kind: str = "libgen_adapter"
    retrieved_at: datetime | None = None
    identifier: str | None = None
    error: str | None = None

    def to_open_access_candidate(self) -> OpenAccessPdfCandidate:
        """Convert to OpenAccessPdfCandidate."""
        return OpenAccessPdfCandidate(
            pdf_url=self.pdf_url or "",
            source_kind=self.source_kind,
            retrieved_at=self.retrieved_at or datetime.now(),
            metadata={
                "identifier": self.identifier,
                "error": self.error,
            },
        )


def convert_scihub_result_to_candidate(
    result: Any,
) -> OpenAccessPdfCandidate | None:
    """Convert SciHubResult to OpenAccessPdfCandidate.
    
    Args:
        result: SciHubResult from SciHubResolver
        
    Returns:
        OpenAccessPdfCandidate or None if no PDF URL found
    """
    if not hasattr(result, "pdf_url") or not result.pdf_url:
        return None
    
    return OpenAccessPdfCandidate(
        pdf_url=result.pdf_url,
        source_kind=getattr(result, "source_kind", "sci_hub_pdf"),
        retrieved_at=getattr(result, "retrieved_at", datetime.now()),
        metadata={
            "doi": getattr(result, "doi", None),
            "pmid": getattr(result, "pmid", None),
            "domain_used": getattr(result, "domain_used", None),
            "error": getattr(result, "error", None),
        },
    )


def convert_libgen_result_to_candidate(
    result: Any,
) -> OpenAccessPdfCandidate | None:
    """Convert LibGenResult to OpenAccessPdfCandidate.
    
    Args:
        result: LibGenResult from LibGenResolver
        
    Returns:
        OpenAccessPdfCandidate or None if no PDF URL found
    """
    if not hasattr(result, "pdf_url") or not result.pdf_url:
        return None
    
    return OpenAccessPdfCandidate(
        pdf_url=result.pdf_url,
        source_kind=getattr(result, "source_kind", "libgen_pdf"),
        retrieved_at=getattr(result, "retrieved_at", datetime.now()),
        metadata={
            "identifier": getattr(result, "identifier", None),
            "doi": getattr(result, "doi", None),
            "isbn": getattr(result, "isbn", None),
            "error": getattr(result, "error", None),
        },
    )
