"""Resolver implementations for various paper sources."""
from research_lab.resolvers.adapters import (
    convert_libgen_result_to_candidate,
    convert_scihub_result_to_candidate,
)
from research_lab.resolvers.libgen import LibGenResolver
from research_lab.resolvers.sci_hub import SciHubResolver

__all__ = [
    "LibGenResolver",
    "SciHubResolver",
    "convert_libgen_result_to_candidate",
    "convert_scihub_result_to_candidate",
]
