# Construct 3 Copilot Prompt Templates

Use these templates to keep interactions consistent. Adapt variable names but retain structure.

## 1. Intent Extraction

````markdown
You are an intent parser for Construct 3 workflows.

Input:
{user_request}

Output the Intent IR JSON matching `intent_schema.json`:
```json
{
  "gameplay": [],
  "ui": [],
  "assets": [],
  "open_questions": []
}
```
- Populate each array with concise strings.
- Include every ambiguity in `open_questions`.
```
````

## 2. Clarification Loop

Use when `open_questions` is non-empty. Ask targeted questions one at a time.

````markdown
Outstanding question: {question_text}

Ask the user:
"{english_question}" (e.g., "Should each hit award +1 point, or do you need score multipliers?")

Wait for the answer before continuing.
````

## 3. Generation Planning & Draft

````markdown
We have confirmed requirements and Intent IR:
```json
{intent_ir}
```

Plan the output:
1. Clipboard payload types needed.
2. Event/logic groups (player control, spawning, scoring, UI, etc.).
3. Required objects, variables, assets (with imageData requirements).
4. Tests/verification steps.

Present the plan to the user for confirmation. After approval, generate JSON following
`clipboard-format.md`, include grouped events, and append resource manifests (variables/assets/mapping).
```
````

## 4. Self-Review & Validation

````markdown
Before responding, confirm all checklist items:

- `"is-c3-clipboard-data": true` with correct `type`.
- Strings quoted (`"\"Text\""`), comparisons numeric, key codes numeric.
- Behavior actions use display names (see behavior-names.md).
- Variables include comment/type/initialValue.
- Layout/object payloads reuse shared imageData indexes.
- Validation script result: {validator_status}. Warnings addressed.
- Resource manifests list every referenced variable/object/asset.
- Paste instructions and manual verification step included.
- Assumptions and clarifications restated.

If any item fails, fix the JSON and rerun validation.
````
