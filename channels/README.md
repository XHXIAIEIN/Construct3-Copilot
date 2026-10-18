# channels

`channels/` 是 Copilot 的消息通道：维护 QQ 连接、传递消息与附件，连接模型，并把消息交给 Construct 应用。
它原来是独立的 qqbot 仓库，2026-10-18 连同提交历史并入 Copilot。

双击 `start.cmd` 打开模型管理页。页面列出本地 Ollama 已安装的模型，支持启动服务、加载模型，以及切换模型并重启 QQ 通道。
模型 API 设置写入 `.env`，服务地址、程序路径与模型目录写入 `var/models.json`。
每次切换都会备份 `.env`。

“API 接口”分组导入 `.env` 中已有的接口，支持添加、编辑、删除与切换。
接口资料放在 `var/apis.json`，密钥通过名称引用 `.env`。编辑时密钥留空会保留原值。
当前使用的接口需先切换后再编辑或删除。删除记录会保留本地备份。

DeepSeek 余额从官方接口查询，显示币种、金额、账户状态和查询时间。
其他接口支持手动标记未知、充足、偏低或耗尽，查询失败会单独显示。
[硅基流动官方公告](https://docs.siliconflow.cn/docs/release-notes/overview)已停止旧的余额查询接口。
添加接口时填写服务地址及模型名称。Claude 官方地址自动使用 Anthropic 原生协议。
自定义服务可在“接口协议”中选择 OpenAI 兼容或 Anthropic 原生。
原生调用遵循 [Anthropic Messages 接口](https://platform.claude.com/docs/en/api/messages/create)，保留工具回合与签名内容。

## 安装与启动

在 Copilot 仓库根目录用 Python 3.10+ 创建 `.venv`，安装通道的依赖：

```powershell
.venv/Scripts/python -m pip install -r channels/requirements.txt
```

复制 `channels/.env.example` 为 `channels/.env`，填写 QQ 凭据。双击 `channels/start.cmd`，选择模型并点击“切换并重启 QQbot”。
`models.example.json` 展示 `var/models.json` 的格式。

```text
start.cmd        日常启动入口，打开面板
settings.py      读取 .env，由入口读一次后显式传下去；数据目录只在这里算，面板和 start.ps1 都用它
app.py           唯一接到 Copilot 的地方：造模型客户端，再造 Construct 应用
model/           模型连接：设置、OpenAI 兼容和 Anthropic 客户端、用量、GPU 让位
core/            与平台无关的部分：chat.py 一问一答（限额、历史、会话目录、回答记录），
                 ack.py 和 ack.json 认出只表示收到的消息，entry.py 平台入口和 --cli，以及启动回执
platforms/       一个文件夹一个平台，__init__.py 是面板读的平台登记表
  qq/            QQ：连接、引用消息、分段回复、文件上传，自带 requirements.txt
panel/           面板：control.py 编排切换，ollama.py、envfile.py、gateway.py 分管
                 Ollama 服务、.env 改写和 QQ 进程；另有接口配置、日志与统计
grader.py        应用自带的回复审查器，读 answers.jsonl 和 turns.jsonl
logs.py          按回合读回答记录：python -m channels.logs
models.example.json  var/models.json 的示例
scripts/         维护命令
.env             本地凭据、模型与应用设置（不进 git）
var/             本地配置、日志、会话与备份（不进 git）
```

离线测试在仓库根目录的 `tests/channels/`。

## 边界

`copilot/` 不 import `channels`；`channels/` 里只有 `app.py` import `copilot`。
`core/` 和 `model/` 不 import 平台和面板，平台之间互不 import，面板只读平台登记表、不碰平台代码。
`tests/channels/test_boundaries.py` 检查这些规则。
其余模块只认得一个有 `handle(request)` 的对象。

## 接入新平台

1. 在 `platforms/` 下建 `<名字>/`，写 `__main__.py`：调用 `core.entry.main("<名字>", run, split=...)`。
   `run` 负责连接平台；`split` 把回复切成该平台能发的段落，`--cli` 也按它打印。
2. 消息一到先调用 `core.chat.Chats` 的 `arrive`，再进 `serialized_sessions` 排队，等同一会话正在做的回答结束：`arrive` 记下到达时间和对方这时看到的那条 bot 消息。
   轮到这条消息时问 `acknowledged`（传入这个 arrival，和 `record` 一样要传聊天类型），是就不回；再依次调用 `admit`（每日限额）和 `ask`（调用应用，也传 arrival）；按平台的方式发出回复和文件，再调用 `record` 写回答记录。
   发送出错时也要调用 `record`：`ask` 返回时回答已经做好并存进历史，回答记录里要有它的用量和工具。
   连上平台后用 `core.receipt.GatewayReceipt` 记录启动和就绪。
3. 平台自己的依赖写进 `<名字>/requirements.txt`，再在 `channels/requirements.txt` 里加一行 `-r`。
4. 在 `platforms/__init__.py` 登记模块名、显示名和要在面板展示的日志。
5. 面板目前只启停 `PANEL` 指定的一个平台（QQ）。要同时运行多个平台，需要每个平台各有一份启动回执；第二个平台接入时再做。
请求包含消息、会话、历史、附件和通知回调；返回值提供 `text`、`files` 与 `trace`，可以再带一个 `record`。

每个聊天最近 3 轮问答存在 `var/sessions/_history/`，最近一张图和它还要跟着的提问数存在 `var/sessions/_images/`，bot 重启后接着用。
两份文件都记着最后一轮的时间（`at`，UTC）。离最后一轮超过 6 小时再问，就不带历史和图，从头开始；没有 `at` 的旧文件也当作过期。
6 小时是 `core/chat.py` 的 `HISTORY_HOURS` 和 `copilot/providers/construct3/application.py` 的 `EARLIER_IMAGE_HOURS`，要改就两处一起改。

只表示收到、懂了或谢谢的消息（「哦哦」「o了」「ojbk」「谢谢」「1」）不回复、不调模型、不算进每日限额，也不进历史。
消息跟着的那条 bot 消息最后一句在问或在提议时照常回答；那条消息里给了方案或选项时，「1」算作选择。带文件或引用了别的消息时总是回答。
词表和这些信号在 `core/ack.json`，改完下一条消息就生效。
“跟着的那条”按消息到达时算，不按轮到它时算。同一会话的回答在做时（建项目要两到十几分钟），新消息要排队。这时它跟着的是这一问发出的忙碌提示（「在做了，要两三分钟，做好发你。」）。提示不问也不提议，所以提示后的「好的」算收到。还没发提示时它不跟着任何消息，因为正在回答的那一问已经回应了更早的回复。
所以建项目时回的「好的」，不会在构建失败后被当成对「……再让我做一次。」的同意，再跑一整轮构建。
没回的消息记进 `skipped.jsonl`，连同它对照的那条 bot 消息的最后一句，用 `python -m channels.logs --skipped` 查，误判的提问能从这里找到（见“回答记录与统计”）。`bot.log` 也记一行 `<聊天> ack: <消息>`。

`app.py` 默认从 Copilot 仓库的相邻目录加载 Construct3-Agent-Skills 和 Construct3-RAG，可用 `.env` 的 `C3BOT_SKILLS` 和 `CONSTRUCT3_RAG` 指定。
Construct 的工具循环、工程解析、生成与交付规则实现在 `copilot/providers/construct3/`。
编辑器脚本由 Agent-Skills 提供，schema 与知识数据由 RAG 提供。

## 维护

在仓库根目录运行：

```powershell
.venv/Scripts/python -m channels.platforms.qq --cli "System Wait 的作用是什么？"
.venv/Scripts/python -m pytest tests/channels
channels/scripts/start.ps1 -Ollama
channels/scripts/start.ps1 -Stop
```

`scripts/start.ps1` 启动 QQ 连接。`-Grader` 同时启动应用提供的回复审查器。
`-Stop` 停止本仓库的连接及审查器。日常操作使用 `start.cmd`。

模型页面日志保存在 `var/logs/models/`，QQ 日志保存在 `var/logs/bot/`。
`var/runtime/gateway.json` 记录 READY 事件、进程身份和正在进行的回答数（`active_answers`）。页面核对进程后显示连接状态；有回答进行时不切换模型。
回执里还有 `code`：bot 启动时 `channels/` 和 `copilot/` 下 Python 文件的指纹，面板自己的代码和 `var/` 不算在内。面板拿它和磁盘上的文件比，不一致就在设置页的 QQbot 一行和模型页标题下提醒重启，鼠标悬停能看到启动后改过哪些文件。没有 `code` 的旧回执，按启动后有没有文件被改过来判断。
Construct 应用的任务与文件记录保存在 `var/copilot/`。

## 回答记录与统计

每次回答，通道往 `var/logs/<通道>/answers.jsonl` 追加一行，QQ 是 `logs/qq/`，`--cli` 也写在这里，聊天类型记为 `cli`。
通道只写基础字段：时间、通道、聊天类型、会话、用时、模型调用数和词元、模型（`model`，取模型接口返回的名字，一轮用了几个就逗号分隔）、收发文件（只记类型和大小，不记文件名）、`handle` 是否正常返回。
`at` 是写这一行的时间，在回复发出之后；`seconds` 只算 `handle`。问题什么时候到的记在 `arrived`（UTC）；它排队等同一会话正在做的回答，等了多少秒记在 `waited`，从到达算到 `handle` 开始。
同一会话没有回答在做时，`waited` 是 0。`--cli` 的行和加这两个字段之前的行没有它们，表示没测，不表示没等。
`bot.log` 的 `usage:` 行末尾也带 `model`，`usage.log` 的格式不变。
应用返回的 `record` 原样放在 `app` 下，通道不解读它。
每行带一个回合号 `turn`。这一轮的问题、回复和完整工具轨迹按回合号写进同一目录的 `turns.jsonl`。超过 32MB 时改名为 `turns.1.jsonl`，只保留这一份旧文件。
`bot.log` 的 `tools:` 行只记工具名的顺序和回合号，以前这一行会塞下整条轨迹，最长 160KB。

没有回答的消息写进同一目录的 `skipped.jsonl`，一条一行：时间、通道、聊天类型、会话、`arrived` 和 `waited`（同上，`waited` 算到判断为止）、原因 `skipped`、消息原文 `message`，以及它到达时跟着的那条 bot 消息的最后一句 `after`。
目前只有一种原因 `ack`，即只表示收到的消息。规则判断那条消息在不在问、在不在提议，看的就是 `after` 这一句；排队的消息这里是忙碌提示，或者为空。
它不进 `answers.jsonl`，因为那里一行就是一次回答，面板统计和应用的审查器都按这个读。跳过的消息既不是回答，也不是失败，混进去会改变回答数、正常返回率、人数和平均用时。
统计不算 `skipped.jsonl`；面板日志页的“QQ 未回答的消息”显示它的原文。

查回答用 `python -m channels.logs`，不要去 grep `bot.log`：

```powershell
python -m channels.logs --since 23:00                     # 每轮一段：时间、问题、收发文件、用量、工具、回复
python -m channels.logs --session E5DB --failed           # 某个会话里失败的回答
python -m channels.logs --skipped                         # 只看没回答的消息和它对照的那条 bot 消息的最后一句
python -m channels.logs --turn <回合号> --grep new_project  # 一轮的完整轨迹，只列匹配的步骤
```

默认列表按时间把没回答的消息排在回合之间，加 `--session` 就只剩同一会话的回合和消息；`--failed` 只列失败的回答，不含这些消息。
`waited` 不少于 3 秒时，标题行在会话后面写 `排队 95s（01:40:12 到）`，到达时间是本地时间。没有回答在做时，消息等不到 1 秒；等 1、2 秒是在等上一条回复发完，所以不显示。
轨迹截断时保留 `->` 后面工具返回的内容，截掉的是前面的参数。`--width 0` 不截。加回合号之前的记录只有计数，问题和回复要去 `bot.log` 里找。

应用的 `describe()` 声明自己加了哪些字段、怎么统计。`app.py` 启动时把它写到 `var/runtime/app.json`，通道停着时这份声明仍在。
面板只实现原子操作：`count`、`sum`、`avg`、`rate`，加上 `where`（过滤）、`each`（展开列表字段）、`by`（分组）和 `split`（按布尔拆成两份）。
基础指标用同样的写法内置在 `panel/stats.py`。没有 `app.json` 时只显示基础指标，并注明应用未提供统计。
统计从这一版开始记，之前的 `bot.log` 和 `usage.log` 不再参与统计。`usage.log` 照旧写，日志页可以查看。
`QQBOT_DATA` 可设置运行数据目录（相对路径从 `channels/` 算起），`C3BOT_DATA` 兼容已有配置。
