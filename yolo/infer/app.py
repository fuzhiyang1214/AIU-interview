# app.py
# 后端：只负责「组装」—— 加载模型、启动摄像头线程、把画面与统计以 HTTP 接口推送。
# 路由概览：
#   GET /          返回前端页面（index.html）
#   GET /video_feed MJPEG 视频流，前端 <img> 直接订阅
#   GET /stats      当前帧率与检测目标数（JSON）

import argparse

from flask import Flask, Response, jsonify, render_template

from camera import Camera
from model_loader import load_model

app = Flask(__name__)
camera: Camera | None = None  # 在 main() 里初始化


@app.route("/")
def index():
    """前端页面：只负责 UI 组织与订阅，不含任何推理逻辑。"""
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    """把摄像头最新帧以 MJPEG 流的形式推给前端。"""

    def generate():
        while True:
            frame = camera.read()
            if frame is None:
                continue
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/stats")
def stats():
    """前端定时轮询这个接口，显示帧率与目标数。"""
    return jsonify(camera.stats())


def main() -> None:
    global camera

    ap = argparse.ArgumentParser(description="YOLO 摄像头实时推理（Flask 后端）")
    ap.add_argument("--camera", type=int, default=0, help="摄像头序号，默认 0")
    ap.add_argument("--port", type=int, default=8000, help="HTTP 端口，默认 8000")
    ap.add_argument("--conf", type=float, default=0.25, help="置信度阈值，默认 0.25")
    ap.add_argument("--imgsz", type=int, default=640, help="推理输入尺寸，默认 640")
    args = ap.parse_args()

    model = load_model()
    camera = Camera(model, args.camera, args.imgsz, args.conf)
    camera.start()

    print(f"[后端] 摄像头 {args.camera} 推理中")
    print(f"[后端] 浏览器打开 http://localhost:{args.port} 查看实时画面，Ctrl+C 退出")
    app.run(host="0.0.0.0", port=args.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
