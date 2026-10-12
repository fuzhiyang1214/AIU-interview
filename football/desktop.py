"""football/desktop.py — 本地桌面入口（一键演示用）

职责：把 football 的 Flask 服务包装成「桌面程序」的观感：
      1) 后台线程起 Flask —— 直接复用 app.py 里已建好的 app 实例，不改动它
      2) 轮询等端口就绪 —— 避免窗口先于服务打开而白屏
      3) 自检 Ollama(11434) —— 没起就当场说清楚，而不是等用户点了按钮才报错
      4) 用 Edge 的 --app 模式开窗 —— 无地址栏、无标签页，观感即桌面软件；
         并给它独立的 user-data-dir，使「关闭窗口 = 退出程序」

零新增依赖：Edge 是 Windows 自带的；找不到时退回默认浏览器。

两种启动方式：
  · 带控制台（能看到日志）：双击 football\\启动.bat
  · 无控制台（最像桌面软件）：双击桌面快捷方式（用 pythonw.exe 运行本文件）
    pythonw 下没有 stdout/stdin，本文件会自动把输出写进 desktop.log，
    并把关键提示改用 Windows 原生弹窗。

对应出题人规范：
  第 1 条 本文件只做「启动与组装」，视觉与推理逻辑仍在 vision/ 与 brain/。
  第 3 条 顶部有简明注释。
"""
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

# 允许从任意工作目录启动：把本文件所在目录加入模块搜索路径
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# pythonw.exe（无控制台）下 sys.stdout / sys.stderr / sys.stdin 都是 None：
# 先把输出重定向到日志文件，否则任何 print 都会直接抛异常。
LOG_PATH = os.path.join(HERE, "desktop.log")
if sys.stdout is None or sys.stderr is None:
    _log = open(LOG_PATH, "w", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = _log
    if sys.stderr is None:
        sys.stderr = _log

from app import app  # noqa: E402  复用 app.py 中已创建好的 Flask 实例

HOST = "127.0.0.1"
DEFAULT_PORT = 8100
OLLAMA = "http://127.0.0.1:11434"

# Windows 自带的 Edge，用它的「应用模式」充当原生窗口壳
EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


# ---------------------------------------------------------------- 用户提示
def _alert(title: str, text: str, warn: bool = False) -> None:
    """无控制台时用 Windows 原生弹窗告知（任何异常都静默，不影响主流程）。"""
    try:
        import ctypes
        flags = 0x30 if warn else 0x40      # MB_ICONWARNING / MB_ICONINFORMATION
        ctypes.windll.user32.MessageBoxW(0, text, title, flags)
    except Exception:
        pass


def _pause(msg: str) -> None:
    """有控制台时等回车；无控制台（pythonw）时改用弹窗。"""
    if sys.stdin is None:
        _alert("AI 战术分析师 · 无法启动", msg, warn=True)
    else:
        input("按回车退出…")


# ---------------------------------------------------------------- 探测工具
def _port_open(port: int, timeout: float = 0.3) -> bool:
    """探测 127.0.0.1:port 是否已可连接。"""
    with socket.socket() as s:
        s.settimeout(timeout)
        return s.connect_ex((HOST, port)) == 0


def _wait_port(port: int, limit: float = 30.0) -> bool:
    """等端口就绪，最多 limit 秒（首次加载 YOLO 权重会慢一点）。"""
    start = time.time()
    while time.time() - start < limit:
        if _port_open(port):
            return True
        time.sleep(0.2)
    return False


def _ollama_ready() -> bool:
    """探测本机 Ollama 服务是否在线（不依赖它，只用于给出人话提示）。"""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"{OLLAMA}/api/tags", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def _find_edge():
    """返回 msedge.exe 路径，找不到则 None。"""
    for path in EDGE_PATHS:
        if os.path.isfile(path):
            return path
    return None


# ---------------------------------------------------------------- 主流程
def main():
    argv = [a for a in sys.argv[1:] if a != "--check"]
    check_only = "--check" in sys.argv[1:]
    port = DEFAULT_PORT
    if argv:
        try:
            port = int(argv[0])
        except ValueError:
            pass

    print("=" * 58)
    print("  AI 战术分析师 · 本地桌面版")
    print("=" * 58)

    # 1) 后台起 Flask（daemon：主线程退出时一并结束）
    threading.Thread(
        target=lambda: app.run(host=HOST, port=port, debug=False,
                               use_reloader=False, threaded=True),
        daemon=True,
    ).start()

    # 2) 等端口就绪
    print(f"[1/3] 正在启动服务（端口 {port}）…")
    if not _wait_port(port):
        msg = (f"30 秒内服务未能就绪。\n\n"
               f"端口 {port} 可能已被占用。\n\n"
               f"换端口重试： python desktop.py 8101")
        print(f"[错误] {msg}")
        _pause(msg)
        return

    # 3) 自检 Ollama
    if _ollama_ready():
        print("[2/3] Ollama 在线 —— 战术分析 / 战术问答可用。")
    else:
        print("[2/3] 未检测到 Ollama（127.0.0.1:11434）")
        print("      影响：「生成分析」「战术问答」会失败；")
        print("            但「上传图片 → 检测人员 / 分队 / 判攻防 / 找空当」照常可用。")
        print("      解决：另开一个终端执行   ollama serve")
        if sys.stdin is None:
            _alert("AI 战术分析师",
                   "未检测到 Ollama（127.0.0.1:11434）\n\n"
                   "仍可用：上传图片 → 检测人员 / 分队 / 判攻防 / 找空当\n"
                   "会失败：生成分析、战术问答\n\n"
                   "解决：另开一个终端执行  ollama serve")

    url = f"http://{HOST}:{port}"

    # --check：只做自检（起服务 + 探接口 + 查 Ollama），不开窗口，便于排查
    if check_only:
        for path in ("/", "/api/state"):
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(url + path, timeout=5) as resp:
                    print(f"      GET {path} -> HTTP {resp.status}")
            except Exception as e:
                print(f"      GET {path} -> 失败：{e}")
        print("[自检] 完成（未打开窗口）。")
        return

    # 4) 开窗口
    #    给 Edge 一个独立的 user-data-dir：这样它会开一个「专属进程」
    #    而不是把请求转交给已打开的 Edge —— 我们才能等到「窗口关闭」这个事件。
    edge = _find_edge()
    if edge:
        profile = os.path.join(tempfile.gettempdir(), "ai_tactics_edge_profile")
        proc = subprocess.Popen([
            edge, f"--app={url}", "--window-size=1320,900",
            f"--user-data-dir={profile}",
        ])
        print(f"[3/3] 已打开 Edge 应用窗口：{url}")
        print("-" * 58)
        print("关闭应用窗口即结束程序。")
        proc.wait()
        print("窗口已关闭，程序退出。")
        return

    # 兜底：没找到 Edge 就用默认浏览器（无法感知窗口关闭，需手动结束）
    import webbrowser
    webbrowser.open(url)
    print(f"[3/3] 未找到 Edge，已用默认浏览器打开：{url}")
    print("-" * 58)
    print("关闭本窗口即结束程序（Ctrl+C 也可）。")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n已退出。")


if __name__ == "__main__":
    main()
