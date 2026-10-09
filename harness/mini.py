"""harness/mini.py — Harness 最小可运行版（单文件，仅验证 agent loop 能跑通一圈）
职责：请求(带工具表) → 模型返回 tool_calls → 本地执行 → 结果回灌 → 再请求 → 输出答案
依赖：只用标准库 + 本机 Ollama(127.0.0.1:11434)
运行：python harness/mini.py
"""
import json
import datetime
import urllib.request

OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen2.5:7b"
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 禁用代理


# ---------- 工具层 ----------
def get_time(city: str) -> str:
    """查询指定城市的当前时间（玩具实现，返回本机时钟）"""
    return f"{city} 当前时间 {datetime.datetime.now():%Y-%m-%d %H:%M:%S}（本机时钟）"


TOOLS = {
    "get_time": {
        "schema": {
            "type": "function",
            "function": {
                "name": "get_time",
                "description": "查询指定城市的当前时间",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string", "description": "城市名称"}},
                    "required": ["city"],
                },
            },
        },
        "run": get_time,
    },
}


def tool_schemas():
    return [t["schema"] for t in TOOLS.values()]


# ---------- 后端层：LLM 网关（直连 Ollama） ----------
def chat(messages):
    body = json.dumps({
        "model": MODEL,
        "stream": False,
        "messages": messages,
        "tools": tool_schemas(),
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA, data=body, headers={"Content-Type": "application/json"}
    )
    with _opener.open(req, timeout=300) as r:
        return json.loads(r.read())["message"]


# ---------- 核心层：agent loop（整个 Harness 的心脏） ----------
def loop(user_input, max_steps=6):
    messages = [
        {"role": "system", "content": "需要信息时调用工具，不要凭空猜测。"},
        {"role": "user", "content": user_input},
    ]
    for _ in range(max_steps):
        msg = chat(messages)
        calls = msg.get("tool_calls")
        if not calls:                                  # 没有工具申请 → 收工
            return msg.get("content", "")
        messages.append(msg)                           # 记下模型的"申请单"
        for c in calls:
            name = c["function"]["name"]
            args = c["function"]["arguments"] or {}
            print(f"  [tool] {name}({args})")
            if name not in TOOLS:
                out = f"未知工具：{name}"
            else:
                try:
                    out = TOOLS[name]["run"](**args)
                except Exception as e:
                    out = f"工具执行失败：{e}"          # 报错也回灌，让模型自己纠偏
            messages.append({"role": "tool", "content": str(out)})
    return "达到最大轮次上限"


if __name__ == "__main__":
    print(loop("北京现在几点？"))
