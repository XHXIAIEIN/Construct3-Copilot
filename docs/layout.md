# 目录与代码归属

Copilot 保存任务运行器和 Construct 应用。`channels/` 是消息通道，负责 QQ 消息、模型调用、文件传输和面板。

```text
copilot/
  runtime.py, store.py, locks.py   任务、结果与资源锁
  provider.py                    Agent-Skills 脚本执行能力
  providers/construct3/           C3 应用、工具循环、工程解析、生成器、项目编辑和回答记录
channels/
  settings.py                    读取 channels/.env，由入口读一次后显式传下去
  app.py                         唯一接到 copilot 的地方：造模型客户端，再造 Construct 应用
  model/                         模型连接：设置、OpenAI 兼容和 Anthropic 客户端、用量、GPU 让位
  core/                          与平台无关的部分：启动回执、回答记录
  qq/                            QQ 通道：连接、文件上传、终端提问（--cli）
  panel/                         面板：模型切换、接口配置、日志与统计
tests/
  channels/                      通道和面板的离线测试，含边界测试
  e2e/construct3/                经 QQ 通道的终端入口执行的 C3 交互验证脚本
docs/                            接口与使用说明
```

`Construct3-Agent-Skills` 提供编辑器脚本和生成辅助函数。
`Construct3-RAG` 提供 schema、示例索引和空项目模板。
Copilot 的 Construct 插件通过显式参数接收这些安装位置及运行数据目录。
每个进程绑定一个宿主，避免会话之间混用路径。

`copilot/` 不 import `channels`；`channels/` 里只有 `app.py` import `copilot`，由 `tests/channels/test_boundaries.py` 检查。
`channels/app.py` 把模型客户端和运行位置交给 Copilot 的 Construct 应用，其余通道模块只认得一个有 `handle(request)` 的对象。
生成器子进程继承任务编号和同一运行器的数据目录，因此工具调用归属于父任务。

`channels/.env` 保存模型和 QQ 凭据，运行数据在 `channels/var/`：

```text
var/
  models.json                    面板的服务设置
  logs/qq/answers.jsonl          每次回答一行：通道写基础字段，应用的 record 放在 app 下
  logs/bot/                      QQ 通道的文本日志和 usage.log
  runtime/gateway.json           QQ 通道的启动回执，含正在进行的回答数 active_answers
  runtime/app.json               应用的 describe()：它加的字段和统计方式，面板按它计算
  copilot/                       Construct 应用的任务与文件记录
  sessions/                      会话目录
```

完整的消息与执行链路见 [运行框架](framework.md)。
