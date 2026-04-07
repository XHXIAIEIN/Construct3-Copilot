# validate/ — Validation Scripts

Validation of Construct 3 clipboard JSON is handled by `clipboard_service.py validate`.

```bash
python3 scripts/generate/clipboard_service.py validate '{json}'
python3 scripts/generate/clipboard_service.py validate path/to/output.json
```

**Exit codes**: 0 = passed, non-zero = errors found.

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
- V1 behavior IDs (`Solid` -> should be `solid`)
- Removed behaviors (`DestroyOutsideLayout`)

**Layer 3 — Global Checks**
- SID uniqueness (deduplicate across entire JSON)
- ACE ID existence (cross-check against schema)
- Parameter matching (names and enum values)

### On Validation Failure

1. Read error/warning list
2. Fix JSON
3. Re-run `clipboard_service.py validate`
4. Loop until exit 0

**Never deliver JSON when validation reports errors.** Pasting invalid JSON into C3 fails silently or causes hard-to-debug behavior.

---

## Anti-patterns

- "Warnings but no errors -- ship it" -> warnings must be disclosed in response
- Manual review instead of script validation -> script catches more than memory can
- Editing JSON without re-validating -> any change can introduce new issues
