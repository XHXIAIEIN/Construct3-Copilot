# RAG Integration & Learning Layer Design

**Date**: 2026-03-13
**Status**: Draft
**Depends on**: [Construct3-RAG: Semantic Chain Design](../../../Construct3-RAG/docs/superpowers/specs/2026-03-13-semantic-chain-design.md)

---

## Architecture Overview

```
用户
  │
  ▼
Copilot（应用层 · 有状态 · 会学习）
  ├─ 意图理解 + Clarification 循环
  ├─ JSON 生成 + ACE Schema 验证
  ├─ 学习层：信号采集 → 经验存储 → 参数更新
  └─ 调用 ↓

RAG（基础设施层 · 无状态 · 专注检索质量）
  ├─ POST /decompose  → 语义分解
  ├─ POST /search     → 原始检索结果（ACE 文档 + 示例项目）
  └─ POST /           → 完整 Q&A（用户答疑场景）
```

**职责划分原则**：
- RAG 只管"找得准"——检索质量、语义理解、知识库覆盖
- Copilot 只管"用得好"——生成质量、用户反馈、经验积累
- RAG 进步 → Copilot 自动受益，无需修改 Copilot 代码

---

## RAG 调用时机

### 1. 意图分解阶段（生成前）

用户描述游戏需求时，先调用 `/decompose`：

```python
# 调用示例
resp = rag_client.post("/decompose", {"query": user_input})
# 返回: query_type, c3_objects, intents, confidence

# 用途：
# - 生成更精准的 Clarification 问题（针对识别出的模糊意图）
# - 预判需要哪些 ACE / 插件（提前准备 Schema 查找范围）
# - confidence 低时多问一轮澄清，避免错误生成
```

### 2. 生成上下文准备（JSON 生成前）

在调用 ACE Schema 查找之后、JSON 生成之前，调用 `/search` 补充语义上下文：

```python
resp = rag_client.post("/search", {
    "query": refined_intent,
    "top_k": 8,
    "collections": ["c3_ace", "c3_examples", "c3_behaviors"]
})
# 返回: 相关 ACE 文档片段 + 示例项目事件表
# 注入到生成 prompt 的 [Context] 部分
```

### 3. 错误解释 / 用户答疑

当用户问"为什么不对"或需要解释某个 C3 概念时，调用 `POST /`：

```python
resp = rag_client.post("/", {"query": user_question})
# 返回: 完整中文解释，带来源引用
# 直接展示给用户
```

---

## 学习层设计

### 信号采集

Copilot 有天然的任务完成反馈信号：

| 信号 | 含义 | 权重 |
|------|------|------|
| 用户直接粘贴，无修改 | 强正反馈 | +1.0 |
| 用户粘贴后追问修改 | 弱正反馈 | +0.3 |
| 用户要求重新生成 | 负反馈 | -0.5 |
| 用户提示 JSON 粘贴失败 | 强负反馈 | -1.0 |
| 对话中断（无响应） | 中性 | 0 |

### 经验存储

每次成功生成后，持久化以下记录：

```json
{
  "timestamp": "2026-03-13T10:00:00",
  "user_query": "做一个平台跳跃游戏",
  "decomposed": {...},          // RAG /decompose 结果
  "rag_context_sources": [...], // 用到的 RAG 检索来源
  "generated_json_hash": "...", // 生成内容的摘要
  "feedback_score": 1.0,        // 采集到的信号
  "clarification_rounds": 1     // 澄清了几轮
}
```

存储位置：`data/experience/YYYY-MM/interactions.jsonl`（按月分片）

### 参数更新（批量，非实时）

每积累 50 条有标签记录后触发：

1. **Few-shot 示例选优**
   - 选 feedback_score ≥ 0.8、clarification_rounds ≤ 1 的记录
   - 提取其 `decomposed` 结果作为新的 Clarification prompt 示例
   - 更新 `SKILL.md` / prompt 文件中的 examples 段落

2. **RAG 查询优化**
   - 分析哪些 `rag_context_sources` 实际被用于生成
   - 将高价值来源模式反馈给 RAG（作为 collection 查询权重参考）
   - *注：RAG 本身不修改，只是调整 Copilot 传入的 collections 参数*

3. **失败模式归档**
   - feedback_score < 0 的记录分析失败原因
   - 分类：ACE 幻觉 / 格式错误 / 意图误解 / RAG 检索偏差
   - 用于更新 `validate_output.py` 的检查规则

---

## 文件规划

| 文件 | 变更 |
|------|------|
| `scripts/rag_client.py` | 新增 — RAG HTTP 客户端（/decompose, /search, /） |
| `scripts/experience_store.py` | 新增 — 交互记录读写 |
| `scripts/learn.py` | 新增 — 批量经验提取 + 参数更新触发 |
| `data/experience/` | 新增目录 — JSONL 格式交互日志 |
| `.agents/skills/construct3-copilot/SKILL.md` | 更新 — 调用 RAG 的工作流步骤 |

---

## 依赖关系

```
Copilot 正常工作：不依赖 RAG（RAG 未启动时降级为仅 Schema 查找）
Copilot 增强模式：需要 RAG server 在 localhost:8765 运行
学习层：完全可选，不影响生成功能
```

**RAG_URL** 通过环境变量配置：
```
RAG_URL=http://localhost:8765   # 默认
```

---

## 成功标准

- RAG 集成后，生成 JSON 的 ACE 准确率提升（减少 Schema 查找失败）
- clarification_rounds 平均值下降（意图分解更准）
- 每 50 次交互后，至少产出 1 个新的高质量 few-shot 示例
- RAG 不可用时，Copilot 功能完全降级但不报错
