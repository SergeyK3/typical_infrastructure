# 13 — MBTI Extension Point

Версия: Draft 0.1

---

## 1. Positioning

MBTI — **5-й test plugin** (`tests/mbti/`), не отдельная архитектура и не hardcoded core logic.

```text
shared_engine/dichotomy_scorer.py   ← generic algorithm
tests/mbti/                         ← MBTI content + config
research/mbti/                      ← experimental approaches
```

Removing `tests/mbti/` must not affect PAEI, DISC, HEXACO, Soft Skills.

---

## 2. Three Colab prototypes → Python scripts

| # | Colab (reference) | Python script (реализация) | Status |
|---|-------------------|---------------------------|--------|
| 1 | `structured_questions_scoring.ipynb` | `research/mbti/scripts/dichotomy_scorer.py` | **Production candidate** |
| 2 | `ai_generated_questions.ipynb` | `research/mbti/scripts/ai_generated_mbti.py` | Research only |
| 3 | `process_orchestrator_v3.ipynb` | `research/mbti/scripts/process_orchestrator.py` | Advanced research |

Colab-файлы сохраняются в `research/mbti/colab/` как **источник логики**.  
Runtime — **только Python**; ноутбуки не вызываются из production.

Target layout:

```text
research/mbti/
├── colab/                              # reference .ipynb
│   ├── structured_questions_scoring.ipynb
│   ├── ai_generated_questions.ipynb
│   └── process_orchestrator_v3.ipynb
└── scripts/                            # ★ Python implementation
    ├── dichotomy_scorer.py
    ├── question_selector.py
    ├── ai_generated_mbti.py            # research
    └── process_orchestrator.py         # research
```

---

## 3. Production path — Structured MBTI (Notebook 1)

### 3.1. Design philosophy

From notebook documentation:

- **Objective methodology** — structured questions, not AI interpretation of free text
- 48 validated questions with difficulty weights (1–3)
- Clear A/B options
- Type calculated from scores, not text analysis
- AI used for **final summary only** (1 API call)

Aligns with [HR OS §11](../architecture/HR_Operating_System_Architecture_Agreement.md) and [07_AI_INTEGRATION_BOUNDARIES.md](07_AI_INTEGRATION_BOUNDARIES.md).

### 3.2. Item bank schema

Extract from notebook `QUESTIONS` dict:

```yaml
# data/banks/v1/mbti_items.yaml
items:
  - id: mbti_ei_001
    axis: "E/I"
    text: "При знакомстве с новой командой вы…"
    option_a:
      text: "быстро завожу контакты"
      pole: E
    option_b:
      text: "сначала наблюдаю со стороны"
      pole: I
    weight: 3
  # ... 48 items total (12 per axis max)
```

Axes: `E/I`, `S/N`, `T/F`, `J/P` — 12 items each, weights 1–3.

### 3.3. Question selection

Config in `tests/mbti/definition.yaml`:

```yaml
selection:
  questions_per_axis: 4     # 2→8 total, 12→48 total
  max_per_axis: 12
  sort_by: weight_desc      # prioritize weight=3 questions
  shuffle_axes: true
  seed: 42                  # reproducibility
```

Algorithm → `shared_engine/question_selector.py` (generic).

### 3.4. Scoring — `dichotomy_weighted_choice`

From `calculate_type_from_answers` in notebook 1:

```python
# Conceptual — lives in shared_engine/dichotomy_scorer.py
# Input: answers = [("E/I", "E"), ("S/N", "N"), ("T/F", "T"), ("J/P", "J"), ...]

axis_counts = { "E/I": {"E": 0, "I": 0}, ... }

for axis, pole in answers:
    axis_counts[axis][pole] += 1

for axis, (pos, neg) in axis_mapping.items():
    dominant = pos if counts[pos] >= counts[neg] else neg
    ratio = abs(counts[pos] - counts[neg]) / total
    level = 1 if ratio < 0.3 else (2 if ratio < 0.7 else 3)
    type_code += dominant
```

Output:

```yaml
type_code: INTJ          # один из 16 допустимых типов (см. §3.7)
axes:
  "E/I":
    dominant: I
    level: 2
    counts: { E: 2, I: 3 }
```

### 3.7. Шестнадцать психологических типов (обязательный вывод)

`dichotomy_scorer` формирует `type_code` — **4 буквы** из комбинации E/I + S/N + T/F + J/P.  
Математически возможны **ровно 16** комбинации (2⁴).

| # | type_code | E/I | S/N | T/F | J/P |
|---|-----------|-----|-----|-----|-----|
| 1 | ISTJ | I | S | T | J |
| 2 | ISFJ | I | S | F | J |
| 3 | INFJ | I | N | F | J |
| 4 | INTJ | I | N | T | J |
| 5 | ISTP | I | S | T | P |
| 6 | ISFP | I | S | F | P |
| 7 | INFP | I | N | F | P |
| 8 | INTP | I | N | T | P |
| 9 | ESTP | E | S | T | P |
| 10 | ESFP | E | S | F | P |
| 11 | ENFP | E | N | F | P |
| 12 | ENTP | E | N | T | P |
| 13 | ESTJ | E | S | T | J |
| 14 | ESFJ | E | S | F | J |
| 15 | ENFJ | E | N | F | J |
| 16 | ENTJ | E | N | T | J |

**Validation:** `type_code` после scoring **must** match one key in  
[`psychological_testing/data/interpretations/v1/mbti_16_types.yaml`](../../../psychological_testing/data/interpretations/v1/mbti_16_types.yaml).

**Report structure (user-facing):**

```text
=== ИТОГОВЫЙ ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ ===

Ваш тип личности: INTJ — Стратег (Architect)

ДЕТАЛИ ПРОФИЛЯ:
  E/I: Интроверсия (I) — уровень выраженности 2/3
  S/N: Интуиция (N) — уровень 3/3
  T/F: Мышление (T) — уровень 2/3
  J/P: Суждение (J) — уровень 2/3

Сильные стороны: …
Зоны роста: …

[AI-резюме — опционально, поверх статического профиля типа]
```

Lookup flow:

```text
dichotomy_scorer → type_code
    → mbti_16_types.yaml[type_code]  → name_ru, strengths, growth_areas
    → optional AI summary (prompt includes type_code + axis levels)
```

Core engine **не хранит** 16 описаний — только validates `type_code`; контент в `tests/mbti/` + `data/interpretations/v1/`.

### 3.8. Telegram UX for MBTI

Each question sent as text + A/B buttons + voice hint:

```text
[3/16] Ось: Экстраверсия / Интроверсия

При знакомстве с новой командой вы…

A) быстро завожу контакты
B) сначала наблюдаю со стороны

🎤 Можно ответить голосом («А» или «Б») или нажмите кнопку.
```

Voice: «вариант А» → resolver → pole E  
Button: tap A → pole E (confidence 1.0)

### 3.9. AI summary (post-score only)

```yaml
ai:
  role: summary_only
  prompt: data/prompts/v1/mbti_summary.txt
  model: gpt-4o-mini
  temperature: 0
  gateway: platform_ai_slot
```

Research uses VseGPT (`VSEGPT_API_KEY`, `https://api.vsegpt.ru/v1/`). Production uses platform gateway.

---

## 4. Research path — AI-Generated Questions (Notebook 2)

### 4.1. Approach

- 20 themes per axis in `AXIS_TOPICS`
- `generate_question(axis, topic)` — LLM creates A/B question per topic
- User answers 1/2
- Simple pole count → type_code
- `generate_final_report(mbti)` — full AI report

### 4.2. Why research only

| Issue | Detail |
|-------|--------|
| Non-reproducible | Different questions each run |
| High token cost | LLM call per question |
| No item bank | Cannot audit question content |
| Scoring drift | Questions vary in quality |

### 4.3. Future use

- Generate **candidate** questions for human review
- Promotion to item bank after acmeological validation
- Location: `research/mbti/ai_generated/`

---

## 5. Research path — Process Orchestrator v3 (Notebook 3)

### 5.1. Approach

From notebook header:

- **State machine** of full workday (morning → inbox → planning → … → summary)
- **Episode** = assistant scene → user response → internal JSON log
- **Quality gate** — regenerate weak scenes
- **Axis validation** — axis closed only with ≥2 episodes AND confidence ≥0.70
- **MAX_EPISODES=12** — emergency completion
- **Guard Agent** — regex + LLM classifier, policy reply

### 5.2. Why research only

| Issue | Detail |
|-------|--------|
| Different paradigm | Process discovery, not structured questionnaire |
| LLM in loop | Scene generation + guard + inference |
| Axis confidence ≠ psychometric score | Not validated against structured MBTI |
| Complexity | Separate state machine on top of engine |

### 5.3. scoring_type

`orchestrated_episode` — custom plugin in research only.

Must **not** produce production `type_code` via LLM inference.

Location: `research/mbti/process_orchestrator/`

### 5.4. Potential future

If validated, could become alternative **delivery_mode** for MBTI:

```yaml
delivery_mode: orchestrated   # vs structured
```

Requires separate validation study and HR compliance review.

---

## 6. TestDefinition (production)

```yaml
test_id: mbti
version: "1.0.0"
display_name: "MBTI (акмеологический опросник)"
scoring_type: dichotomy_weighted_choice
delivery_mode: structured        # structured | ai_generated | orchestrated

item_bank: data/banks/v1/mbti_items.yaml

axes:
  - id: "E/I"
    poles: [E, I]
    labels: { E: "Экстраверсия", I: "Интроверсия" }
  - id: "S/N"
    poles: [S, N]
  - id: "T/F"
    poles: [T, F]
  - id: "J/P"
    poles: [J, P]

selection:
  questions_per_axis: 4
  max_per_axis: 12
  sort_by: weight_desc
  shuffle_axes: true
  seed: 42

scoring:
  method: dichotomy_count
  tie_break: first_pole
  expression_levels: [0.3, 0.7]

channel:
  question_format: text_with_buttons
  voice_hint: true
  allowed_inputs: [voice, button, text]

normalization:
  method: none

interpretation: data/interpretations/v1/mbti_16_types.yaml   # все 16 типов

ai:
  role: summary_only
  prompt: data/prompts/v1/mbti_summary.txt
  model: gpt-4o-mini
  temperature: 0
  gateway: platform_ai_slot
```

---

## 7. Shared vs test-specific (MBTI)

| Component | Layer |
|-----------|-------|
| `dichotomy_scorer.py` | shared_engine |
| `question_selector.py` | shared_engine |
| `answer_resolver` framework | shared_engine |
| 48 questions + weights | tests/mbti / data/banks/v1/ |
| MBTI answer_patterns.yaml | tests/mbti |
| AI summary prompt | tests/mbti / data/prompts/v1/ |
| INTJ/ENFP + **все 16 type_code** | data/interpretations/v1/mbti_16_types.yaml |
| Orchestrator state machine | research/mbti/process_orchestrator/ |
| AI question generation | research/mbti/ai_generated/ |

---

## 8. Extension: adding 6th typology test

To add another dichotomy-based test (not MBTI):

1. Copy `tests/_template/`
2. Define axes and poles in definition.yaml
3. Create item bank YAML
4. Set `scoring_type: dichotomy_weighted_choice`
5. No changes to `dichotomy_scorer.py`

MBTI validates this extension point design.

---

## 9. MBTI risks

| Risk | Mitigation |
|------|------------|
| AI-generated questions in prod | `delivery_mode: structured` only in registry |
| Orchestrator LLM → type_code | Research only; structured scorer for prod |
| MBTI used for hiring/fire | HR OS §11; disclaimer; RBAC |
| 48-question bank drift | Version in TestDefinition; session pins version |
| VseGPT in production | Gateway only; research uses direct API |
| User thinks voice AI decides type | Voice hint + deterministic resolver; AI summary labeled separately |

---

## 10. Migration checklist (notebook 1 → Python → plugin)

- [ ] Save notebook → `research/mbti/colab/structured_questions_scoring.ipynb`
- [ ] Implement `research/mbti/scripts/dichotomy_scorer.py` (same logic as Colab)
- [ ] Implement `research/mbti/scripts/question_selector.py`
- [ ] Validate Python output == Colab on fixed test vectors
- [ ] Export `QUESTIONS` dict → `data/banks/v1/mbti_items.yaml`
- [ ] Promote validated scorer → `shared_engine/dichotomy_scorer.py` (Phase 1)
- [ ] Create `answer_patterns.yaml` for A/B voice
- [ ] Populate `mbti_16_types.yaml` — strengths/growth_areas for all 16 types
- [ ] Extract AI summary prompt → `data/prompts/v1/mbti_summary.txt`
- [ ] Register in test_registry with `delivery_mode: structured`

---

## 11. Related documents

- [05_SHARED_SCORING_ARCHITECTURE.md](05_SHARED_SCORING_ARCHITECTURE.md) §6 — dichotomy strategy
- [06_TELEGRAM_INTEGRATION.md](06_TELEGRAM_INTEGRATION.md) — voice + buttons UX
- [07_AI_INTEGRATION_BOUNDARIES.md](07_AI_INTEGRATION_BOUNDARIES.md) — AI summary only
- [09_SHARED_VS_TEST_SPECIFIC.md](09_SHARED_VS_TEST_SPECIFIC.md) §8 — MBTI classification
- [10_IMPLEMENTATION_ROADMAP.md](10_IMPLEMENTATION_ROADMAP.md) — Phase 2 MBTI plugin
