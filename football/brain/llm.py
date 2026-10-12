"""football/brain/llm.py — 本地大模型客户端

职责：把 messages 发给本机 Ollama，取回文本。
输入：messages（标准 chat 格式）
输出：字符串

与任务四 harness 用的是同一个模型（qwen2.5:7b），
区别只是这里**不接工具**，只做「分析 + 生成」。
urllib 必须套 ProxyHandler({})，否则会被系统代理劫持。
"""
import json
import urllib.request

HOST = "http://127.0.0.1:11434"
MODEL = "qwen2.5:7b"


def chat(messages: list, model: str = MODEL, host: str = HOST,
         timeout: int = 300, temperature: float = 0.6) -> str:
    """发一轮对话，返回模型文本。"""
    body = json.dumps({
        "model": model,
        "stream": False,
        "messages": messages,
        "options": {"temperature": temperature},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{host}/api/chat", data=body,
        headers={"Content-Type": "application/json"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as r:
        return json.loads(r.read())["message"]["content"]
