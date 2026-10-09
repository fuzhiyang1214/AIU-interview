"""harness/backend/ollama_provider.py — Ollama 适配器（Gateway 的一个实现）

职责：把统一的 messages/tools 翻译成 Ollama /api/chat 的请求格式，
      再把返回的 message 解析成统一的 ChatResponse。
输入：messages、tools
输出：ChatResponse
依赖：只用标准库 + 本机 Ollama(127.0.0.1:11434)

说明：urllib 必须套 ProxyHandler({})，否则会被系统代理劫持导致连接失败。
"""
import json
import urllib.request

from .gateway import Gateway, ChatResponse, ToolCall


class OllamaProvider(Gateway):
    """直连本机 Ollama 的网关实现。"""

    def __init__(self, model: str = "qwen2.5:7b",
                 host: str = "http://127.0.0.1:11434", timeout: int = 300):
        self.model = model
        self.url = f"{host}/api/chat"
        self.timeout = timeout
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def chat(self, messages: list, tools: list) -> ChatResponse:
        body = json.dumps({
            "model": self.model,
            "stream": False,
            "messages": messages,
            "tools": tools or [],
        }).encode("utf-8")

        req = urllib.request.Request(
            self.url, data=body, headers={"Content-Type": "application/json"}
        )
        with self._opener.open(req, timeout=self.timeout) as r:
            msg = json.loads(r.read())["message"]

        calls = []
        for c in msg.get("tool_calls") or []:
            fn = c.get("function", {})
            args = fn.get("arguments") or {}
            # 部分模型会把 arguments 序列化成字符串，这里统一兜一下
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append(ToolCall(id=c.get("id", ""), name=fn.get("name", ""), arguments=args))

        return ChatResponse(content=msg.get("content", ""), tool_calls=calls)
