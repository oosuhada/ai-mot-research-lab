from research_lab.user_imports import parse_import


def test_parse_multiple_dois_normalizes_urls() -> None:
    rows = parse_import("doi", "https://doi.org/10.1000/XYZ\n10.2000/abc")
    assert [row.doi for row in rows] == ["10.1000/xyz", "10.2000/abc"]


def test_parse_bibtex_extracts_core_fields() -> None:
    rows = parse_import(
        "bibtex",
        """@article{demo,
          title={AI Capability and Firm Performance},
          author={Doe, Jane and Roe, John},
          year={2024},
          doi={10.1234/demo.1}
        }
        """,
    )
    assert len(rows) == 1
    assert rows[0].doi == "10.1234/demo.1"
    assert rows[0].publication_year == 2024
    assert rows[0].title == "AI Capability and Firm Performance"


def test_parse_ris_and_csv() -> None:
    ris = parse_import("ris", "TY  - JOUR\nTI  - Responsible AI Governance\nPY  - 2025\nDO  - 10.1/ris\nER  -")
    csv_rows = parse_import("csv", "title,doi,year\nAgentic Workflows,10.1/csv,2025\n")
    assert ris[0].title == "Responsible AI Governance"
    assert ris[0].publication_year == 2025
    assert csv_rows[0].title == "Agentic Workflows"
    assert csv_rows[0].publication_year == 2025


def test_parse_scopus_csv_preserves_institutional_metadata() -> None:
    rows = parse_import(
        "scopus_csv",
        """Authors,Title,Year,Source title,Cited by,DOI,Link,Affiliations,Author Keywords,Document Type,EID\nDoe J.; Roe J.,AI Strategy and Innovation,2026,Technovation,12,10.1234/scopus.1,https://www.scopus.com/record/display.uri?eid=2-s2.0-1234567890,SKKU,AI; strategy,Article,2-s2.0-1234567890\n""",
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.source == "scopus_export"
    assert row.scopus_eid == "2-s2.0-1234567890"
    assert row.scopus_id == "1234567890"
    assert row.doi == "10.1234/scopus.1"
    assert row.cited_by_count == 12
    assert row.source_title == "Technovation"
    assert row.affiliations == "SKKU"
