# Skill User Simulation Report

- Run at: `2026-02-10 14:32:01`
- Total scenarios: `3`
- Passed scenarios: `2`

## S1 - Complete Game Generation
- User prompt: `做一个打砖块游戏，包含计分和生命值，给我可粘贴 JSON。`
- Intent IR: `{"gameplay": ["breakout loop", "score", "lives"], "ui": ["score text"], "assets": ["Paddle", "Ball", "Brick", "ScoreText", "Mouse"], "open_questions": [], "assumptions": ["single-level prototype"]}`
- Schema checks:
  - `python C:\Users\Administrator\Documents\GitHub\Construct3-Copilot\.agents\skills\construct3-copilot\scripts\query_schema.py search collision` -> rc=0
  - `python C:\Users\Administrator\Documents\GitHub\Construct3-Copilot\.agents\skills\construct3-copilot\scripts\query_schema.py plugin system add-to-eventvar` -> rc=0
- Output validation:
  - `tests\examples\breakout_layout.json` -> ok=True, errors=0, warnings=0
  - `tests\examples\breakout_events.json` -> ok=True, errors=0, warnings=0
- Preflight: rc=0
- Quality gate: passed=True

## S2 - Incremental Feature Update
- User prompt: `在现有项目里加 WASD 8 方向移动，保持事件表可直接粘贴。`
- Intent IR: `{"gameplay": ["WASD movement"], "ui": [], "assets": ["Player", "Keyboard"], "open_questions": [], "assumptions": ["Player has 8Direction behavior"]}`
- Schema checks:
  - `python C:\Users\Administrator\Documents\GitHub\Construct3-Copilot\.agents\skills\construct3-copilot\scripts\query_schema.py behavior 8direction simulate-control` -> rc=1
  - `python C:\Users\Administrator\Documents\GitHub\Construct3-Copilot\.agents\skills\construct3-copilot\scripts\query_schema.py plugin keyboard key-is-down` -> rc=0
- Output validation:
  - `tests\fixtures\events_basic.json` -> ok=True, errors=0, warnings=0
- Preflight: rc=0
- Quality gate: passed=False
  - reason: 1 schema check(s) failed

## S3 - Out-of-Scope/Error Recovery
- User prompt: `加暂停功能（以前示例写了 toggle-boolean）。`
- Intent IR: `{"gameplay": ["pause toggle"], "ui": [], "assets": ["Keyboard"], "open_questions": [], "assumptions": []}`
- Invalid attempt: ok=False, errors=1
- Similar-case lookup rc=0
- Fixed attempt: ok=True, errors=0
- Quality gate: passed=True

## Artifacts
- JSON report: `tests\regressions\skill_user_simulation_report.json`
- This markdown: `tests\regressions\skill_user_simulation_report.md`
