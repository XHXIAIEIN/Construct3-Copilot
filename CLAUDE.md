# Construct3-Copilot

- 查 QQ bot 的某次回答（问了什么、调了哪些工具、回了什么、花了多少），用 `python -m channels.logs`，先看列表，再用 `--turn <回合号>` 展开那一轮。不要 grep `channels/var/logs/bot/bot.log`，旧记录的工具行一行能到 160KB。
- 在 worktree 里，运行数据在 main 那份 checkout 的 `channels/var/`。用 `QQBOT_DATA=<main>/channels/var python -m channels.logs` 去读。
- 格式和字段见 [channels/README.md](channels/README.md) 的“回答记录与统计”。
