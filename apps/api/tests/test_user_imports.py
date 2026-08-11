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
