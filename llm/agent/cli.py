# -*- coding: utf-8 -*-
"""任务 1-2 · CLI 接入层（零依赖，仅标准库）

职责：只做终端交互——读一行输入 → 交给 dify_client → 打印一行回答。
      与 Dify 通信的全部细节在 dify_client.py 里，本文件不含任何 HTTP 代码。

链路：CLI -> dify_client -> Dify API -> Ollama(qwen2.5:7b) -> 本机 GPU

用法（PowerShell）：
    $env:DIFY_API_KEY="app-xxxxxxxx"
    python cli.py

用法（CMD）：
    set DIFY_API_KEY=app-xxxxxxxx
    python cli.py
"""
import os

from dify_client import DifyClient, DifyError

USER = os.environ.get("DIFY_USER", "local-cli")


def main():
    try:
        client = DifyClient()
    except DifyError as exc:
        print("[启动失败]", exc)
        return

    print("本地大模型链 CLI  |  输入 exit 退出")
    conversation_id = ""          # 多轮上下文：每轮把上一次的 id 传回去

    while True:
        try:
            query = input("\n你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if query in ("", "exit", "quit"):
            break
        try:
            answer, conversation_id, _ = client.chat(
                query, user=USER, conversation_id=conversation_id)
            print("AI >", answer)
        except DifyError as exc:
            print("AI > [请求失败]", exc)


if __name__ == "__main__":
    main()
