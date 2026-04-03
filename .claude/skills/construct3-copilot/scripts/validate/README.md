# validate/ — Validation Scripts

Validates Construct 3 clipboard JSON for format and semantic correctness.
**Must run after every generation. Fail = do not deliver.**

---

## output.py — C3 Clipboard JSON Validator

Three-layer validation + schema cross-check.

**When to use**: After any JSON generation, before delivering to user. No exceptions.
**When NOT to use**: Never skip.

```bash
python3 scripts/validate/output.py '{"is-c3-clipboard-data":true,...}'
python3 scripts/validate/output.py path/to/output.json
echo '...' | python3 scripts/validate/output.py
```

**Exit codes**: 0 = passed, 1 = errors found.

### Validation Layers

**Layer 1 — Structural**
- `is-c3-clipboard-data: true` present
- `type` in valid enum
- `items` is array
- `eventType` in valid enum

**Layer 2 — Known Pitfalls**
- Empty `parameters: {}` (should omit entirely)
- Multiple triggers (`on-*`) in one block
- Trigger conditions in sub-events (children)
- Variable missing `comment` field
- `effectTypes` / `instanceVariables` not arrays
- V1 behavior IDs (`Solid` → should be `solid`)
- Removed behaviors (`DestroyOutsideLayout`)

**Layer 3 — Global Checks**
- SID uniqueness (deduplicate across entire JSON)
- ACE ID existence (cross-check against schema)
- Parameter matching (names and enum values)

### On Validation Failure

1. Read error/warning list
2. Fix JSON
3. Re-run `validate/output.py`
4. Loop until exit 0

**Never deliver JSON when validation reports errors.** Pasting invalid JSON into C3 fails silently or causes hard-to-debug behavior.

---

## Anti-patterns

- "Warnings but no errors — ship it" → warnings must be disclosed in response
- Manual review instead of script validation → script catches more than memory can
- Editing JSON without re-validating → any change can introduce new issues
