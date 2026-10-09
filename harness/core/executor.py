"""harness/core/executor.py — 工具执行器

职责：拿着模型开的"申请单"去真正执行工具，并把结果（或错误）转成字符串回灌。
输入：Registry + ToolCall
输出：字符串结果

设计要点（两条加分细节）：
  1. 报错也当结果回灌 —— 不抛异常崩掉，让模型看到错误信息后自己换条路（pi 的做法）
  2. 未知工具同样回灌一条说明，而不是让程序挂掉
"""


class Executor:
    """执行器。只管"怎么执行"，不管"该不该执行"。"""

    def __init__(self, registry):
        self.registry = registry

    def run(self, call) -> str:
        """执行一次工具调用，永远返回字符串（异常也转成字符串）。"""
        handler = self.registry.get(call.name)
        if handler is None:
            return f"未知工具：{call.name}。可用工具：{self.registry.names()}"
        try:
            return str(handler(**call.arguments))
        except TypeError as e:
            return f"工具参数不正确：{e}"
        except Exception as e:
            return f"工具执行失败：{type(e).__name__}: {e}"
