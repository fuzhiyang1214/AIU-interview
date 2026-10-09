"""harness/core/registry.py — 工具注册表

职责：登记所有可用工具，并把它们导出成模型能看懂的 JSON schema 列表。
输入：工具定义（名字 + schema + 实现函数）
输出：schemas() 返回给模型看的工具表；get(name) 返回实现函数

设计要点：
  core 里不允许出现具体工具的名字 —— 它只认得注册表。
  加工具 = 往 tools/ 丢一个文件 + main.py 加一行 register()，本文件不动。
"""


class Registry:
    """工具注册表。"""

    def __init__(self):
        self._tools = {}   # name -> {"schema": ..., "handler": callable}

    def register(self, name: str, schema: dict, handler):
        """注册一个工具。"""
        self._tools[name] = {"schema": schema, "handler": handler}

    def schemas(self) -> list:
        """导出工具表，直接塞进 LLM 请求的 tools 参数。"""
        return [t["schema"] for t in self._tools.values()]

    def get(self, name: str):
        """按名字取工具实现；不存在返回 None。"""
        entry = self._tools.get(name)
        return entry["handler"] if entry else None

    def names(self) -> list:
        """当前所有已注册工具的名字。"""
        return list(self._tools.keys())
