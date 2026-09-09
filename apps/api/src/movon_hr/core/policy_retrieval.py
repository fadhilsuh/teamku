"""Deterministic, tenant-local policy section retrieval for Ask Teamku."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class PolicyEvidence:
    policy_id: str
    policy_title: str
    section_id: str
    section_heading: str
    effective_date: date
    excerpt: str
    score: int


def _terms(value: str) -> set[str]:
    return {term for term in re.findall(r"[\w-]{2,}", value.lower()) if len(term) > 2}


def retrieve(policies: list[object], question: str, today: date) -> list[PolicyEvidence]:
    """Return effective published sections matching at least one meaningful term.

    The objects are deliberately duck-typed so this deterministic interface stays
    independent of the in-memory and PostgreSQL adapters.
    """
    terms = _terms(question)
    matches: list[PolicyEvidence] = []
    for policy in policies:
        if (
            policy.state != "published"
            or policy.effective_date > today
            or (policy.expiry_date and policy.expiry_date < today)
        ):
            continue
        for section in policy.sections:
            searchable = f"{policy.title} {policy.category} {section.heading} {section.body}"
            score = len(terms & _terms(searchable))
            if score:
                excerpt = section.body[:500].strip()
                matches.append(
                    PolicyEvidence(
                        policy.id,
                        policy.title,
                        section.id,
                        section.heading,
                        policy.effective_date,
                        excerpt,
                        score,
                    )
                )
    return sorted(matches, key=lambda item: (-item.score, item.policy_title, item.section_heading))[:5]
