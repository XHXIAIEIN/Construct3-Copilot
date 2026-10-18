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
                 entry.py 平台入口和 --cli，以及启动回执
platforms/       一个文件夹一个平台，__init__.py 是面板读的平台登记表
  qq/            QQ：连接、引用消息、分段回复、文件上传，自带 requirements.txt
panel/           面板：control.py 编排切换，ollama.py、envfile.py、gateway.py 分管
                 Ollama 服务、.env 改写和 QQ 进程；另有接口配置、日志与统计
grader.py        应用自带的回复审查器
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
2. 收到消息时依次调用 `core.chat.Chats` 的 `admit`（每日限额）和 `ask`（调用应用）；按平台的方式发出回复和文件，再调用 `record` 写回答记录。
   连上平台后用 `core.receipt.GatewayReceipt` 记录启动和就绪。
3. 平台自己的依赖写进 `<名字>/requirements.txt`，再在 `channels/requirements.txt` 里加一行 `-r`。
4. 在 `platforms/__init__.py` 登记模块名、显示名和要在面板展示的日志。
5. 面板目前只启停 `PANEL` 指定的一个平台（QQ）。要同时运行多个平台，需要每个平台各有一份启动回执；第二个平台接入时再做。
请求包含消息、会话、历史、附件和通知回调；返回值提供 `text`、`files` 与 `trace`，可以再带一个 `record`。

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
Construct 应用的任务与文件记录保存在 `var/copilot/`。

## 回答记录与统计

每次回答，通道往 `var/logs/<通道>/answers.jsonl` 追加一行，QQ 是 `logs/qq/`，`--cli` 也写在这里，聊天类型记为 `cli`。
通道只写基础字段：时间、通道、聊天类型、会话、用时、模型调用数和词元、收发文件（只记类型和大小，不记文件名）、`handle` 是否正常返回。
应用返回的 `record` 原样放在 `app` 下，通道不解读它。

应用的 `describe()` 声明自己加了哪些字段、怎么统计。`app.py` 启动时把它写到 `var/runtime/app.json`，通道停着时这份声明仍在。
面板只实现原子操作：`count`、`sum`、`avg`、`rate`，加上 `where`（过滤）、`each`（展开列表字段）、`by`（分组）和 `split`（按布尔拆成两份）。
基础指标用同样的写法内置在 `panel/stats.py`。没有 `app.json` 时只显示基础指标，并注明应用未提供统计。
统计从这一版开始记，之前的 `bot.log` 和 `usage.log` 不再参与统计。`usage.log` 照旧写，日志页可以查看。
`QQBOT_DATA` 可设置运行数据目录（相对路径从 `channels/` 算起），`C3BOT_DATA` 兼容已有配置。
