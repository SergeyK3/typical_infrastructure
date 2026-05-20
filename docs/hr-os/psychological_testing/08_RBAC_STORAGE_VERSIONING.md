# 08 — RBAC, Storage, Versioning

Версия: Draft 0.1

---

## 1. RBAC

### 1.1. Scope

All psych testing data is **organization-scoped** via `client_id`.

Future permission keys (document only — not implemented):

| Permission | Description |
|------------|-------------|
| `hr.psych_testing.admin` | Configure tests, view all org results, manage item banks |
| `hr.psych_testing.assign` | Assign test sessions to employees/groups |
| `hr.psych_testing.view_own` | Employee views own results |
| `hr.psych_testing.view_team` | Manager views direct reports (department-scoped) |
| `hr.psych_testing.export` | Export reports / PDF |

### 1.2. RBAC matrix (target)

| Action | Employee | Manager | HR Admin | Platform Admin |
|--------|----------|---------|----------|----------------|
| Take assigned test | ✅ | ✅ | ✅ | ✅ |
| View own results | ✅ | ✅ | ✅ | ✅ |
| View team results | ❌ | ✅ (direct reports) | ✅ | ✅ |
| View all org results | ❌ | ❌ | ✅ | ✅ |
| Assign tests | ❌ | ❌ | ✅ | ✅ |
| Configure test banks | ❌ | ❌ | ✅ | ✅ |
| Delete results | ❌ | ❌ | ✅ (policy) | ✅ |

### 1.3. Sensitivity

Psychometric results require **stricter access** than skill assessment scores:

- No public URLs for reports
- Audit log for view/export (future platform audit module)
- Manager access limited to direct reports unless HR policy expands
- Raw voice transcripts — HR admin only (STT audit)

### 1.4. Current platform state

`app/models.py` has `Role`, `Account`, `AccountRole` — basic RBAC without module guards.

Skill Assessment routers use `Depends(get_db)` without role checks today.

Psych Testing Phase 4: implement guards when platform RBAC matures.

---

## 2. Storage strategy

### Phase 0–1: Research (now)

| Asset | Location | Format |
|-------|----------|--------|
| Item banks | `psychological_testing/data/banks/v1/` | CSV, YAML |
| Interpretations | `data/interpretations/v1/` | CSV, YAML |
| Prompts | `data/prompts/v1/` | TXT |
| Session dumps | `research/sessions/` | JSON (experiments) |
| Colab notebooks | `research/mbti/colab/` | `.ipynb` |

No DB. File-based versioning.

### Phase 2–3: Integration prototype

- JSON session files or SQLite dev tables
- Optional local PDF output dir

### Phase 4: Production

Mirror `skill_assessment/infrastructure/db_models.py` pattern:

| Table | Purpose |
|-------|---------|
| `pt_test_sessions` | Main session record |
| `pt_session_responses` | Structured answers + audit |
| `pt_session_scores` | Final scores per scale/axis |
| `pt_telegram_bindings` | Chat ↔ employee ↔ session |
| `pt_telegram_process_context` | Dispatcher state |

Shared SQLite via `app.db` Base — same as `sa_*`.

**Not in core `app/models.py`** — plugin ORM only.

### Attachments / reports

- **Replace** standalone GDrive OAuth from 07 PsychTest
- Use platform storage abstraction (future)
- Phase 4: store PDF reference on session record

### Voice audit storage

Per response (when voice input):

```yaml
telegram_file_id: string      # reference, not necessarily stored blob
raw_transcript: string
stt_provider: openai|mock
stt_duration_ms: int
```

Full audio retention — policy decision (Phase 4); default: file_id reference only.

---

## 3. Versioning strategy

### 3.1. TestDefinition versioning

Semantic version on each test: `test_id` + `version`.

```yaml
test_id: mbti
version: "1.0.0"
```

Session pins version at start:

```yaml
session:
  test_id: mbti
  test_definition_version: "1.0.0"
  item_bank_version: "v1"
```

Scores comparable **only within same version**.

### 3.2. Item bank versioning

Directory-based:

```text
data/banks/v1/    ← current production
data/banks/v2/    ← breaking change (new questions, reworded items)
```

Breaking change triggers:

- New question text affecting psychometric properties
- Scale/pole mapping change
- Weight redistribution (MBTI)

Non-breaking (same v1 patch):

- Typo fixes in display text (document in changelog)
- New optional items appended

### 3.3. Research vs production versions

| Zone | Versioning |
|------|------------|
| `research/` | Unversioned experiments |
| `data/banks/v1/` | Production versioned |
| Colab notebooks | Dated filename + README status |

Promotion: research → `data/banks/vN/` with version bump.

### 3.4. Interpretation and prompt versioning

Co-located with item bank major version:

```text
data/interpretations/v1/mbti.yaml
data/prompts/v1/mbti_summary.txt
```

AI prompt changes that affect output style → minor version bump on TestDefinition.

### 3.5. Migration policy

When `v1` → `v2`:

- Old sessions retain `item_bank_version: v1`
- New sessions use `v2`
- No retroactive rescoring without explicit HR admin action
- Analytics dashboards must filter by version

---

## 4. Multi-tenant considerations

Per HR OS Agreement §5.2:

- Organizations enable/disable psych testing module
- Different test sets per org (future: org-specific TestDefinition overrides)
- Different `num_questions_per_axis` policy per org (MBTI length)

Future table: `pt_org_test_config (client_id, test_id, enabled, config_json)`.

---

## 5. Employee linkage

| Field | Source | Use |
|-------|--------|-----|
| `employee_id` | `app.models.Employee` | Session ownership |
| `client_id` | Organization | Tenant isolation |
| `telegram_id` | `Employee.telegram_id` | Bot binding |
| `assignment_id` | nullable | Link result to position assignment (ERD §8.1) |

Conceptual entity `AssessmentSession` from platform ERD maps to `pt_test_sessions`.

---

## 6. Retention policy (TBD)

Document for future implementation:

| Data type | Suggested retention |
|-----------|---------------------|
| Session scores | Org policy (default: indefinite) |
| Raw transcripts | 90 days (audit) |
| Voice file references | 30 days |
| PDF reports | Match session retention |

Requires legal/compliance review before implementation.

---

## 7. Backup and export

Phase 4:

- Export session + scores as JSON/PDF per RBAC
- Org-scoped export only
- Audit log entry on export

No cross-tenant export.
