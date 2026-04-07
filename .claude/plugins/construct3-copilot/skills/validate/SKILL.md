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

1. Run local validation:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate/output.py '{json}'
```

2. When Clipboard service is online, also run:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate/clipboard_service.py validate '{json}'
```

3. For ACE ID verification:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/schema.py plugin {name} {ace-id}
```

## References

| When | Load |
|------|------|
| Always | @${CLAUDE_PLUGIN_ROOT}/references/clipboard-format.md |
| Paste errors | @${CLAUDE_PLUGIN_ROOT}/references/troubleshooting.md |

## Output Format

```
Errors: [list of structural/semantic errors with line-level detail]
Warnings: [list of non-blocking issues]
Fixed JSON: [if repairable, the corrected clipboard JSON]
Fix summary: [what was changed and why]
```

## Memory Context

On skill trigger: find `.c3proj` in project root, read its `uniqueId`. If `{project_root}/.claude/memory/memory.md` exists, read it for project context.

## Boundaries

- Does NOT generate new content from scratch (use c3-create for that)
- CAN modify/repair existing JSON to fix errors
- Accepts JSON from clipboard, file, or inline string
