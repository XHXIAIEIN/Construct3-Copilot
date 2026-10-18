# QQbot

QQbot 是 QQ 消息运行环境。它维护 QQ 连接、传递消息与附件，并装载配置的应用。

双击 `start.cmd` 打开模型管理页。页面列出本地 Ollama 已安装的模型，支持启动服务、加载模型，以及切换模型并重启 QQbot。
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

使用 Python 3.10+ 创建 `.venv`，然后安装本仓库：

```powershell
.venv/Scripts/python -m pip install -e .
```

复制 `.env.example` 为 `.env`，填写 QQ 凭据。双击 `start.cmd`，选择模型并点击“切换并重启 QQbot”。
`config/models.example.json` 展示服务配置格式。

```text
start.cmd             日常启动入口
.env                  本地凭据、模型与应用设置
src/qqbot/            QQ 连接、文件传输、应用加载与模型管理
plugins/construct3/   Construct 应用适配器
config/               配置示例
scripts/              维护命令
tests/                宿主离线测试
var/                  本地配置、日志、会话与备份
```

## 装载应用

将适配器放入 `plugins/<应用名>/__init__.py`，在 `.env` 设置 `QQBOT_APP=<应用名>`。
适配器提供 `create_application(home, data_dir, settings)`，返回具有 `handle(request)` 的对象。
请求包含消息、会话、历史、附件和通知回调；返回值提供 `text`、`files` 与 `trace`。
应用决定自己的模型和工作流程。

默认的 `construct3` 适配器加载相邻的 Construct3-Copilot、Construct3-Agent-Skills 和 Construct3-RAG。
可在 `.env` 指定安装位置。Construct 的工具循环、工程解析、生成与交付规则实现在 Copilot 的 `copilot/providers/construct3/`。
编辑器脚本由 Agent-Skills 提供，schema 与知识数据由 RAG 提供。

## 维护

```powershell
.venv/Scripts/python -m qqbot.qq --cli "System Wait 的作用是什么？"
.venv/Scripts/python -m unittest discover -s tests -v
scripts/start.ps1 -Ollama
scripts/start.ps1 -Stop
```

`scripts/start.ps1` 启动 QQ 连接。`-Grader` 同时启动应用提供的回复审查器。
`-Stop` 停止本仓库的连接及审查器。日常操作使用 `start.cmd`。

模型页面日志保存在 `var/logs/models/`，QQ 日志保存在 `var/logs/bot/`。
`var/runtime/gateway.json` 记录 READY 事件和进程身份，页面核对进程后显示连接状态。
Construct 应用的任务与文件记录保存在 `var/copilot/`。QQ 上传结果另记在连接日志中。
`QQBOT_DATA` 可设置运行数据目录，`C3BOT_DATA` 与 `C3BOT_PLUGIN` 兼容已有配置。
