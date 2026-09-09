"""Small provider boundary; no provider receives data beyond its prompt object."""

from __future__ import annotations

from dataclasses import dataclass


class ProviderError(Exception):
    pass


@dataclass(frozen=True)
class GeneratedAnswer:
    answer: str
    citations: list[dict[str, str]]
    language: str
    confidence: str
    suggested_action: str


class FakePolicyProvider:
    """Predictable local/demo provider that only summarizes supplied evidence."""

    identifier = "fake-policy-provider-v1"

    def answer(self, question: str, evidence: list[object], facts: list[dict]) -> GeneratedAnswer:
        if not evidence:
            raise ProviderError("No evidence supplied")
        first = evidence[0]
        language = "id" if any(token in question.lower() for token in ("apa", "cuti", "saya", "dan", "yang")) else "en"
        prefix = "Menurut kebijakan perusahaan" if language == "id" else "According to company policy"
        fact_text = ""
        if facts:
            fact_text = " " + facts[0]["label"] + ": " + str(facts[0]["value"]) + "."
        return GeneratedAnswer(
            answer=f"{prefix}, {first.excerpt}{fact_text}",
            citations=[{"policy_id": first.policy_id, "section_id": first.section_id}],
            language=language,
            confidence="supported",
            suggested_action="open_leave_request" if "leave" in first.policy_title.lower() or "cuti" in question.lower() else "contact_hr",
        )
