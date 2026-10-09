"""harness/core/loop.py — agent loop（整个 Harness 的心脏）

职责：驱动"请求 → 工具 → 回灌 → 再请求"这一圈，直到模型不再开申请单。
输入：用户输入、Gateway、Registry、Executor、EventBus、Context
输出：模型的最终文本回复

结构（一轮）：
  ① chat(messages, tools)      发请求，带工具表
  ② if not resp.tool_calls     没有申请单 → 收工，返回 content
  ③ 逐个执行工具，结果追加为 tool 消息
  ④ 回到 ①

两条硬规矩：
  · 循环唯一的出口是"模型不再开单"，工具调完不算结束
  · max_steps 是防死循环的兜底 —— 模型可能反复调同一个工具
"""


class AgentLoop:
    """agent 循环。它不聪明，聪明的是模型；它只负责把循环转起来。"""

    def __init__(self, gateway, registry, executor, bus, context, max_steps: int = 8):
        self.gateway = gateway
        self.registry = registry
        self.executor = executor
        self.bus = bus
        self.context = context
        self.max_steps = max_steps

    def run(self, user_input: str) -> str:
        """跑完一整轮对话，返回最终回复。"""
        self.context.add_user(user_input)
        self.bus.emit("turn_start", user_input=user_input)

        for step in range(self.max_steps):
            messages = self.context.build()
            resp = self.gateway.chat(messages, self.registry.schemas())
            self.bus.emit("model_response", step=step, content=resp.content,
                          tool_calls=resp.tool_calls)

            if not resp.has_tool_calls:
                # 模型不开单了 → 收工
                self.context.add_assistant({"role": "assistant", "content": resp.content})
                self.bus.emit("turn_end", content=resp.content, steps=step + 1)
                return resp.content

            # 把模型的"申请单"记进上下文（重新组装成 Ollama 认的格式）
            self.context.add_assistant({
                "role": "assistant",
                "content": resp.content,
                "tool_calls": [
                    {"function": {"name": c.name, "arguments": c.arguments}}
                    for c in resp.tool_calls
                ],
            })

            for call in resp.tool_calls:
                self.bus.emit("tool_start", name=call.name, arguments=call.arguments)
                result = self.executor.run(call)          # 异常已被 executor 转成字符串
                self.bus.emit("tool_end", name=call.name, result=result)
                self.context.add_tool(result)             # 报错也回灌，让模型自己纠偏

        msg = f"达到最大轮次上限（{self.max_steps}），已停止。"
        self.bus.emit("turn_end", content=msg, steps=self.max_steps)
        return msg
