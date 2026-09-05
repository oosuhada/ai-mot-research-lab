from datetime import date

from research_lab.patent_imports import parse_wips_csv


def test_parse_wips_csv_with_korean_headers() -> None:
    rows = parse_wips_csv(
        """국가,출원번호,공개번호,발명의 명칭,요약,출원일,공개일,출원인,발명자,IPC,CPC,법적상태\nKR,10-2025-0012345,KR20260012345A,생성형 AI 기반 기술경영 분석 시스템,기술 정보를 분석한다,2025.02.03,2026.01.15,성균관대학교;테스트기업,홍길동;김연구,G06F 40/30;G06Q 10/06,G06F40/30,공개\n"""
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.jurisdiction == "KR"
    assert row.application_number == "10-2025-0012345"
    assert row.publication_number == "KR20260012345A"
    assert row.title == "생성형 AI 기반 기술경영 분석 시스템"
    assert row.filing_date == date(2025, 2, 3)
    assert row.publication_date == date(2026, 1, 15)
    assert row.applicants == ["성균관대학교", "테스트기업"]
    assert row.inventors == ["홍길동", "김연구"]
    assert row.ipc_codes == ["G06F 40/30", "G06Q 10/06"]


def test_parse_wips_csv_with_english_headers_and_jurisdiction_inference() -> None:
    rows = parse_wips_csv(
        """Publication Number,Title,Filing Date,Applicant,Inventor,IPC,Legal Status\nUS20260123456A1,AI patent intelligence,2025-03-04,Example Corp,Jane Doe,G06F 16/00,Pending\n"""
    )
    row = rows[0]
    assert row.jurisdiction == "US"
    assert row.publication_number == "US20260123456A1"
    assert row.filing_date == date(2025, 3, 4)
    assert row.legal_status == "Pending"
