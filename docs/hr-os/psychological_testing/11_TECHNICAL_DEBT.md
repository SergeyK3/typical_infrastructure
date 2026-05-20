# 11 — Technical Debt

Версия: Draft 0.1

Источник: legacy `07 PsychTest` + gap analysis HR OS.

---

## 1. Critical debt (blocks production)

| # | Issue | Location | Impact | Remediation |
|---|-------|----------|--------|-------------|
| D1 | Dual scoring systems | `telegram_test_bot.py` vs `scoring.py` | Inconsistent results | Unify under `scoring_pipeline` |
| D2 | Monolithic bot (1303 lines) | `telegram_test_bot.py` | Unmaintainable | Extract to adapter + engine |
| D3 | In-memory sessions | `user_sessions` dict | Lost on restart, no multi-instance | `pt_test_sessions` (Phase 4) |
| D4 | CSV banks ≠ live questions | `data/bank/` vs bot parsers | Wrong item counts | Reconcile in Phase 2 |
| D5 | No HR OS integration | 07 PsychTest standalone | No multi-tenant | `integration/hr_core.py` |

---

## 2. High debt (quality / correctness)

| # | Issue | Location | Impact | Remediation |
|---|-------|----------|--------|-------------|
| D6 | HEXACO dimension mapping | bot lines ~365 | A/C swap risk | Review against HEXACO model |
| D7 | ScaleNormalizer passthrough | `scale_normalizer.py` | Misleading name, no normalization | Config-driven normalization |
| D8 | interpretation_utils regex | tied to prompt files | Fragile fallback | `interpretation_engine` + YAML |
| D9 | DISC: 4 CSV vs 8 bot items | data vs bot | Incomplete bank | Merge bot questions into CSV |
| D10 | Soft Skills hardcoded in Python | bot | Not data-driven | Item bank YAML |

---

## 3. Medium debt (maintainability)

| # | Issue | Location | Impact | Remediation |
|---|-------|----------|--------|-------------|
| D11 | Monolithic PDF (951 lines) | `enhanced_pdf_report_v2.py` | Hard to extend | Split report_builder sections |
| D12 | Naming: disk_ vs disc_ | prompts, files | Confusion | Rename to disc_ everywhere |
| D13 | Missing report_template.docx | referenced in cli_main | Broken CLI path | Remove or add template |
| D14 | ~200 archived scripts | archive/, tests/archived/ | Noise | Do not migrate |
| D15 | Streamlit in production deps | requirements.txt | Bloat | Dev-only dependency group |
| D16 | Bot handle inconsistency | README vs main() | Wrong bot reference | Single config source |

---

## 4. Security / ops debt

| # | Issue | Location | Impact | Remediation |
|---|-------|----------|--------|-------------|
| D17 | Secrets in repo tree | `.env`, `token.json` | Leak risk | gitignore + secrets manager |
| D18 | Standalone GDrive OAuth | `oauth_google_drive.py` | Not enterprise | Platform storage |
| D19 | No RBAC on results | 07 PsychTest | Anyone with bot access | pt_* + RBAC Phase 4 |
| D20 | No audit trail | in-memory only | Compliance gap | Store transcript + resolved answer |

---

## 5. UX debt (legacy → target)

| # | Legacy | Target | Status |
|---|--------|--------|--------|
| D21 | Inline buttons only | Text + buttons + voice hint | Planned Phase 3 |
| D22 | No voice input | Voice + STT + resolver | Planned Phase 3 |
| D23 | No reprompt on ambiguous | confidence threshold + reprompt | Planned Phase 1 |
| D24 | No voice hint text | Mandatory hint per question | Documented in 06 |

---

## 6. MBTI-specific debt

| # | Issue | Remediation |
|---|-------|-------------|
| D25 | MBTI only in Colab, not integrated | `tests/mbti/` plugin Phase 2 |
| D26 | 3 parallel MBTI approaches | Only structured in production |
| D27 | VseGPT hardcoded in notebooks | Platform gateway in prod |
| D28 | QUESTIONS dict inline in notebook | Extract to `mbti_items.yaml` |

---

## 7. HR OS platform debt (external)

Not owned by psych testing module but blocking Phase 4:

| # | Issue | Owner |
|---|-------|-------|
| P1 | RBAC not enforced on APIs | Platform core |
| P2 | No platform AI gateway | Platform core |
| P3 | No audit log module | Platform core |
| P4 | Psych testing UI placeholder only | Workspace UI |
| P5 | AssessmentSession conceptual only | Platform ERD → pt_* |

---

## 8. Debt paydown priority

```text
Phase 0: D4, D28 (data reconciliation, MBTI extract)
Phase 1: D1, D7, D8 (scoring unification)
Phase 2: D6, D9, D10 (item banks)
Phase 3: D2, D11, D21-D24 (Telegram + PDF)
Phase 4: D3, D17-D20, P1-P5 (production hardening)
```

---

## 9. Do not fix (intentionally discarded)

- `archive/` scripts — historical
- `tests/archived/` — historical
- Streamlit web_app.py — prototype only
- cli_main.py DOCX demo — low priority
- GDrive upload flow — replace, not fix

---

## 10. Tracking

When implementation starts, link debt items to issues/PRs.

Format: `[D#]` in commit messages when addressing debt.

Example: `fix(scoring): unify likert path [D1]`
