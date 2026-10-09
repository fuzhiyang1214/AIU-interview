"""harness/web/server.py — 应用层（Web 前端）

职责：把事件总线桥接到浏览器 —— 订阅 core 的事件，用 SSE 推给前端；
      接收浏览器的提问，丢给 AgentLoop 执行。本文件不含任何 agent 逻辑。
输入：EventBus、AgentLoop、端口号
输出：HTTP 服务（页面 / 静态资源 / SSE 事件流 / 提问接口）

对应出题人规范第 4 条：前端只负责 UI 组织与订阅，后端只负责计算与推送。
本文件与 cli.py 是**同一套事件的两个订阅者** —— core 完全不知道谁在监听。

依赖：只用标准库（http.server / json / queue / threading），不需要 Flask。
"""
import json
import os
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# 事件名 → 推给前端时统一带上的字段（前端按 event 名决定怎么渲染）
FORWARDED_EVENTS = ("turn_start", "model_response", "tool_start", "tool_end", "turn_end")


def _jsonable(obj):
    """把事件载荷转成可 JSON 序列化的形式（ToolCall 对象等）。"""
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "__dict__"):                      # ToolCall 之类的 dataclass
        return _jsonable(vars(obj))
    return obj


class WebUI:
    """Web 界面：订阅事件 → 塞进每个浏览器的队列；同时提供提问入口。"""

    def __init__(self, bus, loop, port: int = 8000):
        self.bus = bus
        self.loop = loop
        self.port = port
        self.clients = []                             # 每个浏览器连接一个队列
        self._lock = threading.Lock()

        for event in FORWARDED_EVENTS:
            bus.on(event, self._make_handler(event))

    # ---------- 事件订阅（只做转发，不做任何处理） ----------
    def _make_handler(self, event):
        def handler(**payload):
            self.broadcast(event, payload)
        return handler

    def broadcast(self, event: str, payload: dict):
        """把事件推给所有已连接的浏览器。"""
        frame = {"event": event, "data": _jsonable(payload)}
        with self._lock:
            for q in self.clients:
                q.put(frame)

    def subscribe(self):
        """新增一个浏览器连接，返回它专属的队列。"""
        q = queue.Queue()
        with self._lock:
            self.clients.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self.clients:
                self.clients.remove(q)

    # ---------- 提问 ----------
    def ask(self, text: str):
        """在后台线程里跑一轮 agent loop，避免阻塞 HTTP 响应。"""
        def work():
            try:
                self.loop.run(text)
            except Exception as e:
                self.broadcast("error", {"message": f"{type(e).__name__}: {e}"})
        threading.Thread(target=work, daemon=True).start()

    # ---------- 启动 ----------
    def start(self):
        builder = self._build_handler()
        httpd = ThreadingHTTPServer(("127.0.0.1", self.port), builder)
        httpd.ui_ref = self                       # 供 handle_sse 取回 WebUI 实例
        print(f"Harness Web 已启动： http://127.0.0.1:{self.port}")
        print("（Ctrl+C 停止）")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止。")
        finally:
            httpd.server_close()

    def _build_handler(self):
        ui = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass                              # 静音默认访问日志

            def _send(self, code, body: bytes, ctype: str):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    self._send_file("index.html", "text/html; charset=utf-8")
                elif self.path == "/events":
                    ui.handle_sse(self)
                elif self.path == "/stats":
                    body = json.dumps({"clients": len(ui.clients)}).encode()
                    self._send(200, body, "application/json")
                else:
                    name = self.path.lstrip("/")
                    ctype = "text/css" if name.endswith(".css") else \
                            "application/javascript" if name.endswith(".js") else \
                            "text/plain; charset=utf-8"
                    self._send_file(name, ctype)

            def _send_file(self, name, ctype):
                path = os.path.join(STATIC_DIR, name)
                if not os.path.isfile(path):
                    self._send(404, b"not found", "text/plain; charset=utf-8")
                    return
                with open(path, "rb") as f:
                    self._send(200, f.read(), ctype)

            def do_POST(self):
                if self.path != "/ask":
                    self._send(404, b"not found", "text/plain; charset=utf-8")
                    return
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length).decode("utf-8") if length else "{}"
                try:
                    text = (json.loads(raw) or {}).get("text", "").strip()
                except json.JSONDecodeError:
                    self._send(400, b"bad json", "text/plain; charset=utf-8")
                    return
                if not text:
                    self._send(400, b"empty text", "text/plain; charset=utf-8")
                    return
                ui.ask(text)
                self._send(200, b'{"ok":true}', "application/json")

        return Handler

    # ---------- SSE ----------
    @staticmethod
    def handle_sse(handler):
        """长连接：把队列里的事件按 SSE 格式持续写给浏览器。"""
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.end_headers()

        ui = handler.server.ui_ref            # 由 _build_handler 注入
        q = ui.subscribe()
        try:
            handler.wfile.write(b": connected\n\n")
            handler.wfile.flush()
            while True:
                try:
                    frame = q.get(timeout=15)
                    payload = json.dumps(frame["data"], ensure_ascii=False)
                    chunk = f"event: {frame['event']}\ndata: {payload}\n\n"
                    handler.wfile.write(chunk.encode("utf-8"))
                    handler.wfile.flush()
                except queue.Empty:
                    handler.wfile.write(b": ping\n\n")   # 心跳，防代理断连
                    handler.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            ui.unsubscribe(q)
