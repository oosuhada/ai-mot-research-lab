from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.corpus_intelligence import (
    import_localizations,
    translation_queue,
    translation_source_payload,
)
from research_lab.localization_enrichment import (
    DeepLClient,
    DeepLTranslation,
    DeepLUsage,
    KoreanAbstractLocalizationWorker,
)
from research_lab.models import Paper, PaperLocalization, PaperTopic, Topic


def _paper() -> Paper:
    return Paper(
        title="AI adoption and firm performance",
        abstract="This study explains how artificial intelligence changes organizational outcomes.",
        primary_source="openalex",
        source_record_id="W-LOCALIZATION",
        retrieved_at=datetime.now(UTC),
        provenance={},
    )


def _engine() -> Any:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (Paper.__table__, Topic.__table__, PaperTopic.__table__, PaperLocalization.__table__):
        table.create(engine)
    return engine


def test_deepl_client_uses_free_endpoint_and_header_auth() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/usage"):
            return httpx.Response(
                200,
                json={"character_count": 120, "character_limit": 500_000},
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "translations": [
                    {"text": "인공지능 도입", "billed_characters": 11, "model_type_used": "latency_optimized"}
                ]
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = DeepLClient(Settings(deepl_api_key="test-secret:fx"), client=http_client)

    assert client.usage() == DeepLUsage(character_count=120, character_limit=500_000)
    translated = client.translate(["AI adoption"])

    assert translated.texts == ["인공지능 도입"]
    assert translated.billed_characters == 11
    assert all(request.url.host == "api-free.deepl.com" for request in requests)
    assert all("test-secret" not in str(request.url) for request in requests)
    assert all(request.headers["Authorization"] == "DeepL-Auth-Key test-secret:fx" for request in requests)
    http_client.close()


class _FakeDeepLClient:
    def __init__(self, usage: DeepLUsage) -> None:
        self.current_usage = usage
        self.translated = 0

    def usage(self) -> DeepLUsage:
        return self.current_usage

    def translate(self, texts: list[str], *, target_lang: str = "KO") -> DeepLTranslation:
        assert target_lang == "KO"
        self.translated += 1
        translated = ["AI 도입과 기업 성과", "인공지능이 조직 성과를 어떻게 바꾸는지 설명합니다."]
        translated.extend(f"{text} 키워드" for text in texts[2:])
        return DeepLTranslation(
            texts=translated,
            billed_characters=sum(len(text) for text in texts),
            model="test-model",
        )

    def close(self) -> None:
        return None


def test_worker_waits_when_only_monthly_reserve_remains() -> None:
    engine = _engine()
    fake = _FakeDeepLClient(DeepLUsage(character_count=490_000, character_limit=500_000))
    with Session(engine) as session:
        session.add(_paper())
        session.commit()
        result = KoreanAbstractLocalizationWorker(
            session,
            Settings(deepl_api_key="unused", translation_monthly_reserve_characters=10_000),
            client=fake,  # type: ignore[arg-type]
        ).run()

    assert result["status"] == "quota_wait"
    assert result["completed"] == 0
    assert fake.translated == 0


def test_worker_translates_and_persists_verified_korean_abstract() -> None:
    engine = _engine()
    fake = _FakeDeepLClient(DeepLUsage(character_count=0, character_limit=500_000))
    with Session(engine) as session:
        paper = _paper()
        topic = Topic(slug="ai-adoption", display_name="AI adoption", kind="keyword")
        session.add_all([paper, topic])
        session.flush()
        session.add(
            PaperTopic(
                paper_id=paper.id,
                topic_id=topic.id,
                score=1.0,
                assignment_source="test",
            )
        )
        session.commit()

        result = KoreanAbstractLocalizationWorker(
            session,
            Settings(deepl_api_key="unused"),
            client=fake,  # type: ignore[arg-type]
        ).run(max_items=1, max_characters=10_000)
        localization = session.query(PaperLocalization).one()
        source_hash = translation_source_payload(session, paper)["source_hash"]

        assert result["completed"] == 1
        assert localization.status == "completed"
        assert localization.abstract and "인공지능" in localization.abstract
        assert localization.provider == "deepl"
        assert localization.model == "test-model"
        assert localization.source_hash == source_hash


def test_import_rejects_stale_or_non_korean_abstract() -> None:
    engine = _engine()
    with Session(engine) as session:
        paper = _paper()
        session.add(paper)
        session.commit()
        payload = translation_source_payload(session, paper)

        with pytest.raises(ValueError, match="source changed"):
            import_localizations(
                session,
                [{**payload, "source_hash": "stale", "abstract_translated": "한글 초록"}],
            )
        with pytest.raises(ValueError, match="contains no Hangul"):
            import_localizations(
                session,
                [{**payload, "abstract_translated": "English only"}],
            )


def test_translation_queue_requeues_completed_localization_after_source_change() -> None:
    engine = _engine()
    with Session(engine) as session:
        paper = _paper()
        session.add(paper)
        session.commit()
        source = translation_source_payload(session, paper)
        session.add(
            PaperLocalization(
                paper_id=paper.id,
                locale="ko",
                title="AI 도입과 기업 성과",
                abstract="인공지능이 조직 성과를 바꾸는 방식을 설명합니다.",
                status="completed",
                source_hash=str(source["source_hash"]),
                provider="test",
            )
        )
        session.commit()

        assert translation_queue(session) == []
        paper.abstract = f"{paper.abstract} Updated evidence."
        session.commit()

        queue = translation_queue(session)
        assert len(queue) == 1
        assert queue[0]["source_hash"] != source["source_hash"]
