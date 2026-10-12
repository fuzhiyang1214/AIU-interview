"""football/analyze_cli.py — 命令行入口（同时供 Harness 子进程调用）

职责：一张图 / 摄像头一帧 → 视觉分析 →（可选）战术解读 → 一行 JSON。
     不做球队识别；只输出攻防态势与「球可能的发展」线索。
输入：--source（图片路径或 'camera'）等参数
输出：stdout 最后一行是一段 JSON，便于 harness 解析

为什么单独一个脚本：Harness 跑在系统 Python（无 torch），
足球视觉依赖装在 D:\\envs\\yolo 里，用子进程桥接、两边零耦合（与任务二同款做法）。

用法：
  D:\\envs\\yolo\\Scripts\\python.exe analyze_cli.py --source shot.jpg --advise
  D:\\envs\\yolo\\Scripts\\python.exe analyze_cli.py --source camera --save out.jpg
"""
import argparse
import json
import sys
import time
from pathlib import Path

# 让本脚本无论从哪个目录启动，都能 import 到同目录下的 vision/brain
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vision import analyze_image            # noqa: E402
from brain import advise as brain_advise     # noqa: E402


def _load(source: str):
    import cv2
    if source == "camera":
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            raise RuntimeError("无法打开摄像头 0（可能被占用或无权限）")
        for _ in range(5):
            cap.read()
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError("摄像头读取失败")
        return frame
    frame = cv2.imread(source)
    if frame is None:
        raise RuntimeError(f"读不到图片：{source}")
    return frame


def _summary(analysis: dict) -> dict:
    """抽出对上层（模型 / 前端）有用的字段，别把整包坐标塞出去。"""
    return {
        "counts": analysis["counts"],
        "state": analysis["state"],
        "attacking_team": analysis["attacking_team"],
        "defending_team": analysis["sides"]["defending"],
        "direction": analysis.get("direction"),
        "reason": analysis.get("reason"),
        "gap_channel": analysis.get("gap_channel"),
        "dist": analysis.get("dist"),
        "ball": {"present": analysis["ball"]["present"],
                 "zone": analysis["ball"]["zone"],
                 "channel": analysis["ball"]["channel"]},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="AI 战术分析师 · 单张分析（输出 JSON）")
    ap.add_argument("--source", default="camera", help="图片路径，或 'camera'")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--advise", action="store_true", help="同时生成战术解读（需要 Ollama）")
    ap.add_argument("--save", default=None, help="把带标注的图保存到该路径")
    args = ap.parse_args()

    try:
        frame = _load(args.source)
        t0 = time.time()
        analysis, annotated = analyze_image(frame, conf=args.conf, imgsz=args.imgsz,
                                            device=args.device)
        elapsed = round((time.time() - t0) * 1000, 1)

        saved = None
        if args.save:
            import cv2
            cv2.imwrite(args.save, annotated)
            saved = str(Path(args.save).resolve())

        advice = brain_advise(analysis) if args.advise else None

        print(json.dumps({
            "ok": True,
            "source": args.source,
            "elapsed_ms": elapsed,
            "saved": saved,
            "summary": _summary(analysis),
            "advice": advice,
        }, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"ok": False, "source": args.source,
                          "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
