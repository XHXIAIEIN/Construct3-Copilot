# c3-qqbot

QQ bot "Construct 3 Bot": answers Construct 3 questions with the Construct3-RAG tools, edits and makes projects.

| Path | What |
|------|------|
| `bot.py` | QQ front end (qq-botpy, WebSocket); `--cli "问题"` asks once in the terminal |
| `c3bot/` | the bot's code: `agent.py` the model tool loop, `tools.py` the tools and the RAG scripts they run, `acecheck.py` the ACE-name check, `reply.py` the reply's length and phrasing, `usage.py` token counts, `config.py` the settings read from `.env` |
| `c3bot/newproject.py`, `spec_build.py`, `quick_fix.py` | new projects from a spec |
| `c3bot/attachments.py`, `edits.py`, `qqfile.py` | sent files, edit snapshots and undo, file upload to QQ (`python -m c3bot.qqfile` sends one by hand) |
| `c3bot/gpu_yield.py` | unloads the local model while the TTS server generates |
| `grader.py` | silent grader of every reply, writes `reviews/` |
| `start.ps1` | restart bot and grader detached (`-Stop` stops them, `-Ollama` also starts Ollama when it is down) |
| `.env` | keys and model settings; `scripts/set-*-key.ps1` write a key into it |
| `logs/bot/` | `bot.log` (questions, tool calls, replies, warnings), `usage.log` (tokens per answer, QQ and `--cli`), `botpy.log*` (QQ platform connection, rotated daily) |
| `logs/grader/` | `grader.log`: one verdict line per graded reply |
| `logs/ollama/` | Ollama server output when `start.ps1 -Ollama` started it; earlier runs keep a time suffix |
| `sessions/` | one folder per chat; `_edits/` snapshots, `_new/` made projects, `_pending/` deliveries |
| `reviews/` | grader output: `YYYY-MM-DD.md`, `summary.tsv`, `snap/` |
| `specs/` | end-to-end test scripts; their outputs go to `archive/` |
| `backups/<date>/` | `*.bak-*` copies taken before each change until 2026-10-09; since then git history holds the versions |
| `archive/` | finished test sessions and batch runs, each folder with a README, with the `_new/` marks of its sessions |
