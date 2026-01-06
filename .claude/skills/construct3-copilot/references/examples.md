# Construct 3 Copilot Examples

Use these to understand expected input/Intent IR/output relationships.

## Example 1 – Breakout Skeleton

**User request**
> “生成一个基础打砖块框架：球拍跟随鼠标，球碰砖块加分并销毁，掉到底部提示 Game Over。”

**Intent IR**
```json
{
  "gameplay": [
    "mouse-controlled paddle movement",
    "ball collision destroys bricks",
    "score increases per brick",
    "ball falling below layout triggers game over"
  ],
  "ui": ["score text", "game over message"],
  "assets": ["Paddle sprite", "Ball sprite", "Brick sprite", "ScoreText"],
  "open_questions": [],
  "assumptions": [
    "Score increments by +1 per brick",
    "Layout height ~720 and y>650 counts as out"
  ]
}
```

**Output sketch (abbreviated)**
```json
{
  "is-c3-clipboard-data": true,
  "type": "events",
  "items": [
    {"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0", "comment": ""},
    {"eventType": "group", "title": "Paddle Control", "children": [
      {"eventType": "block",
       "conditions": [{"id": "every-tick", "objectClass": "System", "parameters": {}}],
       "actions": [{"id": "set-x", "objectClass": "Paddle", "parameters": {"x": "Mouse.X"}}]}
    ]},
    {"eventType": "group", "title": "Scoring", "children": [
      {"eventType": "block",
       "conditions": [{"id": "on-collision-with-another-object", "objectClass": "Ball", "parameters": {"object": "Brick"}}],
       "actions": [
         {"id": "destroy", "objectClass": "Brick", "parameters": {}},
         {"id": "add-to-eventvar", "objectClass": "System", "parameters": {"variable": "Score", "value": "1"}},
         {"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": "\"Score: \" & Score"}}
       ]}
    ]},
    {"eventType": "group", "title": "Game Over", "children": [
      {"eventType": "block",
       "conditions": [{"id": "compare-y", "objectClass": "Ball", "parameters": {"comparison": 4, "y": "650"}}],
       "actions": [
         {"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": "\"Game Over! Score: \" & Score"}},
         {"id": "destroy", "objectClass": "Ball", "parameters": {}}
       ]}
    ]}
  ],
  "manifests": {
    "variables": [{"name": "Score", "type": "number", "initialValue": "0"}],
    "objects": ["Paddle", "Ball", "Brick", "ScoreText"],
    "assets": ["data:image/png;base64,...", "..."]
  }
}
```

## Example 2 – Platformer Jump Control

**User request**
> “玩家使用左右键移动、空格跳跃，碰到敌人扣血并闪烁。”

**Intent IR**
```json
{
  "gameplay": [
    "platform left/right movement",
    "simulate jump on Space",
    "on collision with enemy subtract health",
    "flash effect when damaged"
  ],
  "ui": ["health text"],
  "assets": ["Player sprite with Platform behavior", "Enemy sprite", "HealthText"],
  "open_questions": ["How much damage per collision?"],
  "assumptions": []
}
```

**Clarification to ask**
> "How many points of health should be removed per collision?"

After receiving “每次 -10”:

**Output sketch**
```json
{
  "is-c3-clipboard-data": true,
  "type": "events",
  "items": [
    {"eventType": "group", "title": "Movement", "children": [
      {"eventType": "block",
       "conditions": [{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 37}}],
       "actions": [{"id": "simulate-control", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"control": "left"}}]},
      {"eventType": "block",
       "conditions": [{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 39}}],
       "actions": [{"id": "simulate-control", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"control": "right"}}]},
      {"eventType": "block",
       "conditions": [{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 32}}],
       "actions": [{"id": "simulate-control", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"control": "jump"}}]}
    ]},
    {"eventType": "group", "title": "Damage Handling", "children": [
      {"eventType": "block",
       "conditions": [{"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Enemy"}}],
       "actions": [
         {"id": "subtract-from-instvar", "objectClass": "Player", "parameters": {"instance-variable": "Health", "value": "10"}},
         {"id": "set-text", "objectClass": "HealthText", "parameters": {"text": "\"HP: \" & Player.Health"}},
         {"id": "flash", "objectClass": "Player", "behaviorType": "Flash", "parameters": {"on-time": "0.1", "off-time": "0.1", "duration": "1"}}
       ]}
    ]}
  ],
  "manifests": {
    "variables": [],
    "objects": ["Player (Platform)", "Enemy", "HealthText"],
    "assets": []
  }
}
```
