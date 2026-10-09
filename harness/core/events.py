"""harness/core/events.py — 事件总线（前后端解耦的关键）

职责：core 只负责"喊一声发生了什么"，谁想听谁自己订阅。
输入：事件名 + 任意关键字参数
输出：无返回值；按订阅顺序回调所有监听者

设计要点（对应出题人规范第 4 条 "前后端高度解耦"）：
  core 里不允许出现 print —— 输出是 UI 的事。
  core 只 emit 事件，CLI / Web 各自订阅，互不知道对方存在。
"""
from collections import defaultdict


class EventBus:
    """极简发布/订阅总线。"""

    def __init__(self):
        self._subs = defaultdict(list)

    def on(self, event: str, handler):
        """订阅一个事件。handler(**kwargs) 会在事件触发时被调用。"""
        self._subs[event].append(handler)
        return handler

    def emit(self, event: str, **payload):
        """发布一个事件，同步通知所有订阅者。"""
        for handler in self._subs.get(event, []):
            handler(**payload)
