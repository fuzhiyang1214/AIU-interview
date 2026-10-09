# core/ — agent 循环层

对应 pi 架构的 **`pi-agent-core`**：整个 Harness 的心脏。

## 文件

| 文件 | 职责 |
|---|---|
| `loop.py` | agent loop —— 整个框架唯一的核心逻辑 |
| `registry.py` | 工具注册表：登记工具、导出 schema |
| `executor.py` | 执行器：跑工具、把异常转成字符串 |
| `events.py` | 事件总线：发布 / 订阅 |
| `context.py` | 会话历史：消息列表 + 截断 |

## 三条铁律

`core` 是这个框架里**唯一不变的部分**。为了保护它，有三条硬规矩：

1. **不出现 `if model == "ollama"`** —— 模型的事交给 `backend/`
2. **不出现具体工具的名字** —— 它只认注册表，不认 `yolo_detect`
3. **不出现 `print`** —— 输出是 UI 的事，core 只 `emit` 事件

一旦这三条被破坏，解耦就破了，出题人规范的第 4 条也就拿不到分。

## 循环长什么样

```
① chat(messages, tools)          带工具表发请求
② if not resp.tool_calls: 收工    唯一的出口
③ 执行工具，结果追加为 tool 消息
④ 回到 ①
```

两个防呆设计：

| 设计 | 为什么 |
|---|---|
| **报错也当结果回灌** | 让模型看到 `工具执行失败：xxx` 后自己换条路，而不是整个程序崩掉 |
| **`max_steps` 上限** | 模型可能反复调同一个工具出不来，必须有硬兜底 |

## 事件表

| 事件 | 触发时机 | 携带数据 |
|---|---|---|
| `turn_start` | 一轮对话开始 | `user_input` |
| `model_response` | 每次模型返回 | `step` `content` `tool_calls` |
| `tool_start` | 准备执行工具 | `name` `arguments` |
| `tool_end` | 工具执行完毕 | `name` `result` |
| `turn_end` | 循环结束 | `content` `steps` |
