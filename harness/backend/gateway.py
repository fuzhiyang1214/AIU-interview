"""harness/backend/gateway.py — LLM 网关抽象层（≈ pi 架构的 pi-ai）

职责：定义"和大模型对话"的统一接口。上层 core 只认这个接口，不认任何具体模型服务。
输入：messages（消息列表）、tools（工具 schema 列表）
输出：ChatResponse（内容 + 工具调用申请）

设计要点：core 里绝不能出现 `if model == "ollama"` 这类判断，
         换模型只需新增一个 Provider 子类，core 一行不改。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """模型开出的一张"调用申请单"。"""
    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class ChatResponse:
    """模型一次回复的统一表示：要么是文本，要么是工具申请单（或两者都有）。"""
    content: str = ""
    tool_calls: list = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        """agent loop 的循环开关：有申请单就继续转，没有就收工。"""
        return bool(self.tool_calls)


class Gateway(ABC):
    """LLM 网关抽象基类。所有模型服务（Ollama / OpenAI / Dify …）都实现它。"""

    @abstractmethod
    def chat(self, messages: list, tools: list) -> ChatResponse:
        """发一轮对话请求，返回 ChatResponse。"""
        raise NotImplementedError
