"""football/app.py — 全栈后端（Flask）

职责：只做「组装」——把视觉层与战术推理层接起来，暴露 HTTP 接口。
     本文件不含任何检测算法、不含任何提示词，全部下沉到 vision/brain。
     （按要求：不做球队识别，只判攻防态势 + 推演球的发展）

接口：
  GET  /                 前端页面
  POST /api/analyze      上传截图（或抓摄像头）→ 返回分析 + 标注图
  POST /api/advise       基于当前画面 → 生成「当前态势 + 球可能的发展」
  POST /api/ask          基于当前画面 → 战术问答
  GET  /api/state        当前缓存的画面分析（调试用）

运行（必须用装了 torch 的 venv）：
  D:\\envs\\yolo\\Scripts\\python.exe app.py --port 8100

对应出题人规范：
  第 1 条 主程序只负责组装；第 3 条 顶部有注释；第 4 条 前后端解耦（后端只算与推，前端只显示）。
"""
import argparse
import base64
import os

import cv2
import numpy as np
from flask import Flask, jsonify, request, send_from_directory

from vision import analyze_image, to_base64_jpeg
from brain import advise as brain_advise, answer as brain_answer

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = Flask(__name__, static_folder=None)

# 单用户本地应用：只缓存「最近一次分析」，供 /advise 与 /ask 复用上下文
STATE = {"analysis": None, "chat": []}

ARGS = {"conf": 0.35, "imgsz": 1280, "device": "cuda:0"}


# ---------------------------------------------------------------- 图像输入
def _decode_data_url(data_url: str):
    """把前端传来的 data:image/...;base64,xxx 解成 BGR 图像。"""
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    buf = np.frombuffer(base64.b64decode(data_url), np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def _grab_camera():
    """抓摄像头一帧（与任务二的 detect_cli 同款做法）。"""
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError("无法打开摄像头 0（可能被占用，或运行环境无摄像头权限）")
    for _ in range(5):
        cap.read()
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError("摄像头读取失败")
    return frame


# ---------------------------------------------------------------- 路由
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    body = request.get_json(silent=True) or {}
    try:
        if body.get("source") == "camera":
            frame = _grab_camera()
        else:
            if not body.get("image"):
                return jsonify({"ok": False, "error": "缺少 image 字段"}), 400
            frame = _decode_data_url(body["image"])
            if frame is None:
                return jsonify({"ok": False, "error": "图片解码失败"}), 400

        analysis, annotated = analyze_image(
            frame, conf=ARGS["conf"], imgsz=ARGS["imgsz"], device=ARGS["device"])

        STATE["analysis"], STATE["chat"] = analysis, []
        return jsonify({
            "ok": True,
            "analysis": analysis,
            "annotated": to_base64_jpeg(annotated),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@app.route("/api/advise", methods=["POST"])
def api_advise():
    if not STATE["analysis"]:
        return jsonify({"ok": False, "error": "请先分析一张截图"}), 400
    text = brain_advise(STATE["analysis"])
    return jsonify({"ok": True, "advice": text})


@app.route("/api/ask", methods=["POST"])
def api_ask():
    if not STATE["analysis"]:
        return jsonify({"ok": False, "error": "请先分析一张截图"}), 400
    q = (request.get_json(silent=True) or {}).get("question", "").strip()
    if not q:
        return jsonify({"ok": False, "error": "问题为空"}), 400
    a = brain_answer(q, STATE["analysis"], STATE["chat"])
    STATE["chat"] += [{"role": "user", "content": q},
                      {"role": "assistant", "content": a}]
    return jsonify({"ok": True, "answer": a})


@app.route("/api/state")
def api_state():
    return jsonify({"ok": True, "has_analysis": STATE["analysis"] is not None})


def main():
    ap = argparse.ArgumentParser(description="AI 战术分析师（全栈）")
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--device", default="cuda:0")
    args = ap.parse_args()
    ARGS.update(conf=args.conf, imgsz=args.imgsz, device=args.device)

    print(f"AI 战术分析师已启动： http://127.0.0.1:{args.port}")
    print("（Ctrl+C 停止；首次分析会自动加载 YOLO 权重）")
    app.run(host="127.0.0.1", port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
