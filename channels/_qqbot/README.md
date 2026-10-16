# c3-qqbot

A QQ bot that answers Construct 3 questions, edits a sent project and makes small example projects. It runs a
tool loop over an OpenAI-compatible model (DeepSeek, Zhipu, SiliconFlow or a local Ollama model) with the tools
of a knowledge plugin. Construct3-Copilot records each answer and executes its named Agent-Skills tools.
QQ keeps the conversations, attachments, edit snapshots and file transport.

## Layout

| Path | What |
|------|------|
| `bot.py` | QQ front end (qq-botpy, WebSocket); `--cli "问题"` asks once in the terminal |
| `grader.py` | silent grader of every reply, runs beside the bot, writes `var/reviews/` |
| `start.ps1` | restart bot and grader detached (`-Stop` stops them, `-Ollama` also starts Ollama when it is down) |
| `c3bot/` | the bot itself: `agent.py` the model tool loop, `reply.py` the reply's length and phrasing, `usage.py` token counts, `config.py` the settings from `.env`, `attachments.py` sent files, `edits.py` edit snapshots and undo, `qqfile.py` file upload to QQ (`python -m c3bot.qqfile` sends one by hand), `gpu_yield.py` yields the GPU to another server |
| `plugins/construct3/` | Construct tools, answer checks, the spec builder and editor play tests. Scripts, generator helpers and design guidance come from Construct3-Agent-Skills. Construct3-RAG supplies schema and empty-project data |
| `c3bot/copilot.py` | imports the trusted Copilot checkout, opens task sessions and routes named scripts with their exit codes |
| `scripts/` | `set-*-key.ps1` write an API key into `.env` |
| `.env.example` | every setting the bot reads; copy to `.env` |
| `var/` | everything the bot writes, not committed: `logs/bot/` (`bot.log`, `usage.log`, `botpy.log*`), `logs/grader/`, `logs/ollama/`, `sessions/` (one folder per chat; `_edits/` snapshots, `_new/` made projects, `_pending/` deliveries), `reviews/`, `archive/` (finished runs, each with a README), `backups/`. `C3BOT_DATA` in `.env` puts it elsewhere |

The plugin interface is the list at the top of `plugins/construct3/__init__.py`; `c3bot/agent.py` reads those
names and nothing else of the plugin, so another knowledge base is another folder under `plugins/` and
`C3BOT_PLUGIN` in `.env`.

## Run

1. Clone this repository and, beside it, `Construct3-Copilot`, `Construct3-Agent-Skills`, `Construct3-RAG` and
   `Construct-Example-Projects`. Set their paths in `.env` when they are elsewhere.
2. Make `.venv` and install `qq-botpy`, `openai`, `python-dotenv`, `aiohttp`.
3. Copy `.env.example` to `.env`, fill in the QQ AppID and secret and a model key.
4. Ask once in the terminal, then run the bot:

```bash
.venv/Scripts/python.exe -u bot.py --cli "两个按钮叠在一起，点上面的，下面的也响应了"
```

```powershell
.\start.ps1
```

`var/logs/bot/bot.log` holds every question, tool call and reply; `var/logs/bot/usage.log` one line of token
counts per answer.

`var/runtime/gateway.json` records the gateway process PID and UTC startup time. Its `ready` status and
`ready_at` time record a QQ ready event. Check the process separately to establish whether it is still running.

`C3BOT_COPILOT` selects the trusted Copilot checkout. `C3BOT_SKILLS` selects an Agent-Skills repository, its
`plugin/` folder or its `construct3-agent-plugin` folder. `CONSTRUCT3_RAG` selects the data clone.
The configured model and API key still belong to qqbot. Copilot receives named skill calls through its local API.
Task records and attachment digests live under `var/copilot/`, or under `C3BOT_DATA/copilot/`.
These records describe prepared attachments. QQ upload success is recorded in the bot log.

Messages in one chat run in order, including attachment handling. A second process answering the same session
receives a busy error from Copilot. Failed editor tests keep the previous session project.
Packing requires the current structural check record. A packing failure returns an unavailable-file reply.

The default generation path checks a design and plays it in the editor. `C3BOT_QUICK=1` generates a structural
prototype and adds an unverified-runtime notice to its reply. `C3BOT_EDITOR_CHECK=0` also requires this notice.
Runtime evidence expires when the generated project files change. Edit snapshots cover event sheets, layouts and
`project.c3proj`; the registered edit tool writes only those files.

Run the offline adapter checks with:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```
