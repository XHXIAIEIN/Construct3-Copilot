# Construct 3 Copilot — Constraints

Generates paste-ready Construct 3 clipboard JSON. This file defines hard rules that override defaults.

---

## Mandatory ACE Retrieval

**Before using ANY ACE ID in generated JSON, confirm it exists via schema lookup. Never guess from training data.**

```bash
python3 scripts/query/schema.py search {keyword}
python3 scripts/query/schema.py plugin {name} {ace-id}
python3 scripts/query/schema.py behavior {name} {ace-id}
```

Use an ACE ID that `query/schema.py` cannot find = instant failure.

## Known Hallucination Traps

| Wrong (does not exist) | Correct (actual ID) |
|------------------------|---------------------|
| `set-angle-toward-position` | `set-angle` + `angle(x1,y1,x2,y2)` expression |
| `move-toward` | MoveTo behavior or manual displacement |
| `EightDir` | `8Direction` (use display name for behaviorType) |
| `set-speed` (8Direction) | `set-max-speed` |
| `on-click` (no params) | `on-click` requires `mouse-button` parameter |
| `toggle-boolean` | `toggle-boolean-eventvar` |
| `compare-boolean` | `compare-boolean-eventvar` |
| `add-to` | `add-to-eventvar` |

## Mandatory Workflow

```
QUERY → GENERATE → VALIDATE → FIX
```

1. **Query**: `scripts/query/schema.py` for every ACE ID before generation
2. **Generate**: Author JSON or use `scripts/generate/` helpers
3. **Validate**: `scripts/validate/output.py '<json>'` — fail = do not deliver
4. **Fix**: On validation failure, fix and re-validate (loop step 3, max 3 retries)

## Pre-Output Checklist

Before delivering JSON, all items must pass:

- [ ] `"is-c3-clipboard-data": true` present
- [ ] All ACE IDs confirmed via `scripts/query/schema.py` (0 unverified IDs)
- [ ] Variables include `comment` field (can be `""`)
- [ ] String params use nested quotes: `"\"value\""`
- [ ] Behavior actions include `behaviorType` (display name, not behaviorId)
- [ ] Comparison operators are numbers: 0=eq, 1=neq, 2=lt, 3=lte, 4=gt, 5=gte
- [ ] Key codes are numbers: 32=Space, 87=W, 65=A, 37=Left, 39=Right
- [ ] `scripts/validate/output.py` exit code = 0
- [ ] Paste location specified (Event sheet margin / Project Bar / Layout view)
- [ ] Manual verification step included ("After pasting, run layout and confirm X")

## Never Do

- Deliver JSON without running `scripts/validate/output.py`
- Deliver JSON when validation reports errors
- Use an ACE ID not confirmed by schema lookup
- Omit paste instructions from output
