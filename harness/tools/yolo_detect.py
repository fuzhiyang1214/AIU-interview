"""harness/tools/yolo_detect.py — 目标检测工具（复用任务二的 YOLO）

职责：让模型能"看见"——对摄像头当前画面或指定图片做一次目标检测。
输入：source（"camera" 或图片路径）、conf（置信度阈值）
输出：人类可读的检测结果字符串

★ 跨解释器说明（本文件的核心难点）：
  Harness 跑在系统 Python 上，不装 torch；
  任务二的 torch / ultralytics 装在 D:\\envs\\yolo 虚拟环境里。
  本工具用「子进程 + venv 的 python」做桥接：
      harness(系统 Python) --subprocess--> D:\\envs\\yolo\\Scripts\\python.exe
                                              └─ yolo/detect_cli.py → JSON
  这样 core 完全无感，YOLO 依赖也不会污染 harness 的运行环境。

  代价：每次调用都要冷启动一次 Python + 加载模型（首次十几秒，热缓存后 1~3 秒）。
  这是刻意接受的取舍——若做成常驻服务会更快，但两边就耦合了。
"""
import json
import os
import subprocess
from pathlib import Path

NAME = "yolo_detect"

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "对摄像头当前画面或指定图片做一次目标检测，返回检测到的物体名称、"
            "置信度和位置。当用户问『你看到了什么』『摄像头里有什么』『帮我看看这张图』时使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "检测来源：填 'camera' 表示抓摄像头一帧；或填写一张图片的完整路径",
                },
                "conf": {
                    "type": "number",
                    "description": "置信度阈值 0~1，默认 0.25。数值越低越敏感但误检越多",
                },
            },
            "required": ["source"],
        },
    },
}

# 项目根目录（本文件 → tools → harness → 仓库根）
ROOT = Path(__file__).resolve().parents[2]

VENV_PYTHON = Path(r"D:\envs\yolo\Scripts\python.exe")
DETECT_CLI = ROOT / "yolo" / "detect_cli.py"


def _format(payload: dict) -> str:
    """把检测脚本的 JSON 结果转成给模型看的自然语言。"""
    if not payload.get("ok"):
        return f"检测失败：{payload.get('error', '未知错误')}"

    objects = payload.get("objects") or []
    src = "摄像头" if payload.get("source") == "camera" else payload.get("source")

    if not objects:
        return (f"{src}画面中未检测到任何目标"
                f"（耗时 {payload.get('elapsed_ms')} ms）。"
                "如果确信画面里应该有的东西，可能是置信度阈值偏高或光线/角度不佳。")

    lines = [f"{src}画面检测到 {len(objects)} 个目标（耗时 {payload.get('elapsed_ms')} ms）："]
    for i, o in enumerate(objects, 1):
        x1, y1, x2, y2 = o["xyxy"]
        lines.append(f"  {i}. {o['label']}  置信度 {o['conf']}  位置 ({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})")
    if payload.get("saved"):
        lines.append(f"（带框的图片已保存到 {payload['saved']}）")
    return "\n".join(lines)


def run(source: str = "camera", conf: float = 0.25) -> str:
    """执行一次检测。异常交给 core/executor.py 统一兜住。"""
    if not VENV_PYTHON.is_file():
        return f"找不到 YOLO 虚拟环境：{VENV_PYTHON}，请确认任务二的环境还在。"
    if not DETECT_CLI.is_file():
        return f"找不到检测脚本：{DETECT_CLI}"

    cmd = [str(VENV_PYTHON), str(DETECT_CLI),
           "--source", str(source), "--conf", str(conf)]

    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        env={**os.environ, "PYTHONUTF8": "1"},      # 防 Windows GBK 编码报错
    )

    stdout = (proc.stdout or "").strip()
    if not stdout:
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        return "检测脚本没有输出。" + ("错误信息：" + " / ".join(tail) if tail else "")

    # 取最后一行 JSON（前面可能有 ultralytics 的日志）
    last_line = stdout.splitlines()[-1]
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError:
        return f"检测脚本输出无法解析：{last_line[:200]}"

    return _format(payload)
