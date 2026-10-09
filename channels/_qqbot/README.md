# c3-qqbot

QQ bot "Construct 3 Bot": answers Construct 3 questions with the Construct3-RAG tools, edits and makes projects.

| Path | What |
|------|------|
| `bot.py` | QQ front end (qq-botpy, WebSocket); `--cli "问题"` asks once in the terminal |
| `agent.py` | model tool loop, voice, reply checks |
| `newproject.py`, `spec_build.py`, `quick_fix.py` | new projects from a spec |
| `attachments.py`, `edits.py`, `qqfile.py` | sent files, edit snapshots and undo, file upload to QQ |
| `gpu_yield.py` | unloads the local model while the TTS server generates |
| `grader.py` | silent grader of every reply, writes `reviews/` |
| `start.ps1` | restart bot and grader detached (`-Stop` stops them, `-Ollama` also starts Ollama when it is down) |
| `.env` | keys and model settings |
| `logs/bot/` | `bot.log` (questions, tool calls, replies, warnings), `usage.log` (tokens per answer, QQ and `--cli`), `botpy.log*` (QQ platform connection, rotated daily) |
| `logs/grader/` | `grader.log`: one verdict line per graded reply |
| `logs/ollama/` | Ollama server output when `start.ps1 -Ollama` started it; earlier runs keep a time suffix |
| `sessions/` | one folder per chat; `_edits/` snapshots, `_new/` made projects, `_pending/` deliveries |
| `reviews/` | grader output: `YYYY-MM-DD.md`, `summary.tsv`, `snap/` |
| `specs/` | end-to-end test scripts and their outputs |
| `backups/<date>/` | `*.bak-*` copies taken before each change |
| `archive/` | finished test sessions |
