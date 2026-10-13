"""harness/tools/football_tactics.py — 足球战术分析工具（复用任务五的创作作品）

职责：让 Agent 具备"看球"的能力 —— 对一张球场截图判断攻防态势（谁进攻、谁防守、
      哪条通道空），并可顺带推演球接下来可能的发展。
输入：source（图片路径或 'camera'）、with_advice（是否生成战术建议）
输出：人类可读的分析结论字符串

★ 与 yolo_detect 同款的跨解释器桥接：
  harness(系统 Python) --subprocess--> D:\\envs\\yolo\\Scripts\\python.exe
                                          └─ football/analyze_cli.py → JSON
  core 完全无感：本工具只是往注册表里多加了一个名字。
"""
import json
import os
import subprocess
from pathlib import Path

NAME = "football_tactics"

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "对一张足球比赛截图做战术分析：判断场上谁是进攻方 / 防守方、"
            "哪条通道是空当，并结合静态画面推演球接下来可能的发展。"
            "当用户问『这球怎么打』『现在谁在进攻』『分析这张球场图』时使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "球场截图路径；或填 'camera' 抓摄像头当前一帧",
                },
                "with_advice": {
                    "type": "boolean",
                    "description": "是否同时生成战术建议（更慢，需本机 Ollama 在跑）",
                },
            },
            "required": ["source"],
        },
    },
}

ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = Path(r"D:\envs\yolo\Scripts\python.exe")
ANALYZE_CLI = ROOT / "football" / "analyze_cli.py"


def _format(payload: dict) -> str:
    """把分析 JSON 转成给模型看的自然语言。"""
    if not payload.get("ok"):
        return f"战术分析失败：{payload.get('error', '未知错误')}"

    s = payload["summary"]
    c = s["counts"]
    lines = [f"画面分析（耗时 {payload.get('elapsed_ms')} ms）："]
    lines.append(f"  球员 {c['players']} 人（T0 {c['team0']} / T1 {c['team1']}）")

    # 方向词由分析层给出（真实画面纵深=横轴、战术板纵深=画布纵轴），这里照抄不自己解释
    axis = s.get("axis") or {}
    depth_labels = axis.get("depth_labels") or ["上", "中", "下"]
    for side, label in (("0", "T0"), ("1", "T1")):
        z = (s.get("dist") or {}).get(side)
        if z:
            lines.append(f"  {label} 纵深分布（{'/'.join(depth_labels)}）："
                         f"{' / '.join(str(v) for v in z)}")

    b = s["ball"]
    if b["present"]:
        where = f"在「{b.get('depth_band')}」纵深段 · 「{b.get('channel_band')}」通道"
        if b.get("owner") is not None:
            where += f"，在 T{b['owner']} 球员脚下"
        lines.append(f"  球：{where}")
    else:
        lines.append("  球：未检出")

    if s["attacking_team"] is None:
        lines.append(f"  攻防判定：相持（{s.get('reason') or ''}）")
    else:
        how = {"ball": "控球判定", "position": "站位粗判"}.get(s.get("basis"), "")
        # 真实画面单帧给不出推进方向（direction=None），这时**不要**印出 "None"
        dir_txt = f"，推进方向「{s['direction']}」" if s.get("direction") else ""
        lines.append(f"  攻防判定：T{s['attacking_team']} 进攻、T{s.get('defending_team')} 防守"
                     f"{dir_txt}（{how}：{s.get('reason') or ''}）")
        if s.get("gap_channel"):
            lines.append(f"  空当通道：{s['gap_channel']}")

    if payload.get("advice"):
        lines.append("\n【战术解读】\n" + payload["advice"])
    return "\n".join(lines)


def run(source: str = "camera", with_advice: bool = False) -> str:
    """执行一次战术分析。异常交给 core/executor.py 兜住。"""
    if not VENV_PYTHON.is_file():
        return f"找不到 YOLO 虚拟环境：{VENV_PYTHON}，请确认任务二的环境还在。"
    if not ANALYZE_CLI.is_file():
        return f"找不到分析脚本：{ANALYZE_CLI}"

    cmd = [str(VENV_PYTHON), str(ANALYZE_CLI), "--source", str(source)]
    if with_advice:
        cmd.append("--advise")

    proc = subprocess.run(
        cmd, cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
        env={**os.environ, "PYTHONUTF8": "1"},
    )

    stdout = (proc.stdout or "").strip()
    if not stdout:
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        return "分析脚本没有输出。" + ("错误信息：" + " / ".join(tail) if tail else "")

    try:
        payload = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError:
        return f"分析脚本输出无法解析：{stdout[-200:]}"
    return _format(payload)
