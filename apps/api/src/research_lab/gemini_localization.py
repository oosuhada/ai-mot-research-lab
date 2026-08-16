from __future__ import annotations

import json
import math
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class GeminiPricing:
    input_usd_per_million_tokens: float = 0.75
    output_usd_per_million_tokens: float = 3.75


@dataclass(frozen=True, slots=True)
class GeminiBatchResult:
    entries: list[dict[str, object]]
    prompt_tokens: int
    output_tokens: int


class VertexGeminiLocalizationClient:
    """Operator-side Vertex AI translator for bootstrap localization.

    Authentication is intentionally ephemeral. The access token is read from
    GOOGLE_CLOUD_ACCESS_TOKEN or minted with the local gcloud CLI and is never
    persisted in artifacts or imported localization provenance.
    """

    def __init__(
        self,
        *,
        project_id: str,
        location: str = "global",
        model: str = "gemini-3.7-flash",
        timeout_seconds: float = 120.0,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._token_lock = threading.Lock()
        self._access_token = os.environ.get("GOOGLE_CLOUD_ACCESS_TOKEN") or self._mint_gcloud_token()

    def translate_batch(self, entries: list[dict[str, object]]) -> GeminiBatchResult:
        prompt = self._build_prompt(entries)
        max_output_tokens = self._max_output_tokens(entries)
        response = self._post(prompt, max_output_tokens=max_output_tokens)
        payload = response.json()
        candidates = payload.get("candidates") if isinstance(payload, dict) else None
        if not isinstance(candidates, list) or not candidates:
            raise TypeError("Vertex AI returned no translation candidate")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not isinstance(parts, list) or not parts or not isinstance(parts[0].get("text"), str):
            raise TypeError("Vertex AI returned an unexpected translation payload")
        translated = json.loads(parts[0]["text"])
        if not isinstance(translated, list):
            raise TypeError("Vertex AI translation result must be a JSON list")

        source_by_id = {str(entry["paper_id"]): entry for entry in entries}
        normalized: list[dict[str, object]] = []
        seen: set[str] = set()
        for item in translated:
            if not isinstance(item, dict):
                raise TypeError("Vertex AI translation item must be an object")
            paper_id = str(item.get("paper_id") or "")
            source = source_by_id.get(paper_id)
            if source is None or paper_id in seen:
                raise ValueError(f"Vertex AI returned an unknown or duplicate paper_id: {paper_id}")
            abstract = str(item.get("abstract_translated") or "").strip()
            if source.get("abstract") and not abstract:
                raise ValueError(f"Vertex AI omitted abstract translation for {paper_id}")
            if abstract and not any("가" <= char <= "힣" for char in abstract):
                raise ValueError(f"Vertex AI Korean translation contains no Hangul for {paper_id}")
            raw_keywords = item.get("keywords")
            keywords = [str(value).strip() for value in raw_keywords] if isinstance(raw_keywords, list) else []
            normalized.append(
                {
                    **source,
                    "title_translated": str(item.get("title_translated") or "").strip() or None,
                    "abstract_translated": abstract,
                    "keywords": [keyword for keyword in keywords if keyword],
                    "provider": "vertex_ai",
                    "model": self.model,
                }
            )
            seen.add(paper_id)
        if seen != set(source_by_id):
            missing = sorted(set(source_by_id) - seen)
            raise ValueError(f"Vertex AI omitted paper ids: {missing[:5]}")

        usage = payload.get("usageMetadata") if isinstance(payload, dict) else None
        prompt_tokens = int(usage.get("promptTokenCount") or 0) if isinstance(usage, dict) else 0
        output_tokens = int(usage.get("candidatesTokenCount") or 0) if isinstance(usage, dict) else 0
        return GeminiBatchResult(normalized, prompt_tokens, output_tokens)

    def conservative_request_cost(self, entries: list[dict[str, object]], pricing: GeminiPricing) -> float:
        # Bound output with maxOutputTokens and intentionally overestimate prompt tokens
        # at two tokens per source character. This reservation prevents concurrent
        # requests from collectively crossing the operator-set budget ceiling.
        source_chars = sum(_source_character_count(entry) for entry in entries)
        prompt_token_cap = max(2 * source_chars + 2_000, 2_000)
        output_token_cap = self._max_output_tokens(entries)
        return (
            prompt_token_cap * pricing.input_usd_per_million_tokens
            + output_token_cap * pricing.output_usd_per_million_tokens
        ) / 1_000_000

    def _post(self, prompt: str, *, max_output_tokens: int) -> httpx.Response:
        url = (
            "https://aiplatform.googleapis.com/v1/projects/"
            f"{self.project_id}/locations/{self.location}/publishers/google/models/"
            f"{self.model}:generateContent"
        )
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "thinkingConfig": {"thinkingLevel": "low"},
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "paper_id": {"type": "STRING"},
                            "title_translated": {"type": "STRING"},
                            "abstract_translated": {"type": "STRING"},
                            "keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
                        },
                        "required": [
                            "paper_id",
                            "title_translated",
                            "abstract_translated",
                            "keywords",
                        ],
                    },
                },
            },
        }
        for attempt in range(5):
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=self.timeout_seconds,
            )
            if response.status_code == 401 and attempt == 0:
                with self._token_lock:
                    self._access_token = self._mint_gcloud_token()
                continue
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 4:
                time.sleep(min(2**attempt, 8))
                continue
            response.raise_for_status()
            return response
        raise RuntimeError("Vertex AI translation retry loop exhausted")

    @staticmethod
    def _mint_gcloud_token() -> str:
        completed = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            check=True,
            capture_output=True,
            text=True,
        )
        token = completed.stdout.strip()
        if not token:
            raise RuntimeError("gcloud returned an empty access token")
        return token

    @staticmethod
    def _max_output_tokens(entries: list[dict[str, object]]) -> int:
        source_chars = sum(_source_character_count(entry) for entry in entries)
        return min(65_536, max(2_048, math.ceil(source_chars * 0.60)))

    @staticmethod
    def _build_prompt(entries: list[dict[str, object]]) -> str:
        compact = [
            {
                "paper_id": entry["paper_id"],
                "title": entry.get("title") or "",
                "abstract": entry.get("abstract") or "",
                "keywords": entry.get("keywords") or [],
            }
            for entry in entries
        ]
        return (
            "Translate the following academic paper metadata from English to Korean. "
            "Do not summarize, shorten, expand, critique, or add facts. Preserve equations, "
            "citation markers, abbreviations, product names, proper nouns, and technical terminology. "
            "Use natural Korean academic prose while keeping the original meaning. Return exactly one "
            "output object per paper_id, in the same order, using the required JSON schema.\n\n"
            + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        )


def translate_localization_export(
    input_path: Path,
    output_path: Path,
    ledger_path: Path,
    *,
    project_id: str,
    location: str = "global",
    model: str = "gemini-3.7-flash",
    budget_usd: float = 40.0,
    batch_size: int = 8,
    workers: int = 8,
    pricing: GeminiPricing | None = None,
) -> dict[str, object]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Gemini localization input must be a JSON list")
    entries = [entry for entry in payload if isinstance(entry, dict)]
    price = pricing or GeminiPricing()
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

    client = VertexGeminiLocalizationClient(project_id=project_id, location=location, model=model)
    batches = [entries[index : index + max(batch_size, 1)] for index in range(0, len(entries), max(batch_size, 1))]
    selected: list[list[dict[str, object]]] = []
    reserved = 0.0
    for batch in batches:
        request_cap = client.conservative_request_cost(batch, price)
        if reserved + request_cap > remaining_budget:
            break
        selected.append(batch)
        reserved += request_cap

    translated_entries: list[dict[str, object]] = []
    prompt_tokens = 0
    output_tokens = 0
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=max(workers, 1)) as pool:
        future_map = {pool.submit(client.translate_batch, batch): batch for batch in selected}
        for future in as_completed(future_map):
            batch = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                failures.append(f"{type(exc).__name__}: {exc}")
                continue
            translated_entries.extend(result.entries)
            prompt_tokens += result.prompt_tokens
            output_tokens += result.output_tokens

    order = {str(entry["paper_id"]): index for index, entry in enumerate(entries)}
    translated_entries.sort(key=lambda entry: order[str(entry["paper_id"])])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(translated_entries, indent=2, ensure_ascii=False), encoding="utf-8")

    actual_cost = (
        prompt_tokens * price.input_usd_per_million_tokens
        + output_tokens * price.output_usd_per_million_tokens
    ) / 1_000_000
    ledger.update(
        {
            "provider": "vertex_ai",
            "project_id": project_id,
            "model": model,
            "budget_usd": budget_usd,
            "estimated_spend_usd": round(spent_before + actual_cost, 6),
            "prompt_tokens": int(ledger.get("prompt_tokens") or 0) + prompt_tokens,
            "output_tokens": int(ledger.get("output_tokens") or 0) + output_tokens,
            "translated_records": int(ledger.get("translated_records") or 0) + len(translated_entries),
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
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "run_cost_usd": round(actual_cost, 6),
        "estimated_spend_usd": ledger["estimated_spend_usd"],
        "budget_usd": budget_usd,
        "output": str(output_path),
        "ledger": str(ledger_path),
    }


def _source_character_count(entry: dict[str, object]) -> int:
    keywords = entry.get("keywords")
    return (
        len(str(entry.get("title") or ""))
        + len(str(entry.get("abstract") or ""))
        + sum(len(str(keyword)) for keyword in keywords)
        if isinstance(keywords, list)
        else len(str(entry.get("title") or "")) + len(str(entry.get("abstract") or ""))
    )


def _read_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Gemini localization ledger must be a JSON object")
    return payload
