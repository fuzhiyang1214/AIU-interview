"""harness/tools/get_time.py — 查询时间（玩具工具）

职责：验证整条链路能跑通的第一个工具，不做真实时区换算，只读本机时钟。
输入：city（城市名，仅用于回显）
输出：字符串
"""
import datetime

NAME = "get_time"

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": "查询指定城市的当前时间",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称，例如：北京"}
            },
            "required": ["city"],
        },
    },
}


def run(city: str) -> str:
    """返回指定城市的当前时间（本机时钟）。"""
    return f"{city} 当前时间 {datetime.datetime.now():%Y-%m-%d %H:%M:%S}（本机时钟）"
