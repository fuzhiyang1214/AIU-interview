"""harness/tools/http_get.py — 抓取网页文本（第二个工具）

职责：演示"加一个新工具不需要改动 core"这件事。
输入：url（网址）、max_chars（最多返回多少字符）
输出：网页的纯文本片段，或错误说明

说明：用正则粗暴剥离 HTML 标签，够用即可；正则解析 HTML 不是本工具的目的，
      这里只是为了让模型能"看见"网页内容。
"""
import re
import urllib.request

NAME = "http_get"

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": "抓取一个网页并返回它的纯文本内容（已剥离 HTML 标签）",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "完整网址，必须以 http:// 或 https:// 开头"},
                "max_chars": {"type": "integer", "description": "最多返回多少字符，默认 2000"},
            },
            "required": ["url"],
        },
    },
}

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # 禁用代理


def run(url: str, max_chars: int = 2000) -> str:
    """抓取网页并返回剥掉标签后的文本。"""
    if not url.startswith(("http://", "https://")):
        return "网址必须以 http:// 或 https:// 开头"

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (harness-tool)"})
    with _opener.open(req, timeout=20) as r:
        raw = r.read()

    charset = r.headers.get_content_charset() or "utf-8"
    html = raw.decode(charset, errors="replace")

    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;?", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > max_chars:
        return text[:max_chars] + f"…（已截断，共 {len(text)} 字符）"
    return text or "（网页没有可读文本）"
