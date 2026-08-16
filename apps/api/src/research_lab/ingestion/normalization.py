from __future__ import annotations

import re
import unicodedata

DOI_PREFIX_PATTERN = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
ARXIV_PREFIX_PATTERN = re.compile(r"^(?:https?://arxiv\.org/(?:abs|pdf)/|arxiv:\s*)", re.IGNORECASE)
ARXIV_VERSION_PATTERN = re.compile(r"v\d+$", re.IGNORECASE)


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    normalized = DOI_PREFIX_PATTERN.sub("", value.strip()).strip().lower()
    return normalized or None


def normalize_openalex_id(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().rstrip("/")
    if normalized.startswith("https://openalex.org/"):
        return normalized.rsplit("/", 1)[-1]
    return normalized


def normalize_arxiv_id(value: str | None) -> str | None:
    if not value:
        return None
    normalized = ARXIV_PREFIX_PATTERN.sub("", value.strip()).strip()
    if normalized.lower().endswith(".pdf"):
        normalized = normalized[:-4]
    normalized = ARXIV_VERSION_PATTERN.sub("", normalized)
    return normalized or None


def normalize_orcid(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().rstrip("/")
    if normalized.startswith("https://orcid.org/"):
        return normalized.rsplit("/", 1)[-1]
    return normalized or None


def normalize_ror(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().rstrip("/")
    if normalized.startswith("https://ror.org/"):
        return normalized.rsplit("/", 1)[-1]
    return normalized or None


def normalize_title_for_fallback(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return " ".join(re.findall(r"[a-z0-9]+", normalized))

