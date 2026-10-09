# backend/ — LLM 网关层

对应 pi 架构的 **`pi-ai`** 层：把"和大模型说话"这件事抽象成一个统一接口。

## 文件

| 文件 | 职责 |
|---|---|
| `gateway.py` | 抽象基类 `Gateway` + 数据结构 `ChatResponse` / `ToolCall` |
| `ollama_provider.py` | 本机 Ollama 的实现（`/api/chat`） |

## 为什么要有这一层

**变化隔离**：模型服务是会变的（今天 Ollama、明天 OpenAI、后天 Dify），但这个变化
不应该传染到 `core/`。所以 `core` 只依赖 `Gateway` 这个抽象类。

由此得出一条硬规矩：

> **`core/` 里不允许出现 `if model == "ollama"` 这类判断。**

## 怎么加一个新模型服务

1. 新建 `xxx_provider.py`，继承 `Gateway`，实现 `chat(messages, tools) -> ChatResponse`
2. 在 `main.py` 里把 `OllamaProvider(...)` 换成 `XxxProvider(...)`

`core/` 一个字都不用改。

## 数据结构

```python
ChatResponse(
    content="...",                                  # 模型的文本回复
    tool_calls=[ToolCall(id, name, arguments)],     # 模型开出的申请单
)
```

`ChatResponse.has_tool_calls` 就是 agent loop 的循环开关。
