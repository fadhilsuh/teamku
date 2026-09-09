---
date: 2026-09-09
title: Ask Teamku Policy Assistant
artifact_readiness: implementation-ready
execution: code
---

# Build Prompt: Ask Teamku Policy Assistant

Implement **Ask Teamku**, a tenant-scoped AI policy assistant for the Teamku HR application. Employees and managers should be able to ask questions about annual leave, sick leave, attendance, remote work, and other company policies and receive a concise answer grounded only in active policy content they are authorized to see.

This document is the execution prompt. Inspect the referenced code before editing, preserve existing behavior, and complete the feature end to end with migrations, API behavior, UI, tests, and documentation.

## Product outcome

An employee can ask questions such as:

- “How many sick-leave days do I have?”
- “Do I need a doctor’s letter?”
- “Can I take leave during probation?”
- “What happens when I forget to check out?”
- “Who approves my leave request?”

Ask Teamku returns:

1. A direct, plain-language answer in Bahasa Indonesia or English, matching the question.
2. Citations to the exact company-policy sections supporting the answer.
3. Relevant personalized facts already known by Teamku, such as the employee’s current leave balance, without sending unnecessary private fields to the language model.
4. A clear uncertainty state when the available policy does not support an answer.
5. A safe next action such as opening the leave-request screen or contacting HR.

## Non-negotiable boundaries

- Never answer from general model knowledge when company policy evidence is absent.
- Never invent policy, legal requirements, citations, balances, eligibility, or effective dates.
- Clearly distinguish company policy from Indonesian legal or regulatory information. The initial release answers company policy only and must not claim legal advice.
- The assistant must not approve or reject leave, discipline employees, interpret motives, score people, or make any employment decision.
- Enforce tenant isolation and existing role visibility on the server. Never trust client-provided tenant or employee identifiers.
- Managers must remain department-scoped and must never receive salary or unrelated sensitive employee data.
- Do not send credentials, precise locations, salary, private leave reasons, photos, or unrelated employee records to the model.
- Store an audit record for every policy answer, including actor, sources used, model/provider identifier, outcome state, and timestamp. Do not store hidden chain-of-thought.
- If the AI provider is unavailable, retrieval still fails safely with a helpful “Ask HR” response. Do not fabricate a fallback answer.

## Existing architecture to preserve

- `apps/web` is a Next.js UI that calls `/api/v1`.
- `apps/api/src/movon_hr/modules/api.py` currently owns domain models, authorization, validation, audit behavior, and API routes.
- `apps/api/src/movon_hr/core/persistence.py` owns PostgreSQL persistence and schema synchronization.
- Production persistence is PostgreSQL; the in-memory store remains a supported demo/test adapter.
- Follow the authentication, tenancy, role-scoping, API error, and audit patterns already present in the repository.
- Existing leave behavior and balances remain authoritative; AI may explain them but must not recalculate them independently.

## Functional requirements

### R1. HR-managed policies

HR administrators can create, edit, publish, unpublish, and supersede policy documents within their tenant.

Each policy contains:

- stable ID and tenant ID;
- title and policy category;
- language;
- effective date and optional expiry date;
- lifecycle state: `draft`, `published`, or `archived`;
- ordered sections with a stable section ID, heading, and plain-text body;
- created/updated timestamps and actor IDs.

Only published policies effective on the current date are eligible for answers. Draft and archived content must never be retrieved for employees or managers.

For the initial release, use structured text entry in Teamku. Do not add PDF/OCR ingestion, web crawling, or document embeddings unless the existing stack already provides a justified, tested mechanism.

### R2. Deterministic policy retrieval

Implement a server-side retrieval service that searches only authorized, currently effective policy sections belonging to the authenticated tenant.

- Prefer a simple, deterministic PostgreSQL-backed search suitable for the MVP. Keyword/full-text search is acceptable.
- Keep retrieval behind an interface so embeddings or an external vector store can be introduced later without changing the API contract.
- Return stable section references, snippets, and relevance signals.
- If no sufficiently relevant section exists, return `insufficient_evidence`; do not ask the model to improvise.
- Retrieval must be testable without a network call.

### R3. Grounded answer generation

Add an AI provider interface in the API with:

- a production adapter configured only through environment variables;
- a deterministic fake adapter for tests and local demo behavior;
- explicit timeout and error handling;
- structured output validation.

The generation request must include only the user’s question, minimal role/context, relevant deterministic facts, and retrieved policy excerpts. Require structured output containing:

- `answer`;
- `citations` referencing supplied policy and section IDs only;
- `language`;
- `confidence`: `supported`, `partially_supported`, or `insufficient_evidence`;
- `suggested_action`: a known internal action or `contact_hr`.

Reject citations not present in the retrieval set. If validation fails, return a safe non-answer rather than raw model output.

### R4. Personalized facts

Resolve supported personal facts through deterministic server-side functions. For the first release, support:

- authenticated employee name and role;
- current leave balance from the existing leave workflow;
- the existing approval path when it can be determined reliably;
- tenant-configured attendance policy fields already visible to that user.

Keep these facts separate from policy excerpts and label them clearly in the response. Do not let the model calculate balances or infer eligibility.

### R5. Ask API

Add an authenticated endpoint similar to:

`POST /api/v1/policy-assistant/questions`

Request:

```json
{ "question": "Apakah saya perlu surat dokter untuk cuti sakit?" }
```

Response shape:

```json
{
  "answer": "...",
  "confidence": "supported",
  "citations": [
    {
      "policy_id": "...",
      "policy_title": "Sick Leave Policy",
      "section_id": "medical-certificate",
      "section_heading": "Medical certificate",
      "effective_date": "2026-01-01",
      "excerpt": "..."
    }
  ],
  "personal_facts": [],
  "suggested_action": {
    "type": "open_leave_request",
    "href": "/app/time/time-off"
  }
}
```

Use a stable error/non-answer contract for empty questions, overlong questions, insufficient evidence, provider timeouts, and invalid model output. Apply a sensible server-side question-length limit.

### R6. Employee and manager UI

Add an **Ask Teamku** page within the authenticated application shell.

The page should include:

- a clear statement that answers come from company policies and may require HR confirmation;
- a question input with example prompts;
- loading, empty, error, and insufficient-evidence states;
- an answer panel with confidence wording, expandable citations, effective dates, and excerpts;
- an appropriate internal-action button when returned by the API;
- a prominent **Contact HR** fallback;
- responsive and keyboard-accessible behavior.

Do not present the interface as an unrestricted conversational companion. A single-question flow with optional recent questions for the current user is sufficient. Do not persist conversation history in the initial release unless required for the audit record.

### R7. HR policy administration UI

Extend the existing settings area with policy management available only to HR administrators.

- List policies and their state/effective dates.
- Create and edit metadata and ordered sections.
- Preview what employees will see.
- Publish only after validation confirms a title, effective date, and at least one non-empty section.
- Require confirmation before unpublishing or superseding a published policy.
- Show audit-relevant timestamps and actors.

### R8. Auditing and privacy

Record:

- the authenticated actor and tenant;
- normalized question or a privacy-minimized representation;
- IDs and versions of cited policy sections;
- provider/model identifier;
- response confidence/outcome;
- timestamp and suggested action.

Do not record provider secrets, hidden reasoning, or unnecessary copies of sensitive personal data. Document retention implications and ensure audit visibility follows existing HR-only conventions.

## Suggested implementation units

### U1. Policy domain and persistence

Add policy and policy-section domain models, in-memory storage, PostgreSQL tables, schema synchronization, and an Alembic migration.

Likely files:

- `apps/api/src/movon_hr/modules/api.py`
- `apps/api/src/movon_hr/core/persistence.py`
- `apps/api/alembic/versions/<new_policy_migration>.py`
- `apps/api/tests/test_policy_management.py`
- `apps/api/tests/test_schema_sync.py`

Test tenant isolation, lifecycle transitions, effective dates, ordering, validation, persistence hydration, and HR-only mutation authorization.

### U2. Retrieval and grounded-answer service

Introduce focused service modules rather than expanding all AI logic inline in `modules/api.py`.

Suggested files:

- `apps/api/src/movon_hr/core/policy_retrieval.py`
- `apps/api/src/movon_hr/core/ai_provider.py`
- `apps/api/src/movon_hr/core/policy_assistant.py`
- `apps/api/tests/test_policy_retrieval.py`
- `apps/api/tests/test_policy_assistant.py`

Test retrieval isolation, effective-policy filtering, citation validation, prompt-data minimization, deterministic personal facts, insufficient evidence, provider failure, timeout, malformed structured output, and attempted citation injection.

### U3. Policy and question APIs

Add HR policy-management endpoints and the authenticated question endpoint using existing API conventions.

Test employee, manager, and HR access; cross-tenant denial; unpublished-policy exclusion; question validation; response contracts; audit creation; and safe failure states.

### U4. Ask Teamku interface

Suggested files:

- `apps/web/src/app/app/ask-teamku/page.tsx`
- `apps/web/src/lib/api.ts`
- the existing authenticated navigation component under `apps/web/src/components/`

Add typed API client models and implement the complete accessible question/answer experience. Verify Bahasa Indonesia and English text do not break layout.

### U5. HR policy-management interface

Extend `apps/web/src/app/app/settings/page.tsx` or introduce a focused settings subpage if the existing page would become unwieldy. Keep HR-only controls hidden in the UI and protected again by the API.

Test or manually verify draft creation, section editing/reordering, preview, publish validation, unpublish confirmation, responsive layout, and authorization failures.

### U6. Documentation and configuration

Document:

- required AI provider environment variables;
- safe local/fake-provider behavior;
- the grounded-answer and citation contract;
- data sent to the provider and explicitly excluded fields;
- operational timeout/failure behavior;
- policy-authoring guidance for HR;
- the limitation that Ask Teamku is not legal advice.

Update `.env.example`, `README.md`, `docs/architecture.md`, `docs/privacy-and-permissions.md`, and `docs/runbook.md` where applicable.

## Verification scenarios

At minimum, prove these behaviors:

1. An employee receives an answer supported by an active policy section with a valid citation.
2. The same question receives `insufficient_evidence` when no published relevant section exists.
3. A draft, expired, archived, or future policy never influences an answer.
4. A user in tenant A cannot retrieve or cite tenant B’s policy.
5. A manager cannot access employees or personal facts outside their department.
6. The assistant returns the existing authoritative leave balance and never asks the model to calculate it.
7. A malicious question cannot cause retrieval of salary, credentials, exact location, private leave reasons, or another tenant’s content.
8. A provider response containing a fabricated citation is rejected safely.
9. Provider timeout or outage returns a helpful non-answer with Contact HR, not a server error or invented response.
10. Only HR administrators can create, edit, publish, archive, or supersede policies.
11. Policy edits and assistant outcomes produce appropriate audit records.
12. Existing attendance, leave, payroll, authentication, tenancy, and notification tests continue to pass.

Run the repository’s normal quality gates:

```bash
cd apps/api && uv run pytest && uv run ruff check .
cd apps/web && npm run lint && npm run build
```

## Definition of done

- All requirements R1–R8 work through both PostgreSQL and the in-memory test/demo adapter.
- Answers are impossible without authorized, effective policy evidence.
- Every factual policy statement shown to the user has a valid visible citation.
- Personalized values come from deterministic Teamku services, not model inference.
- Tenant, role, department, and sensitive-field boundaries have automated coverage.
- Provider failures and malformed outputs fail safely.
- HR can manage and publish policy content without editing code.
- Employees and managers can use Ask Teamku from the authenticated UI.
- Relevant audit, privacy, architecture, configuration, and runbook documentation is updated.
- Existing tests pass alongside the new API and UI verification.

## Implementation guidance

Start by reading the current data models, tenancy helpers, persistence snapshot flow, API response conventions, authenticated shell/navigation, settings page, leave balance calculation, and test fixtures. Implement in dependency order from U1 through U6. Keep commits focused if the execution environment supports commits, but do not change unrelated user work.

When a detail is underspecified, choose the smallest reversible design consistent with the boundaries above. Stop and surface a blocker only when a choice would materially change security, data retention, legal positioning, or product scope.
