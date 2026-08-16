from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.corpus_intelligence import import_localizations, translation_queue


@dataclass(frozen=True, slots=True)
class DeepLUsage:
    character_count: int
    character_limit: int

    @property
    def remaining(self) -> int:
        return max(self.character_limit - self.character_count, 0)


@dataclass(frozen=True, slots=True)
class DeepLTranslation:
    texts: list[str]
    billed_characters: int
    model: str


class DeepLClient:
    """Small official DeepL v2 adapter that keeps the API key server-side."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
    ) -> None:
        if not settings.deepl_api_key:
            raise RuntimeError("DEEPL_API_KEY is required for Korean localization enrichment")
        self.api_key = settings.deepl_api_key
        self.base_url = (
            settings.deepl_base_url.rstrip("/")
            if settings.deepl_base_url
            else "https://api-free.deepl.com"
            if self.api_key.endswith(":fx")
            else "https://api.deepl.com"
        )
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": "ai-mot-research-lab/0.1 (Korean abstract localization)"},
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def usage(self) -> DeepLUsage:
        response = self.client.get(
            f"{self.base_url}/v2/usage",
            headers=self._headers(),
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("DeepL usage response was not a JSON object")
        return DeepLUsage(
            character_count=int(payload.get("character_count") or 0),
            character_limit=int(payload.get("character_limit") or 0),
        )

    def translate(self, texts: list[str], *, target_lang: str = "KO") -> DeepLTranslation:
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("DeepL translation texts must be nonblank")
        response = self.client.post(
            f"{self.base_url}/v2/translate",
            headers={**self._headers(), "Content-Type": "application/json"},
            json={
                "text": texts,
                "target_lang": target_lang,
                "show_billed_characters": True,
                "preserve_formatting": True,
            },
        )
        response.raise_for_status()
        payload = response.json()
        raw_translations = payload.get("translations") if isinstance(payload, dict) else None
        if not isinstance(raw_translations, list) or len(raw_translations) != len(texts):
            raise TypeError("DeepL returned an unexpected translation count")
        translated: list[str] = []
        billed = 0
        models: list[str] = []
        for item in raw_translations:
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                raise TypeError("DeepL returned an invalid translation item")
            translated.append(str(item["text"]).strip())
            billed += int(item.get("billed_characters") or 0)
            model = item.get("model_type_used")
            if isinstance(model, str) and model:
                models.append(model)
        return DeepLTranslation(
            texts=translated,
            billed_characters=billed or sum(len(text) for text in texts),
            model=models[0] if models else "deepl-v2",
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
        }


class KoreanAbstractLocalizationWorker:
    """Translate a bounded recent-paper batch without blocking corpus ingestion."""

    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        client: DeepLClient | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.client = client or DeepLClient(settings)
        self._owns_client = client is None

    def run(
        self,
        *,
        max_items: int = 20,
        max_characters: int = 15_000,
        lookback_days: int = 35,
    ) -> dict[str, Any]:
        usage_before = self.client.usage()
        reserve = self.settings.translation_monthly_reserve_characters
        available = max(usage_before.remaining - reserve, 0)
        batch_budget = min(max(max_characters, 0), available)
        result: dict[str, Any] = {
            "provider": "deepl",
            "locale": "ko",
            "usage_before": usage_before.character_count,
            "usage_limit": usage_before.character_limit,
            "monthly_reserve": reserve,
            "batch_budget": batch_budget,
            "selected": 0,
            "completed": 0,
            "failed": 0,
            "skipped_quota": 0,
            "source_characters": 0,
            "billed_characters": 0,
        }
        if batch_budget <= 0:
            result["status"] = "quota_wait"
            self.close()
            return result

        cutoff = datetime.now(UTC) - timedelta(days=max(lookback_days, 1))
        entries = translation_queue(
            self.session,
            locale="ko",
            limit=max(max_items * 4, max_items, 1),
            retrieved_after=cutoff,
        )
        remaining = batch_budget
        try:
            for entry in entries:
                if int(result["completed"]) >= max(max_items, 1):
                    break
                title = str(entry.get("title") or "").strip()
                abstract = str(entry.get("abstract") or "").strip()
                raw_keywords = entry.get("keywords")
                keywords = (
                    [str(keyword).strip() for keyword in raw_keywords if str(keyword).strip()]
                    if isinstance(raw_keywords, list)
                    else []
                )
                texts = [title, abstract, *keywords]
                source_characters = sum(len(text) for text in texts)
                result["selected"] = int(result["selected"]) + 1
                if source_characters > remaining:
                    result["skipped_quota"] = int(result["skipped_quota"]) + 1
                    continue
                try:
                    translated = self.client.translate(texts, target_lang="KO")
                    import_localizations(
                        self.session,
                        [
                            {
                                **entry,
                                "title_translated": translated.texts[0],
                                "abstract_translated": translated.texts[1],
                                "keywords": translated.texts[2:],
                                "provider": "deepl",
                                "model": translated.model,
                            }
                        ],
                    )
                except (httpx.HTTPError, TypeError, ValueError):
                    self.session.rollback()
                    result["failed"] = int(result["failed"]) + 1
                    continue
                result["completed"] = int(result["completed"]) + 1
                result["source_characters"] = int(result["source_characters"]) + source_characters
                result["billed_characters"] = int(result["billed_characters"]) + translated.billed_characters
                remaining = max(remaining - translated.billed_characters, 0)
        finally:
            self.close()
        result["status"] = "completed"
        result["remaining_batch_budget"] = remaining
        return result

    def close(self) -> None:
        if self._owns_client:
            self.client.close()
