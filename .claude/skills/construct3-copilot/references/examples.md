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
