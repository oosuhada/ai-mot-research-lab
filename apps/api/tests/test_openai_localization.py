from __future__ import annotations

import json
from pathlib import Path

from research_lab import openai_localization
from research_lab.openai_localization import OpenAIBatchResult, translate_localization_export_openai


class _FakeOpenAIClient:
    def __init__(self, **_: object) -> None:
        pass

    def conservative_request_cost(self, entries: list[dict[str, object]], pricing: object) -> float:
        del entries, pricing
        return 0.01

    def translate_batch(self, entries: list[dict[str, object]]) -> OpenAIBatchResult:
        translated = [
            {
                **entry,
                "title_translated": f"한국어 {entry['title']}",
                "abstract_translated": f"한국어 {entry['abstract']}",
                "keywords": ["인공지능"],
                "provider": "openai",
                "model": "gpt-5.6-luna",
            }
            for entry in entries
        ]
        return OpenAIBatchResult(translated, input_tokens=100, output_tokens=120)


def _entry(index: int) -> dict[str, object]:
    return {
        "paper_id": f"paper-{index}",
        "locale": "ko",
        "title": f"Title {index}",
        "abstract": f"Abstract {index}",
        "keywords": ["AI"],
        "source_hash": f"hash-{index}",
    }


def test_openai_export_translation_respects_reserved_budget(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    monkeypatch.setattr(  # type: ignore[attr-defined]
        openai_localization,
        "OpenAILocalizationClient",
        _FakeOpenAIClient,
    )
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    ledger_path = tmp_path / "ledger.json"
    input_path.write_text(json.dumps([_entry(1), _entry(2)]), encoding="utf-8")

    result = translate_localization_export_openai(
        input_path,
        output_path,
        ledger_path,
        api_key="test-key",
        budget_usd=0.015,
        batch_size=1,
        workers=2,
    )

    translated = json.loads(output_path.read_text(encoding="utf-8"))
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert result["status"] == "budget_limited"
    assert result["selected_records"] == 1
    assert len(translated) == 1
    assert translated[0]["provider"] == "openai"
    assert ledger["translated_records"] == 1
    assert float(ledger["estimated_spend_usd"]) < 0.015


def test_response_output_text_extracts_structured_response() -> None:
    payload = {
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"translations":[]}',
                    }
                ],
            }
        ]
    }
    assert openai_localization._response_output_text(payload) == '{"translations":[]}'
