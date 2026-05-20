# 12 — Risk Register

Версия: Draft 0.1

---

## 1. Risk matrix

| ID | Risk | Probability | Impact | Score | Mitigation |
|----|------|-------------|--------|-------|------------|
| R1 | MBTI hardcoded in core engine | Medium | High | **High** | Extension point; `tests/mbti/` plugin only |
| R2 | Mixing with Skill Assessment | Medium | High | **High** | Separate package, prefix, docs |
| R3 | Research code leaks to production | Medium | Medium | Medium | `research/` boundary + CI import guard |
| R4 | Legacy bot copied as-is | Low | High | Medium | Extract patterns, not files |
| R5 | CSV/item bank version drift | Medium | Medium | Medium | Version pinning on sessions |
| R6 | AI psychometry misuse | Low | High | Medium | HR OS §11; disclaimers; no auto-decisions |
| R7 | Premature DB/API work | Medium | Medium | Medium | Phase 4 gate explicit |
| R8 | Psych data sensitivity breach | Low | High | Medium | RBAC matrix; org-scoped storage |
| R9 | STT misrecognition → wrong score | **High** | High | **High** | Resolver + confidence + reprompt; buttons always available |
| R10 | LLM used to map voice → score | Medium | High | **High** | Explicit ban; deterministic resolver only |
| R11 | Ambiguous voice answers | **High** | Medium | Medium | answer_patterns.yaml; reprompt with buttons |
| R12 | MBTI nb2 in production | Low | High | Medium | delivery_mode flag; structured only |
| R13 | Orchestrator v3 conflates inference + score | Medium | High | Medium | Research track separate |
| R14 | VseGPT direct API in prod | Medium | Medium | Medium | Platform gateway only in prod |
| R15 | Voice-only users blocked if STT down | Medium | Medium | Medium | Buttons always shown; text fallback |
| R16 | Telegram callback data collision | Low | Medium | Low | `pt:` prefix on callbacks |
| R17 | Multi-instance session loss | High | Medium | Medium | Phase 4 persistence; until then single worker |
| R18 | HEXACO scoring incorrect (A/C swap) | Medium | Medium | Medium | Review legacy mapping before Phase 2 |

---

## 2. Detailed mitigations

### R9 — STT misrecognition

**Scenario:** User says «Б» but Whisper returns «в» or «бэ».

**Mitigations:**

1. Inline buttons always visible — zero STT error path
2. answer_resolver fuzzy match + confidence score
3. Reprompt below threshold 0.7 — do not record score
4. Store raw_transcript for dispute audit
5. Voice hint encourages clear pronunciation: «скажите А или Б»

### R10 — LLM answer mapping

**Scenario:** Developer uses GPT to interpret free-form voice instead of resolver.

**Mitigations:**

1. Architecture doc ban ([07_AI_INTEGRATION_BOUNDARIES.md](07_AI_INTEGRATION_BOUNDARIES.md))
2. Code review checklist
3. Scoring pipeline accepts only StructuredAnswer with resolved_value
4. CI test: same transcript → same score (determinism)

### R11 — Ambiguous voice

**Scenario:** User says «ну типа первый наверное».

**Mitigations:**

1. Test-specific patterns in `answer_patterns.yaml`
2. Fuzzy match against option text (optional, lower confidence)
3. Reprompt: «Нажмите кнопку A или B для точного ответа»
4. Never guess below confidence threshold

### R15 — STT unavailable

**Scenario:** OpenAI key missing or Whisper API down.

**Mitigations:**

1. User message: «Голосовой ввод недоступен. Используйте кнопки.»
2. Buttons remain fully functional
3. Text input still accepted
4. mock STT for dev/test environments

---

## 3. Compliance risks

| Risk | Regulation concern | Mitigation |
|------|-------------------|------------|
| Psych results used for firing | Labor law / ethics | HR OS §11; human-in-the-loop |
| Data leak cross-tenant | GDPR / 152-FZ | client_id isolation on all pt_* |
| Voice stored without consent | Privacy | Policy TBD; default: transcript only |
| MBTI presented as clinical diagnosis | Medical disclaimer | «Diagnostic tool» not claimed |

---

## 4. Operational risks

| Risk | Mitigation |
|------|------------|
| Telegram 409 (polling conflict) | Separate worker process |
| uvicorn reload kills bot | `telegram_worker.py` standalone |
| Large voice files | `PSYCH_TESTING_STT_MAX_BYTES` limit |
| Token cost overrun | Cost tracking; summary-only AI (1 call MBTI) |

---

## 5. Project risks

| Risk | Mitigation |
|------|------------|
| Scope creep into production backend now | Explicit out-of-scope in roadmap |
| 07 PsychTest migration underestimated | Phase 0 reconciliation first |
| MBTI 3 notebooks → 3 production paths | Only structured approved |
| Platform RBAC not ready for Phase 4 | Document P1-P5 as external deps |

---

## 6. Risk review schedule

| Phase | Review trigger |
|-------|----------------|
| Phase 0 exit | Data reconciliation complete |
| Phase 1 exit | Scoring determinism verified |
| Phase 3 exit | Voice E2E test with real STT |
| Phase 4 exit | Security review + RBAC test |

---

## 7. Accepted risks (documented)

| Risk | Acceptance rationale |
|------|---------------------|
| R17 single worker until Phase 4 | Acceptable for MVP Telegram pilot |
| R18 HEXACO legacy mapping | Fix before plugin port, not blocking docs |
| Research notebooks with direct API | Contained in research/ only |

---

## 8. Escalation

| Severity | Action |
|----------|--------|
| High (R1, R2, R9, R10) | Architecture review before implementation |
| Medium | Document in PR; team review |
| Low | Track in backlog |
