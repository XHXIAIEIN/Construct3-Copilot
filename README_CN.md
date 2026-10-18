# Construct 3 Copilot

**中文** | [English](README.md)

Construct 3 的本地任务入口。执行已安装的 Agent-Skills，记录任务结果，并供 QQ 机器人调用。

C3 的工具、提示、生成器与项目编辑实现在 `copilot/providers/construct3/`。
QQbot 从这里加载同一份实现。代码归属见 [目录说明](docs/layout.md)。

## 本地运行与 QQ 接入

需要 Python 3.10+，以及同级的 `Construct3-Agent-Skills` 仓库。
运行所选技能所需的依赖，仍由该技能提供。

```powershell
python -m copilot capabilities
python -m copilot run lookup_ace --locale zh-CN --limit 3000 -- System wait
```

QQ 接入保留机器人的模型配置和消息处理，由 Copilot 执行 Construct 工具。
CLI 默认将任务记录保存在当前目录下的 `.local/copilot`。
可用 `--data` 或 `COPILOT_DATA` 覆盖路径。
配置、任务查询和验证范围见 [运行说明](docs/runtime.md)。

## 工程工具

文件夹工程与 `.c3p` 文件使用
[Construct3-Agent-Skills](https://github.com/XHXIAIEIN/Construct3-Agent-Skills)。
工程工具和 prompts 由它维护，源数据由
[Construct3-RAG](https://github.com/XHXIAIEIN/Construct3-RAG) 维护。

## License

[MIT](LICENSE)
