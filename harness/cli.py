"""harness/cli.py — 应用层（终端前端）

职责：唯一关心"怎么显示"的地方。订阅事件总线，把事件渲染成人看的东西。
输入：EventBus、AgentLoop
输出：终端输出 + 用户输入

对应出题人规范第 4 条：前端只负责 UI 组织与订阅，不参与任何计算。
"""
import sys

TOOL_LABELS = {
    "tool_start": "调用工具",
    "tool_end": "工具返回",
}


class ConsoleUI:
    """终端界面：订阅事件，负责所有显示。"""

    def __init__(self, bus):
        self.bus = bus
        self.bus.on("tool_start", self.on_tool_start)
        self.bus.on("tool_end", self.on_tool_end)
        self.bus.on("turn_start", self.on_turn_start)
        self.bus.on("turn_end", self.on_turn_end)

    # ---------- 事件回调（只做显示，不含任何逻辑） ----------
    def on_turn_start(self, user_input, **kw):
        print(f"\n> {user_input}")

    def on_tool_start(self, name, arguments, **kw):
        print(f"  [{TOOL_LABELS['tool_start']}] {name}({arguments})")

    def on_tool_end(self, name, result, **kw):
        brief = result if len(result) <= 80 else result[:80] + "…"
        print(f"  [{TOOL_LABELS['tool_end']}] {brief}")

    def on_turn_end(self, content, steps, **kw):
        print(f"\n{content}")
        print(f"  （用了 {steps} 轮）")

    # ---------- 主循环 ----------
    def start(self, loop, one_shot: str | None = None):
        """启动交互；给了 one_shot 就只跑一次。"""
        if one_shot:
            loop.run(one_shot)
            return
        print("Harness 已启动。输入问题回车提问，输入 exit / quit 退出。")
        while True:
            try:
                text = input("\n你: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见。")
                return
            if text.lower() in {"exit", "quit", "q"}:
                print("再见。")
                return
            if not text:
                continue
            try:
                loop.run(text)
            except Exception as e:
                print(f"[错误] {type(e).__name__}: {e}", file=sys.stderr)
