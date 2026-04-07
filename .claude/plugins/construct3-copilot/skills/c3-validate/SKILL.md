name: c3-validate
description: >
  Validate Construct 3 clipboard JSON for structural correctness, identify errors, suggest fixes,
  and repair broken JSON. Debug paste failures in the C3 editor.
  验证 Construct 3 剪贴板 JSON 的结构正确性，诊断粘贴错误，修复损坏的 JSON。
triggers:
  keywords:
    - validate clipboard
    - check json
    - verify json
    - paste error
    - parse error
    - fix json
    - repair json
    - debug paste
    - clipboard error
    - 检查
    - 验证
    - 粘贴报错
    - 修复
  intents:
    - validate_c3_json
    - debug_paste_error
---

# Validate — Check and Repair Construct 3 JSON

Read `${CLAUDE_PLUGIN_ROOT}/CLAUDE.md` for known hallucination traps and format rules.

## Workflow

1. Run validation:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate/clipboard_service.py validate '{json}'
```

3. For ACE ID verification:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/rag.py verify {ace-id} --plugin {name}
```

## References

Validation logic is built into `clipboard_service.py`. No external docs needed — the script handles format rules internally.

## Output Format

```
Errors: [list of structural/semantic errors with line-level detail]
Warnings: [list of non-blocking issues]
Fixed JSON: [if repairable, the corrected clipboard JSON]
Fix summary: [what was changed and why]
```

## Memory Context

On skill trigger: find `.c3proj` in the working directory or one level up. If not found, skip memory loading. If found, read its `uniqueId` and check `{project_root}/.claude/memory/memory.md` — if it exists, read it for project context.

## Service Dependencies

Requires Clipboard service (port 8766) for validation, and RAG (port 8765) for ACE ID verification. If offline:
- RAG: `cd ../Construct3-RAG && python src/api.py`
- Clipboard: `cd ../Construct3-Clipboard && python src/api.py`
- First time? Run `bash .claude/plugins/construct3-copilot/scripts/infra/setup.sh` to clone all deps.

## Boundaries

- Does NOT generate new content from scratch (use c3-create for that)
- CAN modify/repair existing JSON to fix errors
- Accepts JSON from clipboard, file, or inline string
