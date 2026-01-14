# Construct 3 Copilot

**中文** | [English](README.md)

用自然语言生成 Construct 3 事件表 JSON，直接粘贴到编辑器。

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

## 校验

```bash
python scripts/preflight.py output.json
```

## 粘贴位置

| 输出类型 | 粘贴到 |
|----------|--------|
| `layouts` | Project Bar → Layouts |
| `object-types` | Project Bar → Object types |
| `events` | 事件表边缘 |
| `world-instances` | 布局视图 |


## 项目结构

```
Construct3-Copilot/
├── .claude/
│   └── skills/
│       └── construct3-copilot/    # Claude Code Skill
│           ├── SKILL.md           # 执行指令
│           ├── CLAUDE.md          # 行为约束
│           ├── references/        # 参考文档
│           └── scripts/           # 辅助脚本
├── data/
│   └── schemas/                   # ACE Schema (72 插件 + 31 行为)
└── tests/
    └── fixtures/                  # 最小 JSON 夹具（校验）
```

### ACE Schema

由 `source/zh-CN_R466.csv` 通过 `scripts/generate-schema.js` 生成：

```
data/schemas/
├── index.json          # 概要索引
├── plugins/            # 72 插件 (677 条件, 776 动作, 957 表达式)
├── behaviors/          # 31 行为 (115 条件, 248 动作, 138 表达式)
├── effects/            # 89 特效
└── editor/             # 编辑器配置
```

**统计**: 2,911 ACE (792 条件 + 1,024 动作 + 1,095 表达式)

## License

[MIT](LICENSE)
