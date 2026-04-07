# Construct 3 Copilot

**中文** | [English](README.md)

用自然语言生成 Construct 3 剪贴板 JSON，直接粘贴到编辑器。

## 快速开始

```bash
# 1. 克隆 Copilot
git clone https://github.com/XHXIAIEIN/Construct3-Copilot.git
cd Construct3-Copilot

# 2. 自动克隆所有依赖仓库 + 安装 pip 包
bash .claude/plugins/construct3-copilot/scripts/infra/setup.sh

# 3. 启动服务（各开一个终端）
cd ../Construct3-RAG && python src/api.py
cd ../Construct3-Clipboard && python src/api.py

# 4. 运行 Copilot
cd ../Construct3-Copilot && claude
```

> 需要安装 [Claude Code CLI](https://claude.ai/download) 和 Python 3.10+

## 生态系统

Copilot 是一个 Claude Code 插件，依赖两个平级的服务仓库：

**服务**（需要启动）：

| 仓库 | 角色 | 端口 |
|------|------|------|
| [Construct3-Copilot](https://github.com/XHXIAIEIN/Construct3-Copilot) | Claude Code 插件（技能、脚本、编排） | — |
| [Construct3-RAG](https://github.com/XHXIAIEIN/Construct3-RAG) | ACE schema 搜索 + 文档检索 | 8765 |
| [Construct3-Clipboard](https://github.com/XHXIAIEIN/Construct3-Clipboard) | 剪贴板 JSON 生成 + 验证 | 8766 |

**参考资料**（只读，供 skill 使用）：

| 仓库 | 使用者 |
|------|--------|
| [Construct-Addon-SDK](https://github.com/Scirra/Construct-Addon-SDK) | `/c3-addon` — 官方 SDK 模板 |
| [Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | `/c3-search` — 官方游戏示例 |
| [Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | `/c3-addon` — SDK 文档 |

```
../
├── Construct3-Copilot/           ← Claude Code 插件（当前仓库）
├── Construct3-RAG/               ← ACE schema + 文档服务
├── Construct3-Clipboard/         ← JSON 生成 + 验证服务
├── Construct-Addon-SDK/          ← 官方 SDK 模板 (Scirra)
├── Construct-Example-Projects/   ← 官方示例项目 (Scirra)
└── Construct3-Manual/            ← SDK 文档
```

## 使用示例

**完整游戏**
```
> 做一个打砖块游戏，球拍跟随鼠标移动

AI 生成：
- layout.json  → 粘贴到：Project Bar → Layouts
- events.json  → 粘贴到：事件表边缘
```

**添加功能**
```
> 添加 WASD 八方向移动控制

AI 生成事件 JSON → 粘贴到：事件表边缘
```

**UI 片段**
```
> 加一个暂停功能，按 ESC 暂停

AI 生成事件 JSON → 粘贴到：已有事件表
```

## 功能

| 功能 | 说明 |
|------|------|
| 事件 | 游戏逻辑（移动、碰撞、计分、AI、计时器） |
| 对象 | Sprite、Text、TiledBackground + 行为 |
| 布局 | 完整场景（图层 + 实例 + 事件表） |
| 图像 | 占位符 PNG base64（几何图形） |
| 验证 | 粘贴前检查 JSON 格式 |

## 技能

本项目以 [Claude Code 插件](https://docs.anthropic.com/en/docs/claude-code/plugins) 形式工作，提供 4 个技能：

| 技能 | 说明 |
|------|------|
| `/c3-create` | 用自然语言生成剪贴板 JSON |
| `/c3-search` | ACE 查询 + Construct 3 文档搜索 |
| `/c3-validate` | 验证/修复剪贴板 JSON |
| `/c3-addon` | Addon SDK v2 开发指导 |

## 粘贴位置

| 输出类型 | 粘贴到 |
|----------|--------|
| `layouts` | Project Bar → Layouts |
| `object-types` | Project Bar → Object types |
| `events` | 事件表边缘 |
| `world-instances` | 布局视图 |

## 限制

- 不生成 `.c3p` 项目文件
- 不生成可用于生产的美术资源（仅占位图）
- 仅支持 Construct 3

## 项目结构

```
Construct3-Copilot/
├── .claude/
│   └── plugins/
│       └── construct3-copilot/       # Claude Code 插件
│           ├── plugin.json
│           ├── CLAUDE.md
│           ├── skills/               # 4 个技能 (c3-create, c3-search, c3-validate, c3-addon)
│           └── scripts/              # RAG 查询、剪贴板服务、图像生成
├── docs/                             # 设计文档 & 参考资料
├── tests/
│   ├── examples/                     # 完整游戏示例（打砖块、平台跳跃）
│   ├── fixtures/                     # 最小 JSON 夹具（校验）
│   └── regressions/                  # 回归测试用例
└── plans/                            # 实施计划
```

## License

[MIT](LICENSE)
