# -*- coding: utf-8 -*-
"""任务 1-2 · Dify 接入模块（零依赖，仅 Python 标准库）

职责：把「与 Dify Chat API 通信」这件事**完全**封装在这里——配置读取、鉴权、
      请求组装、阻塞式调用、流式调用、错误归一化。

      上层因此可以只做组装，不碰任何 HTTP 细节：
        cli.py     只做终端交互（拿到字符串就打印）
        server.py  只做 HTTP 路由与 SSE 转发（拿到字节就写出）

链路：上层 -> 本模块 -> Dify API -> Ollama(qwen2.5:7b) -> 本机 GPU

环境变量：
    DIFY_API_KEY    必填，Dify 应用密钥，形如 app-xxxxxxxx
    DIFY_API_BASE   选填，默认 http://localhost/v1

用法：
    client = DifyClient()                            # 缺 key 会抛 DifyError
    answer, cid, usage = client.chat("你好")          # 阻塞式，整段返回
    for line in client.chat_stream("你好"):           # 流式，逐行产出 SSE 字节
        ...

对外只暴露一个异常类型 DifyError，调用方无需 import urllib。
"""
import json
import os
import urllib.error
import urllib.request

DEFAULT_BASE = "http://localhost/v1"
DEFAULT_TIMEOUT = 300


class DifyError(RuntimeError):
    """配置或通信层面的错误。上层只需捕获这一个类型。"""


class DifyClient:
    """Dify Chat API 的最小客户端。"""

    def __init__(self, api_key=None, base=None, timeout=DEFAULT_TIMEOUT):
        key = api_key or os.environ.get("DIFY_API_KEY") or ""
        if not key:
            raise DifyError("未设置环境变量 DIFY_API_KEY")
        if not key.isascii():
            # 常见误用：把文档里的占位符（如 app-你的密钥）原样粘了进来。
            # 非 ASCII 会在发请求时被 http.client 的 latin-1 编码拦下，报出
            # 难以理解的 "codec can't encode characters in position 11-14"。
            raise DifyError(
                "DIFY_API_KEY 含非 ASCII 字符，请填入真实密钥（形如 app-xxxxxxxx）")
        self.api_key = key
        root = (base or os.environ.get("DIFY_API_BASE", DEFAULT_BASE)).rstrip("/")
        self.url = root + "/chat-messages"
        self.timeout = timeout
        # 显式禁用代理：发给本机/局域网的请求绝不能走环境里可能残留的代理设置。
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # ---------------- 内部：请求组装与错误归一化 ----------------
    def _payload(self, query, user, conversation_id, inputs, streaming):
        """Dify Chat API 的请求体。response_mode 由本模块决定，上层无需关心。"""
        return {
            "query": query,
            "inputs": inputs or {},
            "user": user,
            "conversation_id": conversation_id or "",
            "response_mode": "streaming" if streaming else "blocking",
        }

    def _request(self, payload, streaming):
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
        }
        if streaming:
            headers["Accept"] = "text/event-stream"
        return urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

    @staticmethod
    def _http_detail(exc):
        try:
            body = exc.read().decode("utf-8", "replace")[:500]
        except Exception:
            body = ""
        return "Dify 返回 HTTP %s: %s" % (exc.code, body)

    # ---------------- 对外：两种调用方式 ----------------
    def chat(self, query, user="local", conversation_id="", inputs=None):
        """阻塞式：等模型生成完，一次性返回 (answer, conversation_id, usage)。"""
        payload = self._payload(query, user, conversation_id, inputs, streaming=False)
        try:
            with self._opener.open(self._request(payload, streaming=False),
                                   timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise DifyError(self._http_detail(exc)) from exc
        except urllib.error.URLError as exc:
            raise DifyError("连接失败：%s" % (exc.reason,)) from exc

        return (
            data.get("answer", ""),
            data.get("conversation_id", conversation_id),
            (data.get("metadata") or {}).get("usage") or {},
        )

    def chat_stream(self, query, user="local", conversation_id="", inputs=None):
        """流式：逐行产出 Dify 返回的 SSE 原始字节，由调用方原样转发给浏览器。"""
        payload = self._payload(query, user, conversation_id, inputs, streaming=True)
        try:
            with self._opener.open(self._request(payload, streaming=True),
                                   timeout=self.timeout) as resp:
                for line in resp:
                    yield line
        except urllib.error.HTTPError as exc:
            raise DifyError(self._http_detail(exc)) from exc
        except urllib.error.URLError as exc:
            raise DifyError("连接失败：%s" % (exc.reason,)) from exc
