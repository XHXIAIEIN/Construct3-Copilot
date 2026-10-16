# c3-qqbot

A QQ bot that answers Construct 3 questions, edits a sent project and makes small example projects. It runs a
tool loop over an OpenAI-compatible model (DeepSeek, Zhipu, SiliconFlow or a local Ollama model) with the tools
of a knowledge plugin; every reply is checked against the plugin's knowledge before it goes out.

## Layout

| Path | What |
|------|------|
| `bot.py` | QQ front end (qq-botpy, WebSocket); `--cli "问题"` asks once in the terminal |
| `grader.py` | silent grader of every reply, runs beside the bot, writes `var/reviews/` |
| `start.ps1` | restart bot and grader detached (`-Stop` stops them, `-Ollama` also starts Ollama when it is down) |
| `c3bot/` | the bot itself: `agent.py` the model tool loop, `reply.py` the reply's length and phrasing, `usage.py` token counts, `config.py` the settings from `.env`, `attachments.py` sent files, `edits.py` edit snapshots and undo, `qqfile.py` file upload to QQ (`python -m c3bot.qqfile` sends one by hand), `gpu_yield.py` yields the GPU to another server |
| `plugins/construct3/` | the Construct 3 knowledge plugin: the tools and prompts the model gets, the check of its answers (`acecheck.py`), projects from a spec (`newproject.py`, `spec_build.py`, `quick_fix.py`), and `e2e/`: runs that ask the bot for a game and play the result in the editor. It runs the tools and reads the bundled data of [Construct3-Agent-Skills](https://github.com/XHXIAIEIN/Construct3-Agent-Skills) |
| `scripts/` | `set-*-key.ps1` write an API key into `.env` |
| `.env.example` | every setting the bot reads; copy to `.env` |
| `var/` | everything the bot writes, not committed: `logs/bot/` (`bot.log`, `usage.log`, `botpy.log*`), `logs/grader/`, `logs/ollama/`, `sessions/` (one folder per chat; `_edits/` snapshots, `_new/` made projects, `_pending/` deliveries), `reviews/`, `archive/` (finished runs, each with a README), `backups/`. `C3BOT_DATA` in `.env` puts it elsewhere |

The plugin interface is the list at the top of `plugins/construct3/__init__.py`; `c3bot/agent.py` reads those
names and nothing else of the plugin, so another knowledge base is another folder under `plugins/` and
`C3BOT_PLUGIN` in `.env`.

## Run

1. Clone this repository and, beside it, `Construct3-Agent-Skills` and `Construct-Example-Projects`. Set
   `CONSTRUCT3_AGENT_SKILLS` to another tools clone or its `plugin/` folder, and `C3_EXAMPLES` to another examples clone.
   The tools read their plugin bundle by default; `CONSTRUCT3_RAG` selects an optional RAG source-data root.
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

## Offline tool checks

Run `.venv/Scripts/python.exe -m unittest discover -s tests -v` with the tools and examples clones configured.
The checks run ACE, scripting API and guide queries, read an official example, then build, check and pack a scratch project.
They also check the grader command and preview-script paths. Model and QQ calls are mocked or left unstarted.
