"""LibGen (Library Genesis) resolver for accessing papers from their database."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from research_lab.config import Settings

logger = logging.getLogger(__name__)

# LibGen endpoints
LIBGEN_API_BASE = "http://libgen.rs"
LIBGEN_ADRESSES = [
    "http://libgen.rs",
    "http://libgen.is",  # Alternative mirror
]


@dataclass
class LibGenResult:
    """Result from LibGen resolution."""
    pdf_url: str | None
    title: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    identifier: str | None = None  # MD5, ISBN, etc.
    source_kind: str = "libgen_pdf"
    retrieved_at: datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pdf_url": self.pdf_url,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "identifier": self.identifier,
            "source_kind": self.source_kind,
            "retrieved_at": self.retrieved_at.isoformat() if self.retrieved_at else None,
            "error": self.error,
        }


class LibGenResolver:
    """
    Resolver for LibGen (Library Genesis).
    
    Uses the libgen.rs API to search for papers by DOI, ISBN, or MD5 hash.
    Note: LibGen does not provide official public APIs; this uses unofficial endpoints.
    """

    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={
                "User-Agent": "ai-mot-research-lab/0.1 (+https://github.com/your-org/ai-mot-research-lab)",
                "Accept": "application/json, text/html",
            },
        )
        self.base_url = LIBGEN_API_BASE

    def resolve_by_doi(self, doi: str) -> LibGenResult:
        """
        Resolve a DOI to a PDF URL via LibGen.
        
        Args:
            doi: The DOI to search for
            
        Returns:
            LibGenResult with pdf_url or error information
        """
        return self._search_and_resolve(doi, identifier_type="doi")

    def resolve_by_isbn(self, isbn: str) -> LibGenResult:
        """
        Resolve an ISBN to a PDF URL via LibGen.
        
        Args:
            isbn: The ISBN to search for
            
        Returns:
            LibGenResult with pdf_url or error information
        """
        return self._search_and_resolve(isbn, identifier_type="isbn")

    def resolve_by_md5(self, md5: str) -> LibGenResult:
        """
        Resolve an MD5 hash directly to a PDF URL.
        
        This is the most reliable method if you already have the MD5.
        
        Args:
            md5: The MD5 hash of the file
            
        Returns:
            LibGenResult with pdf_url or error information
        """
        result = self._fetch_by_md5(md5)
        if result.pdf_url:
            return result
        
        # Fallback to search by MD5 as identifier
        return self._search_and_resolve(md5, identifier_type="md5")

    def _search_and_resolve(
        self, identifier: str, identifier_type: str = "doi"
    ) -> LibGenResult:
        """Search LibGen for an identifier and resolve to PDF."""
        # Search endpoint format varies by identifier type
        search_endpoint = f"{self.base_url}/search.php"
        
        params = {
            "req": identifier,
            "view": "simple",
            "res": 25,  # Return up to 25 results
        }
        
        try:
            response = self.client.get(search_endpoint, params=params)
            
            if response.status_code != 200:
                return LibGenResult(
                    pdf_url=None,
                    identifier=identifier,
                    source_kind="libgen_pdf",
                    retrieved_at=datetime.now(),
                    error=f"Search failed with HTTP {response.status_code}",
                )
            
            # Parse search results to find MD5
            md5 = self._extract_md5_from_search(response.text, identifier)
            
            if md5:
                return self.resolve_by_md5(md5)
            else:
                return LibGenResult(
                    pdf_url=None,
                    identifier=identifier,
                    source_kind="libgen_pdf",
                    retrieved_at=datetime.now(),
                    error=f"No matching entry found for {identifier_type}: {identifier}",
                )
                
        except httpx.RequestError as e:
            # Retry with exponential backoff (max 2 attempts, faster for testing)
            last_error = str(e)
            for attempt in range(2):
                wait_time = 0.5 * (attempt + 1)  # 0.5s, 1s
                logger.warning(f"LibGen request failed on attempt {attempt + 1}, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
                
                try:
                    response = self.client.get(search_endpoint, params=params)
                    
                    if response.status_code == 200:
                        md5 = self._extract_md5_from_search(response.text, identifier)
                        if md5:
                            return self.resolve_by_md5(md5)
                        else:
                            return LibGenResult(
                                pdf_url=None,
                                identifier=identifier,
                                source_kind="libgen_pdf",
                                retrieved_at=datetime.now(),
                                error=f"No matching entry found for {identifier_type}: {identifier} after retry",
                            )
                    else:
                        last_error = f"HTTP {response.status_code}"
                except httpx.RequestError as retry_e:
                    last_error = str(retry_e)
            
            # All retries failed - record as timeout
            return LibGenResult(
                pdf_url=None,
                identifier=identifier,
                source_kind="libgen_timeout",
                retrieved_at=datetime.now(),
                error=f"LibGen timeout after 2 attempts: {last_error}",
            )

    def _fetch_by_md5(self, md5: str) -> LibGenResult:
        """Fetch paper metadata directly by MD5 hash."""
        # Direct download URL pattern
        # Format: http://libgen.rs/ads.php?md5={MD5} or http://libgen.rs/full.php?md5={MD5}
        
        urls_to_try = [
            f"{self.base_url}/full.php?md5={md5}",
            f"{self.base_url}/ads.php?md5={md5}",
        ]
        
        for url in urls_to_try:
            try:
                response = self.client.get(url, follow_redirects=True)
                
                if response.status_code == 200:
                    # Extract PDF URL from the page
                    pdf_url = self._extract_pdf_from_libgen_page(response.text)
                    
                    if pdf_url:
                        return LibGenResult(
                            pdf_url=pdf_url,
                            identifier=md5,
                            source_kind="libgen_pdf",
                            retrieved_at=datetime.now(),
                        )
            except httpx.RequestError:
                continue
        
        return LibGenResult(
            pdf_url=None,
            identifier=md5,
            source_kind="libgen_pdf",
            retrieved_at=datetime.now(),
            error=f"Failed to fetch by MD5: {md5}",
        )

    def _extract_md5_from_search(self, html: str, identifier: str) -> str | None:
        """Extract MD5 hash from search results HTML."""
        import re
        
        # Look for MD5 in various formats in the search results
        patterns = [
            r'md5=([a-fA-F0-9]{32})',
            r'[\'"]md5[\'"]\s*:\s*[\'"]([a-fA-F0-9]{32})[\'"]',
            rf'{re.escape(identifier)}.*?md5=([a-fA-F0-9]{{32}})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        
        return None

    def _extract_pdf_from_libgen_page(self, html: str) -> str | None:
        """Extract PDF download URL from LibGen page."""
        import re
        from urllib.parse import urljoin
        
        # Look for direct PDF links
        patterns = [
            r'href=["\']([^"\']*\.pdf)["\']',
            r'document\.location\s*=\s*["\']([^"\']*\.pdf)["\']',
            r'url\s*:\s*["\']([^"\']*\.pdf)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                url = match.group(1)
                if not url.startswith("http"):
                    url = urljoin(self.base_url, url)
                return url
        
        # Try to find download button
        import html
        soup_html = html.unescape(html)
        download_patterns = [
            r'href=["\']([^"\']*download\.php[^"\']*)["\']',
            r'href=["\']([^"\']*ads\.php[^"\']*)["\']',
        ]
        
        for pattern in download_patterns:
            match = re.search(pattern, soup_html)
            if match:
                url = match.group(1)
                if not url.startswith("http"):
                    url = urljoin(self.base_url, url)
                return url
        
        return None

    def close(self) -> None:
        """Close the HTTP client."""
        if self._owns_client:
            self.client.close()
