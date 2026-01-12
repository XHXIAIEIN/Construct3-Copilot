# Construct 3 Copilot Examples

Each scenario pairs a layout + event sheet so you can validate the full clipboard workflow end to end.
Always paste the layout first, then the events, and finally run `scripts/validate_output.py` on the
JSON before sharing with users.

## Example 1 – Breakout (Mouse paddle, restart on click)

- **Intent IR**
  ```json
  {
    "gameplay": [
      "paddle follows mouse while GameState=ready",
      "left-click launches the ball with Bullet speed",
      "brick hits add score and decrement a bricks-left counter",
      "ball falling below the paddle consumes a life (3 total)",
      "win when all bricks are gone, lose when lives hit 0, click to restart"
    ],
    "ui": ["ScoreText shows score + lives + win/lose messaging"],
    "assets": ["Paddle", "Ball (Bullet)", "Brick (Solid)", "Wall TiledBg", "ScoreText", "Mouse"],
    "open_questions": []
  }
  ```
- **Files (under `tests/examples/`)**
  - Layout: [`tests/examples/breakout_layout.json`](../../../../tests/examples/breakout_layout.json)
  - Events: [`tests/examples/breakout_events.json`](../../../../tests/examples/breakout_events.json)
- **Usage**
  1. Copy the layout JSON into the C3 layout bar (creates Paddle/Ball/Brick/Wall/ScoreText/Mouse).
  2. Paste the event JSON into the layout’s event sheet.
  3. Run `python3 .claude/skills/construct3-copilot/scripts/validate_output.py tests/examples/breakout_events.json`.
  4. Manual check: launch the ball, drain lives to see the KO banner, clear all bricks to hit the win
     banner, and click the layout to restart after either ending.

## Example 2 – Platformer (Arrow movement, coins, health gate)

- **Intent IR**
  ```json
  {
    "gameplay": [
      "←/→/Space control a Platform player",
      "collecting coins destroys the coin and adds score",
      "enemy contact subtracts HP and disables input when HP ≤ 0"
    ],
    "ui": ["single HUD text showing Score + HP, KO reminder when health hits 0"],
    "assets": ["Sky TiledBg", "Ground TiledBg (Solid)", "Player (Platform)", "Coin", "Enemy", "ScoreText", "Keyboard"],
    "open_questions": []
  }
  ```
- **Files (under `tests/examples/`)**
  - Layout: [`tests/examples/platformer_layout.json`](../../../../tests/examples/platformer_layout.json)
  - Events: [`tests/examples/platformer_events.json`](../../../../tests/examples/platformer_events.json)
- **Usage**
  1. Paste the layout JSON (includes small seamless tiles for `Sky` to avoid stretched gradients).
  2. Paste the event JSON and verify ACE IDs via the schema if prompted.
  3. Run `python3 .claude/skills/construct3-copilot/scripts/validate_output.py tests/examples/platformer_events.json`.
  4. Manual check: move with ←/→, jump with Space, pick coins to raise score, collide with the enemy
     until HP reaches 0, confirm controls disable and the HUD instructs you to press `R` to restart.

## Example 3 – Top-Down Shooter (WASD + Mouse aim)

- **Intent IR**
  ```json
  {
    "gameplay": [
      "WASD moves the player with 8Direction behavior",
      "player sprite rotates to face Mouse position",
      "left-click spawns a Bullet from player that travels toward Mouse",
      "bullets destroy enemies on collision, add score",
      "enemy spawns every 2 seconds at random edge position",
      "enemy contact with player reduces HP, game over when HP ≤ 0"
    ],
    "ui": ["ScoreText top-left", "HPText top-right"],
    "assets": ["Player (8Direction)", "Bullet (Bullet)", "Enemy", "ScoreText", "HPText", "Mouse", "Keyboard"],
    "visual_style": {
      "palette": ["green", "red", "yellow"],
      "resolution": "32x32",
      "shape_language": "geometric"
    },
    "open_questions": []
  }
  ```
- **Key Event Snippets**
  ```json
  // Player rotation toward mouse
  {
    "eventType": "block",
    "conditions": [{"id": "every-tick", "objectClass": "System", "parameters": {}}],
    "actions": [{"id": "set-angle-toward-position", "objectClass": "Player", "parameters": {"x": "Mouse.X", "y": "Mouse.Y"}}]
  }

  // Fire bullet on click
  {
    "eventType": "block",
    "conditions": [{"id": "on-click", "objectClass": "Mouse", "parameters": {"button": 0}}],
    "actions": [{"id": "spawn-another-object", "objectClass": "Player", "parameters": {"object": "Bullet", "imagePoint": 0}}]
  }

  // Enemy spawn timer
  {
    "eventType": "block",
    "conditions": [{"id": "every-x-seconds", "objectClass": "System", "parameters": {"interval": "2"}}],
    "actions": [{"id": "create-object", "objectClass": "System", "parameters": {"objectToCreate": "Enemy", "layer": "\"Main\"", "x": "choose(0, 640)", "y": "choose(0, 480)"}}]
  }
  ```

## Example 4 – UI Snippet (Pause Menu)

适用于只需要部分事件片段而非完整游戏的场景。

- **Intent IR**
  ```json
  {
    "gameplay": ["press Escape toggles pause state", "pause freezes all game objects"],
    "ui": ["PauseText centered, visible only when paused"],
    "assets": ["PauseText", "Keyboard"],
    "open_questions": []
  }
  ```
- **Events JSON (paste into existing event sheet)**
  ```json
  {"is-c3-clipboard-data": true, "type": "events", "items": [
    {"eventType": "variable", "name": "IsPaused", "type": "boolean", "initialValue": "false", "comment": "Pause state flag"},
    {"eventType": "block",
     "conditions": [{"id": "on-key-pressed", "objectClass": "Keyboard", "parameters": {"key": 27}}],
     "actions": [{"id": "toggle-boolean", "objectClass": "System", "parameters": {"variable": "IsPaused"}}]},
    {"eventType": "block",
     "conditions": [{"id": "compare-boolean", "objectClass": "System", "parameters": {"variable": "IsPaused", "value": "true"}}],
     "actions": [
       {"id": "set-time-scale", "objectClass": "System", "parameters": {"timeScale": "0"}},
       {"id": "set-visible", "objectClass": "PauseText", "parameters": {"visibility": 1}}
     ]},
    {"eventType": "block",
     "conditions": [{"id": "compare-boolean", "objectClass": "System", "parameters": {"variable": "IsPaused", "value": "false"}}],
     "actions": [
       {"id": "set-time-scale", "objectClass": "System", "parameters": {"timeScale": "1"}},
       {"id": "set-visible", "objectClass": "PauseText", "parameters": {"visibility": 0}}
     ]}
  ]}
  ```
- **Usage**: 直接粘贴到已有事件表，需要项目中已存在 `PauseText` 和 `Keyboard` 对象。

## Example 5 – Minimal Collision Template

最小化的碰撞检测模板，用于快速复制修改。

- **Events JSON**
  ```json
  {"is-c3-clipboard-data": true, "type": "events", "items": [
    {"eventType": "block",
     "conditions": [{"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Coin"}}],
     "actions": [
       {"id": "add-to", "objectClass": "System", "parameters": {"variable": "Score", "value": "1"}},
       {"id": "destroy", "objectClass": "Coin", "parameters": {}}
     ]}
  ]}
  ```
- **替换规则**:
  - `Player` → 碰撞发起对象
  - `Coin` → 碰撞目标对象
  - `Score` → 要修改的变量
  - `add-to` / `destroy` → 需要的动作

## Example 6 – Script Integration (Event + JavaScript)

在事件表中嵌入 JavaScript 脚本块。

- **Intent IR**
  ```json
  {
    "gameplay": ["function that adds two numbers using JavaScript"],
    "ui": [],
    "assets": [],
    "open_questions": []
  }
  ```
- **Events JSON (with script action)**
  ```json
  {"is-c3-clipboard-data": true, "type": "events", "items": [
    {"eventType": "comment", "text": "Script integration example: Call JavaScript function from events"},
    {"eventType": "group", "disabled": false, "title": "Script Functions", "description": "Event functions that wrap JavaScript code", "isActiveOnStart": true, "children": [
      {
        "functionName": "add",
        "functionDescription": "Add two numbers via JavaScript.",
        "functionCategory": "",
        "functionReturnType": "number",
        "functionCopyPicked": false,
        "functionIsAsync": false,
        "functionParameters": [
          {"name": "firstNumber", "type": "number", "initialValue": "0", "comment": ""},
          {"name": "secondNumber", "type": "number", "initialValue": "0", "comment": ""}
        ],
        "eventType": "function-block",
        "conditions": [],
        "actions": [
          {"type": "script", "language": "javascript", "script": ["runtime.setReturnValue(localVars.firstNumber + localVars.secondNumber);"]}
        ]
      },
      {
        "functionName": "distance",
        "functionDescription": "Calculate distance between two points.",
        "functionCategory": "",
        "functionReturnType": "number",
        "functionCopyPicked": false,
        "functionIsAsync": false,
        "functionParameters": [
          {"name": "x1", "type": "number", "initialValue": "0", "comment": ""},
          {"name": "y1", "type": "number", "initialValue": "0", "comment": ""},
          {"name": "x2", "type": "number", "initialValue": "0", "comment": ""},
          {"name": "y2", "type": "number", "initialValue": "0", "comment": ""}
        ],
        "eventType": "function-block",
        "conditions": [],
        "actions": [
          {"type": "script", "language": "javascript", "script": [
            "const dx = localVars.x2 - localVars.x1;",
            "const dy = localVars.y2 - localVars.y1;",
            "runtime.setReturnValue(Math.sqrt(dx * dx + dy * dy));"
          ]}
        ]
      }
    ]}
  ]}
  ```
- **Usage**:
  - 粘贴后可在表达式中使用 `Functions.add(1, 2)` 或 `Functions.distance(0, 0, 100, 100)`
  - 脚本通过 `localVars` 访问函数参数
  - 使用 `runtime.setReturnValue()` 返回结果

## Example 7 – Script Action for Runtime Access

直接在事件中使用脚本访问运行时 API。

- **Events JSON**
  ```json
  {"is-c3-clipboard-data": true, "type": "events", "items": [
    {"eventType": "variable", "name": "PlayerSpeed", "type": "number", "initialValue": "0", "comment": "Calculated speed"},
    {"eventType": "block",
     "conditions": [{"id": "every-tick", "objectClass": "System", "parameters": {}}],
     "actions": [
       {"type": "script", "language": "javascript", "script": [
         "const player = runtime.objects.Player.getFirstInstance();",
         "if (player) {",
         "  const vx = player.behaviors.Platform?.vectorX ?? 0;",
         "  const vy = player.behaviors.Platform?.vectorY ?? 0;",
         "  localVars.PlayerSpeed = Math.sqrt(vx * vx + vy * vy);",
         "}"
       ]}
     ]}
  ]}
  ```
- **Key Points**:
  - `runtime.objects.Player.getFirstInstance()` 获取对象实例
  - `runtime.dt` 获取帧间隔时间
  - `localVars` 读写事件表局部变量
  - 脚本可以包含多行，每行是数组中的一个字符串
  - 参考 `references/runtime-api.md` 了解完整 API
