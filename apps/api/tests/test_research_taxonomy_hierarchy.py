from research_lab.taxonomy import RESEARCH_AXES, RESEARCH_SUBAXES, infer_subaxis_labels


def test_every_research_axis_has_a_drillable_child_taxonomy() -> None:
    direct_parent_slugs = {
        subaxis.parent_slug
        for subaxis in RESEARCH_SUBAXES
        if subaxis.parent_slug in {axis.slug for axis in RESEARCH_AXES}
    }

    assert direct_parent_slugs == {axis.slug for axis in RESEARCH_AXES}


def test_large_adoption_subareas_have_a_third_level() -> None:
    third_level_parents = {
        subaxis.parent_slug
        for subaxis in RESEARCH_SUBAXES
        if subaxis.parent_slug not in {axis.slug for axis in RESEARCH_AXES}
    }

    assert {
        "scaling-implementation",
        "workflow-transformation",
        "productivity-performance",
        "workforce-human-ai",
        "adoption-determinants",
    }.issubset(third_level_parents)

    assert {
        "governance-trust-explainability",
        "governance-regulation-compliance",
        "governance-fairness-ethics",
        "org-decision-making",
        "agentic-multi-agent-coordination",
        "industrial-digital-twin",
        "industrial-predictive-maintenance",
    }.issubset(third_level_parents)


def test_hierarchical_inference_requires_the_parent_chain() -> None:
    text = "AI implementation work studies the pilot-to-production transition and enterprise integration."

    adoption_labels = infer_subaxis_labels(text, axis_slugs={"ai-adoption-business-value"})
    governance_labels = infer_subaxis_labels(text, axis_slugs={"ai-governance-responsible-deployment"})

    assert "scaling-implementation" in adoption_labels
    assert "implementation-pilot-production" in adoption_labels
    assert "implementation-integration" in adoption_labels
    assert "scaling-implementation" not in governance_labels
    assert "implementation-pilot-production" not in governance_labels


def test_other_top_level_axes_receive_their_own_children() -> None:
    organization_labels = infer_subaxis_labels(
        "AI changes decision making, team coordination, and knowledge work in organizations.",
        axis_slugs={"ai-organizational-change"},
    )
    industrial_labels = infer_subaxis_labels(
        "Machine learning supports predictive maintenance and digital twin systems in manufacturing.",
        axis_slugs={"industrial-ai-smart-operations"},
    )

    assert "org-decision-making" in organization_labels
    assert "org-teams-coordination" in organization_labels
    assert "org-knowledge-work" in organization_labels
    assert "industrial-predictive-maintenance" in industrial_labels
    assert "industrial-digital-twin" in industrial_labels
