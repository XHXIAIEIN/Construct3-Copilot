# QQbot

QQ transport, model selection and file delivery for Copilot. Construct tools and project generation load from the configured Construct3-Copilot checkout.

## Open

Double-click `start.cmd` to open the model panel. Select an installed model, load it, or switch and restart QQbot. The panel lists the models reported by the local Ollama service.

Copy `.env.example` to `.env` and fill in QQ credentials before starting the bot. Keep the model API settings in `.env`; the panel saves changes there and backs up the previous file.

The panel creates `var/models.json` with this machine's Ollama address, program path and model directory. Edit that file to change service settings. `config/models.example.json` describes its format.

## Folders

```text
start.cmd       open the model panel
.env            local credentials and bot configuration
c3bot/          QQ transport, model loop and runtime bridge
  model_manager/  panel, model listing and process control
config/         configuration examples
scripts/        maintenance commands
tests/         offline checks
var/            local models.json, logs, sessions and backups
```

Construct-specific tools live in `Construct3-Copilot/copilot/providers/construct3/`. Agent-Skills supplies the editor scripts; Construct3-RAG supplies schemas and project templates.

## Setup and maintenance

Use sibling checkouts of Construct3-Copilot, Construct3-Agent-Skills and Construct3-RAG, or set their paths in `.env`. Create `.venv` and install `qq-botpy`, `openai`, `python-dotenv` and `aiohttp`. Install the dependencies required by the selected Agent-Skills tools.

```powershell
.venv/Scripts/python -m c3bot.qq --cli "System Wait 的作用是什么？"
.venv/Scripts/python -m c3bot.grader --help
.venv/Scripts/python -m unittest discover -s tests -v
```

`scripts/start.ps1 -Ollama` starts the bot and optional reply grader. `scripts/start.ps1 -Stop` stops this checkout's bot and grader. Daily model selection uses `start.cmd`.

The panel writes logs to `var/logs/models/`. QQ conversations go to `var/logs/bot/bot.log`; token usage goes to `usage.log`. `var/runtime/gateway.json` records a ready event and its process PID. The panel also checks that process before showing it as running.

Task records and prepared attachment hashes live in `var/copilot/`, selected by `C3BOT_DATA` when configured. QQ upload success is recorded separately in the bot log. Quick generation marks projects as unverified in the editor. Snapshot-based undo covers event sheets, layouts and the project manifest.
