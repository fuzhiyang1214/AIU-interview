# -*- coding: utf-8 -*-
"""任务 1-2 · Web 接入层（零依赖，仅标准库）

职责（只做组装，不做计算）：
  1. 静态托管同目录下的 index.html
  2. 把浏览器的 POST /api/chat 转成对 Dify 的流式请求，并把 SSE 原样推回
  3. GET /api/health 提供不依赖 Dify 存活的服务探针

  与 Dify 通信的细节全部在 dify_client.py 里，本文件只做路由与转发。

链路：浏览器 -> server.py -> dify_client -> Dify API -> Ollama(qwen2.5:7b) -> 本机 GPU

启动（PowerShell）：
    $env:DIFY_API_KEY="app-xxxxxxxx"
    python server.py
然后浏览器打开 http://127.0.0.1:8000
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dify_client import DifyClient, DifyError

HOST = os.environ.get("WEB_HOST", "127.0.0.1")
PORT = int(os.environ.get("WEB_PORT", "8000"))
ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LocalLLMWeb/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[web] %s\n" % (fmt % args))

    # ---------------- 响应工具 ----------------
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _sse_error(self, msg):
        """SSE 通道已开时用它报错：事件格式与 Dify 保持一致。"""
        try:
            data = json.dumps({"event": "error", "message": msg}, ensure_ascii=False)
            self.wfile.write(("data: " + data + "\n\n").encode("utf-8"))
            self.wfile.flush()
        except Exception:
            pass

    # ---------------- 路由 ----------------
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            path = os.path.join(ROOT, "index.html")
            if not os.path.isfile(path):
                self._json(404, {"error": "index.html 不存在"})
                return
            with open(path, "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif self.path == "/api/health":
            key = os.environ.get("DIFY_API_KEY") or ""
            self._json(200, {
                "ok": True,
                "key_loaded": bool(key),
                "key_ok": key.isascii() and key.startswith("app-"),
            })
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/chat":
            self._json(404, {"error": "not found"})
            return

        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception as exc:
            self._json(400, {"error": "请求体解析失败: %s" % exc})
            return

        try:
            client = DifyClient()
        except DifyError as exc:
            self._json(500, {"error": str(exc)})
            return

        # 先发响应头：SSE 不设 Content-Length，以关闭连接表示结束
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()

        try:
            # 强制流式由 dify_client 内部决定，前端传什么 response_mode 都不影响
            for line in client.chat_stream(
                    body.get("query", ""),
                    user=body.get("user") or "web-ui",
                    conversation_id=body.get("conversation_id") or "",
                    inputs=body.get("inputs")):
                self.wfile.write(line)
                self.wfile.flush()
        except DifyError as exc:
            self._sse_error(str(exc))
        except (BrokenPipeError, ConnectionResetError):
            pass          # 浏览器提前断开（刷新/关页面），不是错误


def main():
    if not os.environ.get("DIFY_API_KEY"):
        print("!! 警告：未设置 DIFY_API_KEY，/api/chat 会返回 500")
    print("Web 界面 : http://%s:%d" % (HOST, PORT))
    print("健康检查 : http://%s:%d/api/health" % (HOST, PORT))
    print("按 Ctrl+C 停止")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已停止")
