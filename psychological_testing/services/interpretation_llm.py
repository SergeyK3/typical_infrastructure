"""
AI interpretation for PDF export: session ``ai_enrichment`` and manifest ``ai_cache``.

Lazy + cache: on export, missing narrative slots are filled via LLM once, then persisted.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from psychological_testing.integration.session_persistence import (
    apply_ai_enrichment,
    persist_json_enabled,
    update_session_ai_enrichment,
)
from psychological_testing.services.llm_service import (
    LlmClient,
    default_llm_model,
    get_llm_client,
    llm_provider,
)
from psychological_testing.services.prompt_loader import (
    prompt_for_cross_test_slot,
    prompt_for_test,
)
from psychological_testing.shared_engine.report_contract import (
    AI_ENRICHMENT_SCHEMA_VERSION,
    get_ai_section_text,
)

_log = logging.getLogger(__name__)

INTERPRETATION_SLOT = "interpretation"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.3


class InterpretationMockLlm:
    """Deterministic narratives for tests without API keys."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
    ) -> str:
        self.calls.append({"model": model, "messages": messages, "temperature": temperature})
        user = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
        if "общий психологический портрет" in user.lower() or "результаты всех тестов" in user.lower():
            return (
                "ОБЩИЙ ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ (mock)\n\n"
                "Сводный профиль сформирован по завершённым тестам. "
                "Рекомендуется учитывать DISC и MBTI при распределении ролей в команде."
            )
        if "профессиональному развитию" in user.lower() or "подбору в команду" in user.lower():
            return (
                "РЕКОМЕНДАЦИИ ПО РАЗВИТИЮ (mock)\n\n"
                "1. Усилить навыки коммуникации.\n"
                "2. Развивать стратегическое мышление.\n"
                "3. Подбирать в команду дополняющие DISC-профили."
            )
        for test_id in ("paei", "disc", "hexaco", "soft_skills", "mbti"):
            if test_id.upper() in user or test_id in user.lower():
                return f"Интерпретация по тесту {test_id.upper()} (mock): профиль согласован с переданными баллами."
        if "MBTI" in user:
            return "Интерпретация MBTI (mock): сильные стороны — системность; зоны роста — гибкость."
        return "Интерпретация (mock): текст согласован с результатами тестирования."


def interpretation_ai_enabled() -> bool:
    """Whether export may call LLM (still uses cache when disabled)."""
    raw = (
        os.getenv("PSYCH_TESTING_PDF_AI")
        or os.getenv("PSYCH_TESTING_AI_ENABLED")
        or ""
    ).strip().lower()
    return raw in ("1", "true", "yes")


def get_interpretation_llm(*, force_mock: bool = False) -> LlmClient:
    if force_mock:
        return InterpretationMockLlm()
    if llm_provider() == "mock":
        return InterpretationMockLlm()
    return get_llm_client()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scores_line(scores: dict[str, Any] | None) -> str:
    if not isinstance(scores, dict):
        return ""
    parts: list[str] = []
    for key in ("normalized_scores", "raw_scores"):
        block = scores.get(key)
        if isinstance(block, dict) and block:
            parts.append(
                ", ".join(f"{k}: {v}" for k, v in sorted(block.items(), key=lambda x: str(x[0])))
            )
    typology = scores.get("typology_code")
    if typology:
        parts.append(f"тип: {typology}")
    axis = scores.get("axis_details")
    if isinstance(axis, dict) and axis:
        for ax_name, detail in axis.items():
            if isinstance(detail, dict) and detail.get("dominant"):
                parts.append(f"{ax_name}={detail['dominant']}")
    return "; ".join(parts)


def _static_context(session: dict[str, Any]) -> str:
    interp = session.get("interpretation")
    if isinstance(interp, dict):
        profile = interp.get("profile")
        if isinstance(profile, dict):
            name = (
                profile.get("archetype_ru")
                or profile.get("name_ru")
                or profile.get("code")
            )
            if name:
                return f"Статический профиль: {name}"
        code = interp.get("typology_code")
        if code:
            return f"Тип: {code}"
    report = session.get("report") or {}
    if isinstance(report, dict):
        text = str(report.get("text_telegram") or "").strip()
        if text:
            return text[:500]
    return ""


def build_test_user_prompt(session: dict[str, Any]) -> str:
    test_id = str(session.get("test_id") or "")
    scores_text = _scores_line(session.get("scores"))
    lines = [f"Проанализируй результаты теста {test_id.upper()}: {scores_text}"]
    ctx = _static_context(session)
    if ctx:
        lines.append(f"\nКонтекст (детерминированный scoring, не изменять): {ctx}")
    return "\n".join(lines)


def build_cross_test_user_prompt(
    sessions_by_test: dict[str, dict[str, Any]],
    *,
    slot: str,
) -> str:
    lines = ["Результаты завершённых тестов:\n"]
    order = ("mbti", "paei", "soft_skills", "hexaco", "disc")
    seen: set[str] = set()
    for test_id in list(order) + sorted(sessions_by_test.keys()):
        if test_id in seen or test_id not in sessions_by_test:
            continue
        seen.add(test_id)
        doc = sessions_by_test[test_id]
        scores_text = _scores_line(doc.get("scores"))
        ai_bit = get_ai_section_text(doc, INTERPRETATION_SLOT)
        block = f"{test_id.upper()}: {scores_text}"
        if ai_bit:
            block += f"\n  Краткая интерпретация: {ai_bit[:400]}"
        lines.append(block + "\n")

    if slot == "career_recommendations":
        lines.append(
            "\nСформируй рекомендации по профессиональному развитию и подбору в команду "
            "на основе данных выше."
        )
    else:
        lines.append(
            "\nСоздай общий психологический портрет и заключение на основе данных выше."
        )
    return "\n".join(lines)


def _call_llm(
    llm: LlmClient,
    *,
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float = DEFAULT_TEMPERATURE,
) -> tuple[str, dict[str, int]]:
    text = llm.chat(
        model,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    usage = {
        "input_tokens": max(1, len(system_prompt) // 4 + len(user_prompt) // 4),
        "output_tokens": max(1, len(text) // 4),
    }
    return text.strip(), usage


def _new_enrichment_block(
    *,
    sections: dict[str, str],
    prompt_version: str,
    usage: dict[str, int],
    model: str,
) -> dict[str, Any]:
    return {
        "schema_version": AI_ENRICHMENT_SCHEMA_VERSION,
        "generated_at": _utc_now_iso(),
        "provider": llm_provider(),
        "model": model,
        "prompt_version": prompt_version,
        "sections": sections,
        "usage": usage,
    }


def enrich_session(
    session: dict[str, Any],
    slots: list[str] | None = None,
    *,
    regenerate: bool = False,
    llm: LlmClient | None = None,
    persist: bool = True,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Fill ``ai_enrichment.sections`` for per-test slots (default: ``interpretation``).

    Returns updated session document (persisted when ``persist=True`` and env allows).
    """
    want = slots or [INTERPRETATION_SLOT]
    test_id = str(session.get("test_id") or "")
    if not test_id:
        raise ValueError("session.test_id is required for enrich_session")

    to_generate: list[str] = []
    for slot in want:
        if regenerate or not get_ai_section_text(session, slot):
            to_generate.append(slot)

    if not to_generate:
        return session

    if llm is None and not interpretation_ai_enabled() and not regenerate:
        _log.info("interpretation_ai disabled, skipping LLM for %s", test_id)
        return session

    client = llm or get_interpretation_llm()
    model_name = model or default_llm_model("report") or DEFAULT_MODEL
    system_prompt, prompt_version = prompt_for_test(test_id)
    user_prompt = build_test_user_prompt(session)

    generated: dict[str, str] = {}
    total_usage = {"input_tokens": 0, "output_tokens": 0}
    for slot in to_generate:
        if slot != INTERPRETATION_SLOT:
            _log.warning("unsupported per-session slot %s for test %s", slot, test_id)
            continue
        text, usage = _call_llm(
            client,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model_name,
        )
        generated[slot] = text
        total_usage["input_tokens"] += usage.get("input_tokens", 0)
        total_usage["output_tokens"] += usage.get("output_tokens", 0)

    if not generated:
        return session

    enrichment = _new_enrichment_block(
        sections=generated,
        prompt_version=prompt_version,
        usage=total_usage,
        model=model_name,
    )
    updated = apply_ai_enrichment(session, enrichment)

    session_id = str(session.get("session_id") or "")
    if persist and session_id and persist_json_enabled():
        from psychological_testing.integration.session_repository import get_session_document

        if get_session_document(session_id) is not None:
            update_session_ai_enrichment(session_id, enrichment)

    return updated


def get_manifest_ai_text(manifest: dict[str, Any], slot: str) -> str | None:
    cache = manifest.get("ai_cache")
    if not isinstance(cache, dict):
        return None
    value = cache.get(slot)
    return str(value).strip() if value else None


def set_manifest_ai_cache(
    manifest: dict[str, Any],
    slot: str,
    text: str,
    *,
    prompt_version: str,
    model: str,
    usage: dict[str, int] | None = None,
) -> dict[str, Any]:
    out = dict(manifest)
    cache = dict(out.get("ai_cache") or {})
    cache[slot] = text
    meta = dict(cache.get("_meta") or {})
    meta[slot] = {
        "generated_at": _utc_now_iso(),
        "prompt_version": prompt_version,
        "model": model,
        "provider": llm_provider(),
        "usage": usage or {},
    }
    cache["_meta"] = meta
    out["ai_cache"] = cache
    return out


def enrich_manifest_cross_test(
    manifest: dict[str, Any],
    sessions_by_test: dict[str, dict[str, Any]],
    slots: list[str],
    *,
    regenerate: bool = False,
    llm: LlmClient | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Fill ``manifest.ai_cache`` for cross-test slots (``general_summary``, ``career_recommendations``)."""
    if not slots:
        return manifest

    client = llm or get_interpretation_llm()
    model_name = model or default_llm_model("report") or DEFAULT_MODEL
    out = dict(manifest)

    for slot in slots:
        if not regenerate and get_manifest_ai_text(out, slot):
            continue
        if llm is None and not interpretation_ai_enabled() and not regenerate:
            continue

        system_prompt, prompt_version = prompt_for_cross_test_slot(slot)
        user_prompt = build_cross_test_user_prompt(sessions_by_test, slot=slot)
        text, usage = _call_llm(
            client,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model_name,
        )
        out = set_manifest_ai_cache(
            out,
            slot,
            text,
            prompt_version=prompt_version,
            model=model_name,
            usage=usage,
        )

    return out


def collect_required_ai_slots(
    manifest: dict[str, Any],
    registry: Any,
) -> tuple[dict[str, list[str]], list[str]]:
    """
    From enabled manifest sections, return per-test_id slots and cross-test slots.
    """
    per_test: dict[str, list[str]] = {}
    cross: list[str] = []

    sections_cfg = manifest.get("sections") or []
    if not isinstance(sections_cfg, list):
        return per_test, cross

    for item in sections_cfg:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        section_id = str(item.get("section_id") or "")
        spec = registry.sections.get(section_id)
        if spec is None or not spec.ai_slots:
            continue
        if spec.cross_test:
            for slot in spec.ai_slots:
                if slot not in cross:
                    cross.append(slot)
            continue
        if spec.test_id:
            slots = per_test.setdefault(spec.test_id, [])
            for slot in spec.ai_slots:
                if slot not in slots:
                    slots.append(slot)

    return per_test, cross


def ensure_export_ai_enrichment(
    manifest: dict[str, Any],
    sessions_by_test: dict[str, dict[str, Any]],
    *,
    registry: Any,
    regenerate_ai: bool = False,
    llm: LlmClient | None = None,
    persist_sessions: bool = True,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """
    Lazy-fill AI narratives before PDF render.

    Returns ``(manifest, sessions_by_test)`` with caches populated.
    """
    per_test_slots, cross_slots = collect_required_ai_slots(manifest, registry)
    updated_sessions = dict(sessions_by_test)

    for test_id, slots in per_test_slots.items():
        doc = updated_sessions.get(test_id)
        if not doc:
            continue
        updated_sessions[test_id] = enrich_session(
            doc,
            slots,
            regenerate=regenerate_ai,
            llm=llm,
            persist=persist_sessions,
        )

    updated_manifest = enrich_manifest_cross_test(
        manifest,
        updated_sessions,
        cross_slots,
        regenerate=regenerate_ai,
        llm=llm,
    )
    return updated_manifest, updated_sessions


def persist_manifest_file(manifest_path: str, manifest: dict[str, Any]) -> None:
    """Write manifest JSON back (wrapper with ``manifest`` key preserved)."""
    from pathlib import Path

    path = Path(manifest_path)
    raw: dict[str, Any]
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict) and isinstance(loaded.get("manifest"), dict):
            raw = loaded
            raw["manifest"] = manifest
        else:
            raw = manifest
    else:
        raw = manifest
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
