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

## Example 8 – Complete Platformer Character (Keyboard Input)

为简单平台游戏角色生成完整的事件表，响应键盘输入（左、右、跳跃）。

- **Intent IR**
  ```json
  {
    "gameplay": [
      "left arrow moves player left",
      "right arrow moves player right",
      "space bar makes player jump",
      "player has Platform behavior"
    ],
    "ui": [],
    "assets": ["Player (Platform)", "Ground (Solid)", "Keyboard"],
    "open_questions": []
  }
  ```

- **Events JSON (Complete Event Sheet)**
  ```json
  {"is-c3-clipboard-data": true, "type": "events", "items": [
    {"eventType": "comment", "text": "=== Platformer Character Controls ==="},
    {"eventType": "comment", "text": "Player must have Platform behavior. Ground must have Solid behavior."},

    {"eventType": "group", "disabled": false, "title": "Player Movement", "description": "Keyboard controls for platformer character", "isActiveOnStart": true, "children": [
      {"eventType": "block",
       "conditions": [{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 37}}],
       "actions": [
         {"id": "simulate-control", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"control": "left"}},
         {"id": "set-mirrored", "objectClass": "Player", "parameters": {"state": 1}}
       ]},
      {"eventType": "block",
       "conditions": [{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 39}}],
       "actions": [
         {"id": "simulate-control", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"control": "right"}},
         {"id": "set-mirrored", "objectClass": "Player", "parameters": {"state": 0}}
       ]},
      {"eventType": "block",
       "conditions": [{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 32}}],
       "actions": [{"id": "simulate-control", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"control": "jump"}}]}
    ]},

    {"eventType": "group", "disabled": false, "title": "Animation States", "description": "Switch animations based on movement", "isActiveOnStart": true, "children": [
      {"eventType": "block",
       "conditions": [{"id": "is-moving", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}],
       "actions": [{"id": "set-animation", "objectClass": "Player", "parameters": {"animation": "\"Run\"", "from": "current-frame"}}]},
      {"eventType": "block",
       "conditions": [
         {"id": "invert", "objectClass": "System", "parameters": {}},
         {"id": "is-moving", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}
       ],
       "actions": [{"id": "set-animation", "objectClass": "Player", "parameters": {"animation": "\"Idle\"", "from": "current-frame"}}]},
      {"eventType": "block",
       "conditions": [{"id": "is-jumping", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}],
       "actions": [{"id": "set-animation", "objectClass": "Player", "parameters": {"animation": "\"Jump\"", "from": "beginning"}}]},
      {"eventType": "block",
       "conditions": [{"id": "is-falling", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}],
       "actions": [{"id": "set-animation", "objectClass": "Player", "parameters": {"animation": "\"Fall\"", "from": "beginning"}}]}
    ]}
  ]}
  ```

- **Required Setup**:
  1. Player sprite with Platform behavior (set `default-controls: false`)
  2. Ground with Solid behavior
  3. Keyboard object in project
  4. Player animations: "Idle", "Run", "Jump", "Fall"

- **Key Codes**: 37=←, 39=→, 32=Space

## Example 9 – Pause Menu with Resume/Settings/Quit Buttons

完整的暂停菜单系统，包含恢复、设置、退出按钮和可见性切换逻辑。

- **Intent IR**
  ```json
  {
    "gameplay": [
      "ESC toggles pause state",
      "pause sets time scale to 0",
      "resume continues game"
    ],
    "ui": [
      "PauseOverlay darkens screen",
      "PauseTitle shows 'PAUSED'",
      "ResumeButton resumes game",
      "SettingsButton goes to settings",
      "QuitButton returns to main menu"
    ],
    "assets": ["PauseOverlay", "PauseTitle", "ResumeButton", "SettingsButton", "QuitButton", "Keyboard", "Mouse"],
    "open_questions": []
  }
  ```

- **Layout Objects (paste to Layout view)**
  ```json
  {"is-c3-clipboard-data": true, "type": "world-instances", "items": [
    {"type": "PauseOverlay", "properties": {"initially-visible": false}, "world": {"x": 0, "y": 0, "width": 1280, "height": 720, "color": [0, 0, 0, 0.7]}},
    {"type": "PauseTitle", "properties": {"text": "PAUSED", "font": "Arial", "size": 48, "bold": true, "color": [1, 1, 1, 1], "horizontal-alignment": "center", "initially-visible": false}, "world": {"x": 640, "y": 200, "width": 400, "height": 60}},
    {"type": "ResumeButton", "properties": {"text": "Resume", "font": "Arial", "size": 24, "color": [1, 1, 1, 1], "horizontal-alignment": "center", "initially-visible": false}, "world": {"x": 540, "y": 320, "width": 200, "height": 50}},
    {"type": "SettingsButton", "properties": {"text": "Settings", "font": "Arial", "size": 24, "color": [1, 1, 1, 1], "horizontal-alignment": "center", "initially-visible": false}, "world": {"x": 540, "y": 390, "width": 200, "height": 50}},
    {"type": "QuitButton", "properties": {"text": "Quit", "font": "Arial", "size": 24, "color": [1, 1, 1, 1], "horizontal-alignment": "center", "initially-visible": false}, "world": {"x": 540, "y": 460, "width": 200, "height": 50}}
  ], "object-types": [
    {"name": "PauseOverlay", "plugin-id": "TiledBg"},
    {"name": "PauseTitle", "plugin-id": "Text"},
    {"name": "ResumeButton", "plugin-id": "Text"},
    {"name": "SettingsButton", "plugin-id": "Text"},
    {"name": "QuitButton", "plugin-id": "Text"}
  ]}
  ```

- **Events JSON (Complete Pause System)**
  ```json
  {"is-c3-clipboard-data": true, "type": "events", "items": [
    {"eventType": "variable", "name": "IsPaused", "type": "boolean", "initialValue": "false", "comment": "Pause state flag"},

    {"eventType": "group", "disabled": false, "title": "Pause System", "description": "Toggle pause with ESC, show/hide menu", "isActiveOnStart": true, "children": [
      {"eventType": "comment", "text": "Toggle pause on ESC"},
      {"eventType": "block",
       "conditions": [{"id": "on-key-pressed", "objectClass": "Keyboard", "parameters": {"key": 27}}],
       "actions": [{"id": "toggle-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsPaused"}}]},

      {"eventType": "comment", "text": "Show pause menu when paused"},
      {"eventType": "block",
       "conditions": [{"id": "compare-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsPaused", "comparison": 0, "value": "true"}}],
       "actions": [
         {"id": "set-time-scale", "objectClass": "System", "parameters": {"time-scale": "0"}},
         {"id": "set-visible", "objectClass": "PauseOverlay", "parameters": {"visibility": 1}},
         {"id": "set-visible", "objectClass": "PauseTitle", "parameters": {"visibility": 1}},
         {"id": "set-visible", "objectClass": "ResumeButton", "parameters": {"visibility": 1}},
         {"id": "set-visible", "objectClass": "SettingsButton", "parameters": {"visibility": 1}},
         {"id": "set-visible", "objectClass": "QuitButton", "parameters": {"visibility": 1}}
       ]},

      {"eventType": "comment", "text": "Hide pause menu when unpaused"},
      {"eventType": "block",
       "conditions": [{"id": "compare-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsPaused", "comparison": 0, "value": "false"}}],
       "actions": [
         {"id": "set-time-scale", "objectClass": "System", "parameters": {"time-scale": "1"}},
         {"id": "set-visible", "objectClass": "PauseOverlay", "parameters": {"visibility": 0}},
         {"id": "set-visible", "objectClass": "PauseTitle", "parameters": {"visibility": 0}},
         {"id": "set-visible", "objectClass": "ResumeButton", "parameters": {"visibility": 0}},
         {"id": "set-visible", "objectClass": "SettingsButton", "parameters": {"visibility": 0}},
         {"id": "set-visible", "objectClass": "QuitButton", "parameters": {"visibility": 0}}
       ]}
    ]},

    {"eventType": "group", "disabled": false, "title": "Pause Menu Buttons", "description": "Handle button clicks", "isActiveOnStart": true, "children": [
      {"eventType": "block",
       "conditions": [{"id": "on-object-clicked", "objectClass": "Mouse", "parameters": {"mouse-button": "left", "click-type": "clicked", "object-clicked": "ResumeButton"}}],
       "actions": [{"id": "set-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsPaused", "value": "false"}}]},

      {"eventType": "block",
       "conditions": [{"id": "on-object-clicked", "objectClass": "Mouse", "parameters": {"mouse-button": "left", "click-type": "clicked", "object-clicked": "SettingsButton"}}],
       "actions": [{"id": "go-to-layout", "objectClass": "System", "parameters": {"layout": "\"Settings\""}}]},

      {"eventType": "block",
       "conditions": [{"id": "on-object-clicked", "objectClass": "Mouse", "parameters": {"mouse-button": "left", "click-type": "clicked", "object-clicked": "QuitButton"}}],
       "actions": [{"id": "go-to-layout", "objectClass": "System", "parameters": {"layout": "\"MainMenu\""}}]}
    ]},

    {"eventType": "group", "disabled": false, "title": "Button Hover Effects", "description": "Visual feedback on hover", "isActiveOnStart": true, "children": [
      {"eventType": "block",
       "conditions": [{"id": "cursor-is-over-object", "objectClass": "Mouse", "parameters": {"object": "ResumeButton"}}],
       "actions": [{"id": "set-opacity", "objectClass": "ResumeButton", "parameters": {"opacity": "70"}}]},
      {"eventType": "block",
       "conditions": [{"id": "invert", "objectClass": "System", "parameters": {}}, {"id": "cursor-is-over-object", "objectClass": "Mouse", "parameters": {"object": "ResumeButton"}}],
       "actions": [{"id": "set-opacity", "objectClass": "ResumeButton", "parameters": {"opacity": "100"}}]},

      {"eventType": "block",
       "conditions": [{"id": "cursor-is-over-object", "objectClass": "Mouse", "parameters": {"object": "SettingsButton"}}],
       "actions": [{"id": "set-opacity", "objectClass": "SettingsButton", "parameters": {"opacity": "70"}}]},
      {"eventType": "block",
       "conditions": [{"id": "invert", "objectClass": "System", "parameters": {}}, {"id": "cursor-is-over-object", "objectClass": "Mouse", "parameters": {"object": "SettingsButton"}}],
       "actions": [{"id": "set-opacity", "objectClass": "SettingsButton", "parameters": {"opacity": "100"}}]},

      {"eventType": "block",
       "conditions": [{"id": "cursor-is-over-object", "objectClass": "Mouse", "parameters": {"object": "QuitButton"}}],
       "actions": [{"id": "set-opacity", "objectClass": "QuitButton", "parameters": {"opacity": "70"}}]},
      {"eventType": "block",
       "conditions": [{"id": "invert", "objectClass": "System", "parameters": {}}, {"id": "cursor-is-over-object", "objectClass": "Mouse", "parameters": {"object": "QuitButton"}}],
       "actions": [{"id": "set-opacity", "objectClass": "QuitButton", "parameters": {"opacity": "100"}}]}
    ]}
  ]}
  ```

- **Usage**:
  1. Place UI objects on UI layer (parallax 0,0)
  2. Paste events to event sheet
  3. Ensure "Settings" and "MainMenu" layouts exist (or change names)
  4. Add Keyboard and Mouse objects

- **Key Points**:
  - All pause menu objects start invisible (`initially-visible: false`)
  - `set-time-scale: 0` freezes gameplay while keeping UI responsive
  - Button text objects double as clickable buttons
  - Hover effect uses opacity change for visual feedback

## Example 10 – Particle Effect Trigger

在碰撞或销毁时触发粒子效果。

- **Intent IR**
  ```json
  {
    "gameplay": [
      "enemy destroyed triggers explosion particles",
      "particles spawn at enemy position",
      "particles fade out over time"
    ],
    "ui": [],
    "assets": ["Enemy", "ExplosionParticles (Particles)"],
    "open_questions": []
  }
  ```

- **Events JSON (Complete Particle System)**
  ```json
  {"is-c3-clipboard-data": true, "type": "events", "items": [
    {"eventType": "comment", "text": "=== Particle Effect System ==="},

    {"eventType": "group", "disabled": false, "title": "Enemy Death Effects", "description": "Spawn particles when enemies are destroyed", "isActiveOnStart": true, "children": [
      {"eventType": "block",
       "conditions": [{"id": "on-destroyed", "objectClass": "Enemy", "parameters": {}}],
       "actions": [
         {"id": "create-object", "objectClass": "System", "parameters": {"object-to-create": "ExplosionParticles", "layer": "\"Game\"", "x": "Enemy.X", "y": "Enemy.Y"}}
       ]},

      {"eventType": "comment", "text": "Auto-destroy particles after burst"},
      {"eventType": "block",
       "conditions": [{"id": "on-created", "objectClass": "ExplosionParticles", "parameters": {}}],
       "actions": [
         {"id": "set-rate", "objectClass": "ExplosionParticles", "parameters": {"rate": "100"}},
         {"id": "wait", "objectClass": "System", "parameters": {"seconds": "0.5"}},
         {"id": "set-rate", "objectClass": "ExplosionParticles", "parameters": {"rate": "0"}},
         {"id": "wait", "objectClass": "System", "parameters": {"seconds": "2"}},
         {"id": "destroy", "objectClass": "ExplosionParticles", "parameters": {}}
       ]}
    ]}
  ]}
  ```

- **Required Setup**:
  1. Particles object with burst-style settings
  2. Set particle lifetime to ~1-2 seconds
  3. Configure size/speed/gravity in properties

## Example 11 – Audio Playback Control

完整的音频播放系统，包含背景音乐和音效。

- **Intent IR**
  ```json
  {
    "gameplay": [
      "play background music on layout start, loop continuously",
      "play sound effect on collision",
      "mute/unmute audio on button press"
    ],
    "ui": ["MuteButton"],
    "assets": ["Audio", "Keyboard"],
    "open_questions": []
  }
  ```

- **Events JSON (Complete Audio System)**
  ```json
  {"is-c3-clipboard-data": true, "type": "events", "items": [
    {"eventType": "variable", "name": "IsMuted", "type": "boolean", "initialValue": "false", "comment": "Audio mute state"},

    {"eventType": "group", "disabled": false, "title": "Audio System", "description": "Background music and sound effects", "isActiveOnStart": true, "children": [
      {"eventType": "comment", "text": "Start background music on layout"},
      {"eventType": "block",
       "conditions": [{"id": "on-start-of-layout", "objectClass": "System", "parameters": {}}],
       "actions": [
         {"id": "play", "objectClass": "Audio", "parameters": {"audio-file": "bgm", "loop": "looping", "volume": "-10", "tag-optional": "\"bgm\""}}
       ]},

      {"eventType": "comment", "text": "Play sound effect on collision"},
      {"eventType": "block",
       "conditions": [{"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Coin"}}],
       "actions": [
         {"id": "play", "objectClass": "Audio", "parameters": {"audio-file": "coin-pickup", "loop": "not-looping", "volume": "0", "tag-optional": "\"\""}}
       ]},

      {"eventType": "comment", "text": "Toggle mute on M key"},
      {"eventType": "block",
       "conditions": [{"id": "on-key-pressed", "objectClass": "Keyboard", "parameters": {"key": 77}}],
       "actions": [{"id": "toggle-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsMuted"}}]},

      {"eventType": "block",
       "conditions": [{"id": "compare-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsMuted", "comparison": 0, "value": "true"}}],
       "actions": [{"id": "set-master-volume", "objectClass": "Audio", "parameters": {"volume": "-60"}}]},

      {"eventType": "block",
       "conditions": [{"id": "compare-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsMuted", "comparison": 0, "value": "false"}}],
       "actions": [{"id": "set-master-volume", "objectClass": "Audio", "parameters": {"volume": "0"}}]}
    ]},

    {"eventType": "group", "disabled": false, "title": "Audio Transitions", "description": "Fade effects for audio", "isActiveOnStart": true, "children": [
      {"eventType": "comment", "text": "Fade out BGM on game over"},
      {"eventType": "block",
       "conditions": [{"id": "compare-eventvar", "objectClass": "System", "parameters": {"variable": "GameState", "comparison": 0, "value": "2"}}],
       "actions": [
         {"id": "fade-volume", "objectClass": "Audio", "parameters": {"tag": "\"bgm\"", "volume": "-60", "duration": "2", "stopping-mode": "stop"}}
       ]}
    ]}
  ]}
  ```

- **Key Points**:
  - Use tags to control specific audio tracks
  - Volume in dB: 0 = full, -60 = nearly silent
  - `looping` for BGM, `not-looping` for SFX
  - Key code 77 = M

## Example 12 – Array/Dictionary Data-Driven Level

使用 Array 或 Dictionary 数据驱动的关卡生成。

- **Intent IR**
  ```json
  {
    "gameplay": [
      "level data stored in Array",
      "loop through array to spawn objects",
      "different values create different object types"
    ],
    "ui": [],
    "assets": ["Array", "Brick", "Enemy"],
    "open_questions": []
  }
  ```

- **Events JSON (Data-Driven Spawning)**
  ```json
  {"is-c3-clipboard-data": true, "type": "events", "items": [
    {"eventType": "comment", "text": "=== Data-Driven Level Generation ==="},
    {"eventType": "comment", "text": "LevelData array: 0=empty, 1=brick, 2=enemy"},

    {"eventType": "variable", "name": "GridWidth", "type": "number", "initialValue": "10", "comment": "Number of columns"},
    {"eventType": "variable", "name": "GridHeight", "type": "number", "initialValue": "5", "comment": "Number of rows"},
    {"eventType": "variable", "name": "CellSize", "type": "number", "initialValue": "40", "comment": "Size of each cell"},

    {"eventType": "group", "disabled": false, "title": "Level Generation", "description": "Generate level from array data", "isActiveOnStart": true, "children": [
      {"eventType": "block",
       "conditions": [{"id": "on-start-of-layout", "objectClass": "System", "parameters": {}}],
       "actions": [
         {"id": "set-size", "objectClass": "LevelData", "parameters": {"width": "GridWidth", "height": "GridHeight"}}
       ],
       "children": [
         {"eventType": "comment", "text": "Initialize level data (example pattern)"},
         {"eventType": "block",
          "conditions": [{"id": "for", "objectClass": "System", "parameters": {"name": "\"row\"", "start-index": "0", "end-index": "GridHeight-1"}}],
          "actions": [],
          "children": [
            {"eventType": "block",
             "conditions": [{"id": "for", "objectClass": "System", "parameters": {"name": "\"col\"", "start-index": "0", "end-index": "GridWidth-1"}}],
             "actions": [
               {"id": "set-at-xy", "objectClass": "LevelData", "parameters": {"x": "loopindex(\"col\")", "y": "loopindex(\"row\")", "value": "choose(0,0,1,1,1,2)"}}
             ]}
          ]}
       ]},

      {"eventType": "comment", "text": "Spawn objects from level data"},
      {"eventType": "block",
       "conditions": [{"id": "on-function", "objectClass": "System", "parameters": {"name": "\"GenerateLevel\""}}],
       "actions": [],
       "children": [
         {"eventType": "block",
          "conditions": [{"id": "for", "objectClass": "System", "parameters": {"name": "\"y\"", "start-index": "0", "end-index": "GridHeight-1"}}],
          "actions": [],
          "children": [
            {"eventType": "block",
             "conditions": [{"id": "for", "objectClass": "System", "parameters": {"name": "\"x\"", "start-index": "0", "end-index": "GridWidth-1"}}],
             "actions": [],
             "children": [
               {"eventType": "block",
                "conditions": [{"id": "compare-value", "objectClass": "System", "parameters": {"first": "LevelData.At(loopindex(\"x\"),loopindex(\"y\"))", "comparison": 0, "second": "1"}}],
                "actions": [
                  {"id": "create-object", "objectClass": "System", "parameters": {"object-to-create": "Brick", "layer": "\"Game\"", "x": "100 + loopindex(\"x\") * CellSize", "y": "100 + loopindex(\"y\") * CellSize"}}
                ]},
               {"eventType": "block",
                "conditions": [{"id": "compare-value", "objectClass": "System", "parameters": {"first": "LevelData.At(loopindex(\"x\"),loopindex(\"y\"))", "comparison": 0, "second": "2"}}],
                "actions": [
                  {"id": "create-object", "objectClass": "System", "parameters": {"object-to-create": "Enemy", "layer": "\"Game\"", "x": "100 + loopindex(\"x\") * CellSize", "y": "100 + loopindex(\"y\") * CellSize"}}
                ]}
             ]}
          ]}
       ]}
    ]}
  ]}
  ```

- **Required Setup**:
  1. Create Array object named `LevelData`
  2. Set array dimensions in properties or via events
  3. Create Brick and Enemy sprite objects

- **Key Points**:
  - Use 2D Array for grid-based levels
  - `loopindex("name")` gets current loop iteration
  - `LevelData.At(x,y)` reads array value at position
  - `choose()` returns random value from list

## Example 13 – Dictionary-Based Item System

使用 Dictionary 实现物品数据系统。

- **Intent IR**
  ```json
  {
    "gameplay": [
      "item properties stored in Dictionary",
      "lookup item stats by ID",
      "apply item effects on pickup"
    ],
    "ui": [],
    "assets": ["Dictionary", "Item"],
    "open_questions": []
  }
  ```

- **Events JSON (Dictionary Item System)**
  ```json
  {"is-c3-clipboard-data": true, "type": "events", "items": [
    {"eventType": "comment", "text": "=== Dictionary-Based Item System ==="},

    {"eventType": "group", "disabled": false, "title": "Item Data Setup", "description": "Initialize item definitions", "isActiveOnStart": true, "children": [
      {"eventType": "block",
       "conditions": [{"id": "on-start-of-layout", "objectClass": "System", "parameters": {}}],
       "actions": [
         {"id": "add-key", "objectClass": "ItemData", "parameters": {"key": "\"health_potion_heal\"", "value": "50"}},
         {"id": "add-key", "objectClass": "ItemData", "parameters": {"key": "\"health_potion_name\"", "value": "\"Health Potion\""}},
         {"id": "add-key", "objectClass": "ItemData", "parameters": {"key": "\"speed_boost_multiplier\"", "value": "1.5"}},
         {"id": "add-key", "objectClass": "ItemData", "parameters": {"key": "\"speed_boost_duration\"", "value": "5"}},
         {"id": "add-key", "objectClass": "ItemData", "parameters": {"key": "\"speed_boost_name\"", "value": "\"Speed Boost\""}}
       ]}
    ]},

    {"eventType": "group", "disabled": false, "title": "Item Pickup", "description": "Apply item effects on collision", "isActiveOnStart": true, "children": [
      {"eventType": "block",
       "conditions": [
         {"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Item"}},
         {"id": "compare-instvar", "objectClass": "Item", "parameters": {"instance-variable": "ItemType", "comparison": 0, "value": "\"health_potion\""}}
       ],
       "actions": [
         {"id": "add-to-eventvar", "objectClass": "System", "parameters": {"variable": "PlayerHealth", "value": "ItemData.Get(\"health_potion_heal\")"}},
         {"id": "destroy", "objectClass": "Item", "parameters": {}}
       ]},

      {"eventType": "block",
       "conditions": [
         {"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Item"}},
         {"id": "compare-instvar", "objectClass": "Item", "parameters": {"instance-variable": "ItemType", "comparison": 0, "value": "\"speed_boost\""}}
       ],
       "actions": [
         {"id": "set-max-speed", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"max-speed": "330 * ItemData.Get(\"speed_boost_multiplier\")"}},
         {"id": "wait", "objectClass": "System", "parameters": {"seconds": "ItemData.Get(\"speed_boost_duration\")"}},
         {"id": "set-max-speed", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"max-speed": "330"}},
         {"id": "destroy", "objectClass": "Item", "parameters": {}}
       ]}
    ]}
  ]}
  ```

- **Required Setup**:
  1. Create Dictionary object named `ItemData`
  2. Item sprite needs instance variable `ItemType` (string)
  3. Set ItemType to "health_potion" or "speed_boost" for each instance

- **Key Points**:
  - Dictionary stores key-value pairs
  - `ItemData.Get("key")` retrieves value
  - Use naming convention: `{item_id}_{property}`
  - Combine with instance variables for flexible item system
