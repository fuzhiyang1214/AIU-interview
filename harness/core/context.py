"""harness/core/context.py — 会话上下文

职责：维护消息历史，并在历史过长时做截断，防止超出模型上下文窗口。
输入：user_input / system_prompt
输出：messages 列表（可直接发给模型）

设计要点：模型是"无状态"的 —— 它不记得上一轮说过什么。
          所谓"记忆"其实存在这里，每轮把历史全量重发给它。
"""

DEFAULT_SYSTEM_PROMPT = (
    "你是一个会使用工具的助手。需要信息时调用工具获取，不要凭空猜测。"
    "回答请使用简体中文。"
)


class Context:
    """会话上下文。"""

    def __init__(self, system_prompt: str = DEFAULT_SYSTEM_PROMPT, max_messages: int = 40):
        self.system_prompt = system_prompt
        self.max_messages = max_messages
        self.messages = []

    def reset(self):
        """清空历史。"""
        self.messages = []

    def add_user(self, text: str):
        self.messages.append({"role": "user", "content": text})

    def add_assistant(self, message: dict):
        """记录模型回复（含 tool_calls 的原始 message）。"""
        self.messages.append(message)

    def add_tool(self, content: str):
        """记录一次工具执行结果。"""
        self.messages.append({"role": "tool", "content": content})

    def build(self) -> list:
        """组装成可发送的 messages：system 顶在开头，过长的历史从中间截断。"""
        history = self.messages
        if len(history) > self.max_messages:
            # 保留最早一条和最近若干条，避免上下文窗口被撑爆
            history = history[:1] + history[-(self.max_messages - 1):]
        return [{"role": "system", "content": self.system_prompt}] + history
