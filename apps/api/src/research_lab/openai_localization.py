from __future__ import annotations

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class OpenAIPricing:
    # GPT-5.6 Luna list pricing as of 2026-09. Kept explicit in the ledger so
    # accounting remains auditable if pricing changes later.
    input_usd_per_million_tokens: float = 0.20
    output_usd_per_million_tokens: float = 1.20


@dataclass(frozen=True, slots=True)
class OpenAIBatchResult:
    entries: list[dict[str, object]]
    input_tokens: int
    output_tokens: int


class OpenAILocalizationClient:
    """High-throughput Korean academic-metadata translator using Responses API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-5.6-luna",
        timeout_seconds: float = 120.0,
    ) -> None:
        if not api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI localization")
        self.api_key = api_key.strip()
        self.model = model
        self.timeout_seconds = timeout_seconds

    def translate_batch(self, entries: list[dict[str, object]]) -> OpenAIBatchResult:
        response = self._post(entries)
        payload = response.json()
        text = _response_output_text(payload)
        parsed = json.loads(text)
        translations = parsed.get("translations") if isinstance(parsed, dict) else None
        if not isinstance(translations, list):
            raise TypeError("OpenAI translation result must contain a translations array")

        source_by_id = {str(entry["paper_id"]): entry for entry in entries}
        normalized: list[dict[str, object]] = []
        seen: set[str] = set()
        for item in translations:
            if not isinstance(item, dict):
                raise TypeError("OpenAI translation item must be an object")
            paper_id = str(item.get("paper_id") or "")
            source = source_by_id.get(paper_id)
            if source is None or paper_id in seen:
                raise ValueError(f"OpenAI returned an unknown or duplicate paper_id: {paper_id}")
            abstract = str(item.get("abstract_translated") or "").strip()
            if source.get("abstract") and not abstract:
                raise ValueError(f"OpenAI omitted abstract translation for {paper_id}")
            if abstract and not any("가" <= char <= "힣" for char in abstract):
                raise ValueError(f"OpenAI Korean translation contains no Hangul for {paper_id}")
            raw_keywords = item.get("keywords")
            keywords = [str(value).strip() for value in raw_keywords] if isinstance(raw_keywords, list) else []
            normalized.append(
                {
                    **source,
                    "title_translated": str(item.get("title_translated") or "").strip() or None,
                    "abstract_translated": abstract,
                    "keywords": [keyword for keyword in keywords if keyword],
                    "provider": "openai",
                    "model": self.model,
                }
            )
            seen.add(paper_id)
        if seen != set(source_by_id):
            missing = sorted(set(source_by_id) - seen)
            raise ValueError(f"OpenAI omitted paper ids: {missing[:5]}")

        usage = payload.get("usage") if isinstance(payload, dict) else None
        input_tokens = int(usage.get("input_tokens") or 0) if isinstance(usage, dict) else 0
        output_tokens = int(usage.get("output_tokens") or 0) if isinstance(usage, dict) else 0
        return OpenAIBatchResult(normalized, input_tokens, output_tokens)

    def conservative_request_cost(self, entries: list[dict[str, object]], pricing: OpenAIPricing) -> float:
        source_chars = sum(_source_character_count(entry) for entry in entries)
        input_token_cap = max(math.ceil(source_chars * 0.75) + 2_500, 2_500)
        output_token_cap = self._max_output_tokens(entries)
        return (
            input_token_cap * pricing.input_usd_per_million_tokens
            + output_token_cap * pricing.output_usd_per_million_tokens
        ) / 1_000_000

    def _post(self, entries: list[dict[str, object]]) -> httpx.Response:
        source_chars = sum(_source_character_count(entry) for entry in entries)
        body = {
            "model": self.model,
            "reasoning": {"effort": "none"},
            "instructions": (
                "Translate academic paper metadata from English to Korean. Do not summarize, shorten, "
                "expand, critique, or add facts. Preserve equations, citation markers, abbreviations, "
                "proper nouns, product names, and technical terminology. Use natural Korean academic prose."
            ),
            "input": json.dumps(
                [
                    {
                        "paper_id": entry["paper_id"],
                        "title": entry.get("title") or "",
                        "abstract": entry.get("abstract") or "",
                        "keywords": entry.get("keywords") or [],
                    }
                    for entry in entries
                ],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "max_output_tokens": self._max_output_tokens(entries),
            "text": {
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": "korean_localizations",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "translations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "paper_id": {"type": "string"},
                                        "title_translated": {"type": "string"},
                                        "abstract_translated": {"type": "string"},
                                        "keywords": {"type": "array", "items": {"type": "string"}},
                                    },
                                    "required": [
                                        "paper_id",
                                        "title_translated",
                                        "abstract_translated",
                                        "keywords",
                                    ],
                                },
                            }
                        },
                        "required": ["translations"],
                    },
                },
            },
            "metadata": {"purpose": "private_academic_korean_localization"},
            "store": False,
        }
        # Avoid absurd output reservations for unusually long abstracts.
        body["max_output_tokens"] = min(int(body["max_output_tokens"]), max(4_096, math.ceil(source_chars * 0.9)))

        last_error: Exception | None = None
        for attempt in range(6):
            try:
                response = httpx.post(
                    "https://api.openai.com/v1/responses",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                last_error = exc
                if attempt < 5:
                    time.sleep(min(2**attempt, 15))
                    continue
                raise
            if response.status_code in {408, 409, 429, 500, 502, 503, 504} and attempt < 5:
                retry_after = response.headers.get("retry-after")
                try:
                    wait = float(retry_after) if retry_after else min(2**attempt, 15)
                except ValueError:
                    wait = min(2**attempt, 15)
                time.sleep(max(wait, 0.5))
                continue
            response.raise_for_status()
            return response
        raise RuntimeError(f"OpenAI translation retry loop exhausted: {last_error}")

    @staticmethod
    def _max_output_tokens(entries: list[dict[str, object]]) -> int:
        source_chars = sum(_source_character_count(entry) for entry in entries)
        return min(65_536, max(4_096, math.ceil(source_chars * 0.85)))


def translate_localization_export_openai(
    input_path: Path,
    output_path: Path,
    ledger_path: Path,
    *,
    api_key: str,
    model: str = "gpt-5.6-luna",
    budget_usd: float = 200.0,
    batch_size: int = 8,
    workers: int = 8,
    pricing: OpenAIPricing | None = None,
) -> dict[str, object]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("OpenAI localization input must be a JSON list")
    entries = [entry for entry in payload if isinstance(entry, dict)]
    price = pricing or OpenAIPricing()
    ledger = _read_ledger(ledger_path)
    spent_before = float(ledger.get("estimated_spend_usd") or 0.0)
    remaining_budget = max(budget_usd - spent_before, 0.0)
    if remaining_budget <= 0:
        return {
            "status": "budget_exhausted",
            "translated": 0,
            "input_records": len(entries),
            "estimated_spend_usd": spent_before,
            "budget_usd": budget_usd,
        }

    client = OpenAILocalizationClient(api_key=api_key, model=model)
    size = max(batch_size, 1)
    batches = [entries[index : index + size] for index in range(0, len(entries), size)]
    selected: list[list[dict[str, object]]] = []
    reserved = 0.0
    for batch in batches:
        request_cap = client.conservative_request_cost(batch, price)
        if reserved + request_cap > remaining_budget:
            break
        selected.append(batch)
        reserved += request_cap

    translated_entries: list[dict[str, object]] = []
    input_tokens = 0
    output_tokens = 0
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=max(workers, 1)) as pool:
        future_map = {pool.submit(client.translate_batch, batch): batch for batch in selected}
        for future in as_completed(future_map):
            try:
                result = future.result()
            except Exception as exc:
                failures.append(f"{type(exc).__name__}: {exc}")
                continue
            translated_entries.extend(result.entries)
            input_tokens += result.input_tokens
            output_tokens += result.output_tokens

    order = {str(entry["paper_id"]): index for index, entry in enumerate(entries)}
    translated_entries.sort(key=lambda entry: order[str(entry["paper_id"])])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(translated_entries, indent=2, ensure_ascii=False), encoding="utf-8")

    actual_cost = (
        input_tokens * price.input_usd_per_million_tokens
        + output_tokens * price.output_usd_per_million_tokens
    ) / 1_000_000
    ledger.update(
        {
            "provider": "openai",
            "model": model,
            "budget_usd": budget_usd,
            "estimated_spend_usd": round(spent_before + actual_cost, 6),
            "input_tokens": int(ledger.get("input_tokens") or 0) + input_tokens,
            "output_tokens": int(ledger.get("output_tokens") or 0) + output_tokens,
            "translated_records": int(ledger.get("translated_records") or 0) + len(translated_entries),
            "pricing_input_usd_per_million_tokens": price.input_usd_per_million_tokens,
            "pricing_output_usd_per_million_tokens": price.output_usd_per_million_tokens,
        }
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "status": "completed" if len(selected) == len(batches) else "budget_limited",
        "input_records": len(entries),
        "selected_records": sum(len(batch) for batch in selected),
        "translated": len(translated_entries),
        "failed_batches": len(failures),
        "first_failure": failures[0] if failures else None,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "run_cost_usd": round(actual_cost, 6),
        "estimated_spend_usd": ledger["estimated_spend_usd"],
        "budget_usd": budget_usd,
        "output": str(output_path),
        "ledger": str(ledger_path),
    }


def _response_output_text(payload: dict[str, Any]) -> str:
    for item in payload.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    return text
    raise TypeError("OpenAI Responses API returned no output_text")


def _source_character_count(entry: dict[str, object]) -> int:
    keywords = entry.get("keywords")
    keyword_chars = sum(len(str(keyword)) for keyword in keywords) if isinstance(keywords, list) else 0
    return len(str(entry.get("title") or "")) + len(str(entry.get("abstract") or "")) + keyword_chars


def _read_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("OpenAI localization ledger must be a JSON object")
    return payload
