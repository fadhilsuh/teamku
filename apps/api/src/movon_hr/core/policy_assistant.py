"""Grounded policy-answer orchestration and strict output validation."""

from __future__ import annotations

from dataclasses import asdict

from movon_hr.core.ai_provider import FakePolicyProvider, ProviderError
from movon_hr.core.policy_retrieval import retrieve


def answer_question(*, policies: list[object], question: str, today, facts: list[dict]) -> tuple[dict, str]:
    evidence = retrieve(policies, question, today)
    fallback = {
        "answer": "Kebijakan perusahaan yang aktif belum cukup untuk menjawab pertanyaan ini. Silakan hubungi HR.",
        "confidence": "insufficient_evidence",
        "citations": [],
        "personal_facts": facts,
        "suggested_action": {"type": "contact_hr", "href": "mailto:hr@company.local"},
    }
    if not evidence:
        return fallback, "insufficient_evidence"
    try:
        generated = FakePolicyProvider().answer(question, evidence, facts)
    except (ProviderError, TimeoutError):
        return {**fallback, "answer": "Layanan Ask Teamku sedang tidak tersedia. Silakan hubungi HR."}, "provider_unavailable"
    allowed = {(item.policy_id, item.section_id) for item in evidence}
    cited = [(item.get("policy_id"), item.get("section_id")) for item in generated.citations]
    if generated.confidence not in {"supported", "partially_supported", "insufficient_evidence"} or not cited or not set(cited) <= allowed:
        return {**fallback, "answer": "Jawaban tidak dapat diverifikasi terhadap kebijakan yang tersedia. Silakan hubungi HR."}, "invalid_provider_output"
    citation_map = {(item.policy_id, item.section_id): asdict(item) for item in evidence}
    action = {"type": "contact_hr", "href": "mailto:hr@company.local"}
    if generated.suggested_action == "open_leave_request":
        action = {"type": "open_leave_request", "href": "/app/time/time-off"}
    return {
        "answer": generated.answer,
        "confidence": generated.confidence,
        "citations": [citation_map[item] for item in cited],
        "personal_facts": facts,
        "suggested_action": action,
    }, "supported"
