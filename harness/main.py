"""harness/main.py — 组装入口

职责：只有"接线" —— 注册工具、拼装三层、交给应用层启动。通篇没有业务逻辑。
输入：命令行参数（--web 切 Web 前端 / --port 指定端口 / --ask 单次提问）
输出：无（把控制权交给 cli 或 web）

对应出题人规范第 1 条：主程序只负责模块的组装。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.events import EventBus          # noqa: E402
from core.registry import Registry        # noqa: E402
from core.executor import Executor        # noqa: E402
from core.loop import AgentLoop           # noqa: E402
from core.context import Context          # noqa: E402
from backend.ollama_provider import OllamaProvider   # noqa: E402
from tools import get_time, http_get, yolo_detect     # noqa: E402


def build():
    """把各层拼在一起。这是本文件唯一的职责。"""
    # ① 工具层：注册即接入
    reg = Registry()
    reg.register(get_time.NAME, get_time.SCHEMA, get_time.run)
    reg.register(http_get.NAME, http_get.SCHEMA, http_get.run)
    reg.register(yolo_detect.NAME, yolo_detect.SCHEMA, yolo_detect.run)   # ← 复用任务二

    # ② 后端层：换模型只改这一行
    gateway = OllamaProvider(model="qwen2.5:7b")

    # ③ 核心层：循环 / 执行器 / 上下文 / 事件总线
    bus = EventBus()
    loop = AgentLoop(
        gateway=gateway,
        registry=reg,
        executor=Executor(reg),
        bus=bus,
        context=Context(),
        max_steps=8,
    )
    return loop, bus


def main():
    parser = argparse.ArgumentParser(description="LLM Agent Harness")
    parser.add_argument("--web", action="store_true", help="启动 Web 前端（默认终端）")
    parser.add_argument("--port", type=int, default=8000, help="Web 端口，默认 8000")
    parser.add_argument("--ask", type=str, default=None, help="只问一次就退出（终端模式）")
    args = parser.parse_args()

    loop, bus = build()
    # 应用层订阅事件 —— 换前端只改这里，core 一行不动
    if args.web:
        from web.server import WebUI
        WebUI(bus, loop, port=args.port).start()
    else:
        from cli import ConsoleUI
        ConsoleUI(bus).start(loop, one_shot=args.ask)


if __name__ == "__main__":
    main()

