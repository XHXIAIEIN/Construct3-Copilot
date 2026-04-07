# Construct 3 Copilot

**中文** | [English](README.md)

用自然语言生成 Construct 3 剪贴板 JSON，直接粘贴到编辑器。

## 快速开始

```bash
git clone https://github.com/XHXIAIEIN/Construct3-Copilot.git
cd Construct3-Copilot
claude
```

> 需要安装 [Claude Code CLI](https://claude.ai/download)

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
