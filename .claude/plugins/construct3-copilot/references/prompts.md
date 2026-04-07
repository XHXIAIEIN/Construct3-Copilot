# Construct 3 Copilot — Prompt Templates

Use these templates at each workflow stage. Adapt variable names but retain structure and output format.

---

## 1. Intent Extraction

```
You are an intent parser for Construct 3 workflows.

Input: {user_request}

Output the Intent IR JSON:
```json
{
  "gameplay": [],
  "ui": [],
  "assets": [],
  "open_questions": [],
  "assumptions": []
}
```

Rules:
- Populate each array with concise strings (1 sentence max per item)
- Include every ambiguity in `open_questions` — 0 missed ambiguities is the target
- `assets` must name every object, behavior, and plugin the output will reference
- If `open_questions` is empty, every detail is unambiguous — verify this claim
```

## 2. Clarification

Use when `open_questions` is non-empty. Ask one question at a time.

```
Outstanding question: {question_text}

Ask: "{concrete question with example options}"
Example: "Should each hit award +1 point, or do you need score multipliers like 2x/3x?"

Wait for answer. Do not generate JSON until all questions are resolved.
```

Stop clarifying when: all Intent IR arrays contain concrete values with no ambiguous terms.

## 3. Generation Planning

```
Confirmed Intent IR:
```json
{intent_ir}
```

Plan:
1. Clipboard type(s): {events | object-types | layouts | ...}
2. Event groups: {list groups by responsibility}
3. Required objects + behaviors: {list with behavior display names}
4. Variables: {name, type, initialValue for each}
5. ImageData needed: {yes/no, specs}

Present plan → get confirmation → generate JSON per clipboard-format.md.
```

Use this template before emitting payloads with >50 events. For small snippets (<10 events), skip planning and generate directly.

## 4. Self-Review

Run through before every delivery:

```
Checklist:
- [ ] `"is-c3-clipboard-data": true` with correct `type`
- [ ] All ACE IDs confirmed via scripts/query/schema.py (0 unverified)
- [ ] Strings quoted ("\"Text\""), comparisons numeric, key codes numeric
- [ ] Behavior actions use display names (confirm via schema.py behavior {name})
- [ ] Variables include comment/type/initialValue
- [ ] scripts/validate/output.py exit code: {0 or error details}
- [ ] Paste location specified
- [ ] Manual verification step included
- [ ] Assumptions restated

If any item fails → fix JSON → re-validate → re-check.
```
