# 本地任务运行与 QQ 接入

Copilot 执行已安装的 Construct3-Agent-Skills 脚本，并用 SQLite 保存每次调用的请求和结果。
QQ 机器人负责接收消息、调用模型和回复，Copilot 负责工具执行。

## 运行

需要 Python 3.10+。Copilot 本身只用标准库。
Agent-Skills 中的浏览器工具、检索工具仍需要各自的依赖。
默认从同级的 `Construct3-Agent-Skills` 加载技能。
也可以显式指定仓库、plugin 目录或技能目录：

```powershell
python -m copilot --skills-root ../Construct3-Agent-Skills capabilities
python -m copilot --data .local/copilot run lookup_ace --locale zh-CN -- System wait
python -m copilot --data .local/copilot run print_sheet --project D:/games/demo -- --map
python -m copilot --data .local/copilot task TASK_ID
```

`--` 后的参数交给技能脚本。
通过 `--project` 指定项目，运行器会记录项目路径、uniqueId 和清单文件摘要。
`--request-id` 配合 `--session` 可避免重复执行同一请求。
同一请求号的输入变化会报错。
文件夹打包通过 `--project` 指定来源；运行器不接受打包工具的位置参数 SOURCE。
创建项目时，将目标目录放在技能参数的首位。

运行结果以 JSON 输出。
退出码为 0 表示脚本完成，1 表示执行失败，2 表示配置或参数错误。
退出码 5 表示资源忙，124 表示超时，75 表示重复请求仍在运行。
超时会终止工具进程，并尝试清理它的进程树。
Windows 上，父进程提前退出后留下的独立子进程可能需要人工关闭。

## QQ 配置

适配后的 qqbot 默认查找同级 `Construct3-Copilot` 和 `Construct3-Agent-Skills`。
已有模型、令牌和 QQ 应用配置继续放在 qqbot 自己的 `.env` 中。
需要覆盖路径时，在该文件中设置：

```dotenv
C3BOT_COPILOT=D:/code/Construct3-Copilot
C3BOT_SKILLS=D:/code/Construct3-Agent-Skills
```

先在 qqbot 目录运行离线检查，再启动机器人：

```powershell
.venv/Scripts/python -m unittest discover -s tests -v
.venv/Scripts/python -m c3bot.qq
```

QQ 的一次对话对应一个父任务，各项工具调用是它的子任务。
机器人会话通过消息入口和 Copilot 会话锁串行处理。
发出的项目文件会记录路径、大小和 SHA-256。

## 执行边界

运行器只开放命名的 Construct 工具，不接受任意脚本路径。
它保留技能的标准输出、错误输出和退出码。
项目操作使用进程锁，浏览器工具继续使用技能自己的浏览器锁。
使用同一个数据目录的进程才共享 Copilot 项目锁。

脚本完成只证明该脚本返回成功。
项目检查、编辑器打开、运行验证和实际交互分别由对应工具证明。
QQ 快速模式会明确提示尚未运行验证。
预览超时、非零退出或打包失败时，机器人不会发送项目成品。

任务数据含有问题和工具输出，应保存在 Git 忽略的本地目录。
运行器不读取历史聊天，也不自动把聊天提升为长期记忆。
进程意外退出后，其锁由操作系统释放；遗留 running 记录供人工核查，不会自动重跑。
个性、长期记忆与自主调度由调用方管理。

## Python 接口

```python
from pathlib import Path
from copilot import Runtime

runtime = Runtime(Path("../Construct3-Agent-Skills"), Path(".local/copilot"))
with runtime.session("qqbot", "opaque-session", metadata={"question": "查询 Wait"}) as task:
    result = runtime.run_script("lookup_ace", ["System", "wait"], locale="zh-CN")
    status = "completed" if result["status"] == "completed" else "failed"
    task.finish(status=status, summary=result["reason"] or result["stdout"][:500])
```

会话必须显式提交 completed、failed 或 interrupted 结果。
工具的 busy、timed_out 等状态应由调用方转换为会话失败，并保留原因。
交付文件通过 `task.finish(artifacts=[...])` 计算实际字节的摘要。

C3 工具由 `copilot/providers/construct3/` 提供。宿主通过 `load(runtime, data_dir=..., rag=..., options=...)` 绑定运行位置，再使用返回的工具与生成接口。每个进程绑定一个宿主。
