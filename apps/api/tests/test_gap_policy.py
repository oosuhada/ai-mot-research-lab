from collections import Counter

from research_lab.gap_analysis import (
    _candidate_methods,
    _candidate_theoretical_lenses,
    _coverage_signal,
)


def test_gap_coverage_is_labeled_as_candidate_signal() -> None:
    text = _coverage_signal(Counter({"Governance": 2, "Adoption": 8}), 10)

    assert "Candidate coverage signal only" in text
    assert "not itself a research gap" in text


def test_gap_recommendations_are_explicitly_candidates() -> None:
    lenses = _candidate_theoretical_lenses("AI adoption and firm performance")
    methods = _candidate_methods("AI adoption and firm performance")

    assert lenses.startswith("Candidate lenses to evaluate")
    assert methods.startswith("Candidate methods")
