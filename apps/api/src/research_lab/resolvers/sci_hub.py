"""Sci-Hub (including sci-hub.kr and other mirrors) resolver."""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from research_lab.config import Settings

logger = logging.getLogger(__name__)

# Known Sci-Hub mirrors (active as of 2026)
# These domains are rotated to avoid blocking
SCI_HUB_DOMAINS = [
    "https://sci-hub.kr",
    "https://sci-hub.se",
    "https://sci-hub.st",
    "https://sci-hub.ru",
    "https://sci-hub.shop",
    "https://sci-hub.name",
    "https://sci-hub.wf",
]


@dataclass
class SciHubResult:
    """Result from Sci-Hub resolution."""
    pdf_url: str | None
    doi: str | None = None
    pmid: str | None = None
    source_kind: str = "sci_hub_pdf"
    retrieved_at: datetime | None = None
    domain_used: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pdf_url": self.pdf_url,
            "doi": self.doi,
            "pmid": self.pmid,
            "source_kind": self.source_kind,
            "retrieved_at": self.retrieved_at.isoformat() if self.retrieved_at else None,
            "domain_used": self.domain_used,
            "error": self.error,
        }


class SciHubResolver:
    """
    Resolver for Sci-Hub and its mirror sites.
    
    Uses direct URL construction pattern: https://sci-hub.{tld}/{DOI}
    Falls back to multiple domains when one is blocked.
    """

    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] = lambda x: __import__("time").sleep(x),
    ) -> None:
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={
                "User-Agent": "ai-mot-research-lab/0.1 (+https://github.com/your-org/ai-mot-research-lab)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        self.sleeper = sleeper
        self._last_request_at: float = 0.0
        self._request_interval = 3.0  # Minimum seconds between requests to avoid rate limiting

    def _get_next_domain(self, current_domain: str | None) -> str:
        """Get next domain in rotation, avoiding duplicates."""
        if current_domain is None:
            return SCI_HUB_DOMAINS[0]
        
        try:
            idx = SCI_HUB_DOMAINS.index(current_domain)
            next_idx = (idx + 1) % len(SCI_HUB_DOMAINS)
            return SCI_HUB_DOMAINS[next_idx]
        except ValueError:
            return SCI_HUB_DOMAINS[0]

    def resolve(self, identifier: str, *, identifier_type: str = "doi") -> SciHubResult:
        """
        Resolve a DOI/PMID to a PDF URL via Sci-Hub.
        
        Args:
            identifier: The DOI, PMID, or URL to resolve
            identifier_type: One of 'doi', 'pmid', 'url'
            
        Returns:
            SciHubResult with pdf_url or error information
        """
        # Rate limiting
        elapsed = datetime.now().timestamp() - self._last_request_at
        if elapsed < self._request_interval:
            self.sleeper(self._request_interval - elapsed)
        
        domain = None
        last_error = None
        
        for attempt in range(len(SCI_HUB_DOMAINS)):
            domain = self._get_next_domain(domain)
            
            try:
                result = self._try_resolve_with_domain(identifier, identifier_type, domain)
                if result.pdf_url:
                    logger.info(f"Successfully resolved {identifier} via {domain}")
                    return result
                elif result.error:
                    last_error = result.error
                    logger.warning(f"Domain {domain} failed for {identifier}: {result.error}")
            except httpx.RequestError as e:
                last_error = str(e)
                logger.warning(f"Network error on domain {domain}: {e}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Unexpected error on domain {domain}: {e}")

        # Determine final source_kind based on last error
        final_source_kind = "sci_hub_captcha_detected" if last_error and "captcha" in last_error.lower() else "sci_hub_pdf"
        
        return SciHubResult(
            pdf_url=None,
            doi=identifier if identifier_type == "doi" else None,
            pmid=identifier if identifier_type == "pmid" else None,
            source_kind=final_source_kind,
            retrieved_at=datetime.now(),
            error=f"All domains failed: {last_error}",
        )

    def _try_resolve_with_domain(
        self, identifier: str, identifier_type: str, domain: str
    ) -> SciHubResult:
        """Try to resolve identifier using a specific Sci-Hub domain."""
        # Construct URL based on identifier type
        if identifier_type == "doi":
            target_url = f"{domain}/{identifier}"
        elif identifier_type == "pmid":
            target_url = f"{domain}/{identifier}"
        elif identifier_type == "url":
            target_url = f"{domain}/{identifier}"
        else:
            return SciHubResult(
                pdf_url=None,
                doi=identifier if identifier_type == "doi" else None,
                pmid=identifier if identifier_type == "pmid" else None,
                source_kind="sci_hub_pdf",
                retrieved_at=datetime.now(),
                domain_used=domain,
                error=f"Unknown identifier type: {identifier_type}",
            )

        try:
            response = self.client.get(target_url, follow_redirects=True)
            
            # Check for CAPTCHA or blocking
            if "captcha" in response.text.lower():
                return SciHubResult(
                    pdf_url=None,
                    doi=identifier if identifier_type == "doi" else None,
                    pmid=identifier if identifier_type == "pmid" else None,
                    source_kind="sci_hub_pdf",
                    retrieved_at=datetime.now(),
                    domain_used=domain,
                    error="CAPTCHA detected - manual intervention required",
                )

            # Check for access denied
            if "denied" in response.text.lower() or response.status_code == 403:
                return SciHubResult(
                    pdf_url=None,
                    doi=identifier if identifier_type == "doi" else None,
                    pmid=identifier if identifier_type == "pmid" else None,
                    source_kind="sci_hub_pdf",
                    retrieved_at=datetime.now(),
                    domain_used=domain,
                    error=f"Access denied (HTTP {response.status_code})",
                )

            # Parse HTML to find PDF link
            pdf_url = self._extract_pdf_url(response.text, domain)
            
            if pdf_url:
                return SciHubResult(
                    pdf_url=pdf_url,
                    doi=identifier if identifier_type == "doi" else None,
                    pmid=identifier if identifier_type == "pmid" else None,
                    source_kind="sci_hub_pdf",
                    retrieved_at=datetime.now(),
                    domain_used=domain,
                )
            else:
                return SciHubResult(
                    pdf_url=None,
                    doi=identifier if identifier_type == "doi" else None,
                    pmid=identifier if identifier_type == "pmid" else None,
                    source_kind="sci_hub_pdf",
                    retrieved_at=datetime.now(),
                    domain_used=domain,
                    error="No PDF URL found in response",
                )

        except httpx.TimeoutException:
            return SciHubResult(
                pdf_url=None,
                doi=identifier if identifier_type == "doi" else None,
                pmid=identifier if identifier_type == "pmid" else None,
                source_kind="sci_hub_pdf",
                retrieved_at=datetime.now(),
                domain_used=domain,
                error="Request timeout",
            )

    def _extract_pdf_url(self, html: str, base_domain: str) -> str | None:
        """Extract PDF download URL from Sci-Hub HTML page."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Method 1: Look for iframe with src pointing to PDF
        iframe = soup.find("iframe", src=True)
        if iframe and iframe["src"]:
            pdf_url = urljoin(base_domain, iframe["src"])
            if pdf_url.endswith(".pdf"):
                return pdf_url
        
        # Method 2: Look for embed tag with src
        embed = soup.find("embed", src=True)
        if embed and embed["src"]:
            pdf_url = urljoin(base_domain, embed["src"])
            if pdf_url.endswith(".pdf"):
                return pdf_url
        
        # Method 3: Look for download link button
        download_button = soup.find(
            "button",
            {"id": re.compile(r"btn.*download", re.I)},
        )
        if download_button:
            onclick = download_button.get("onclick", "")
            match = re.search(r"url\s*=\s*['\"]([^'\"]+)['\"]", onclick)
            if match:
                return urljoin(base_domain, match.group(1))
        
        # Method 4: Look for any link ending in .pdf
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.endswith(".pdf"):
                pdf_url = urljoin(base_domain, href)
                return pdf_url
        
        # Method 5: Search for PDF URL in JavaScript
        script_tag = soup.find("script", string=re.compile(r"location\.href.*\.pdf", re.I))
        if script_tag:
            match = re.search(r"['\"]([^'\"]+\.pdf)['\"]", script_tag.string)
            if match:
                return urljoin(base_domain, match.group(1))

        return None

    def close(self) -> None:
        """Close the HTTP client."""
        if self._owns_client:
            self.client.close()
