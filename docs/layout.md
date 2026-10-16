# 目录与代码归属

Copilot 保存任务运行器和领域插件。QQbot 加载领域插件，负责 QQ 消息、模型调用和文件传输。

```text
copilot/
  runtime.py, store.py, locks.py   任务、结果与资源锁
  provider.py                    Agent-Skills 脚本执行能力
  providers/construct3/           C3 工具、提示、生成器和项目编辑
tests/
  e2e/construct3/                 经 QQ 入口执行的 C3 交互验证脚本
docs/                            接口与使用说明
.claude/                         Claude 客户端插件入口
```

`Construct3-Agent-Skills` 提供编辑器脚本和生成辅助函数。
`Construct3-RAG` 提供 schema、示例索引和空项目模板。
Copilot 的 Construct 插件通过显式参数接收这些安装位置及运行数据目录。
每个进程绑定一个宿主，避免会话之间混用路径。

QQbot 的 `c3bot/knowledge.py` 从配置的 Copilot 安装加载 Construct 插件。
生成器子进程继承任务编号和同一运行器的数据目录，因此工具调用归属于父任务。
QQbot 的 `.env` 保存模型和 QQ 凭据；模型面板的服务设置放在 `var/models.json`。
