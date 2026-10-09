# detect_cli.py
# 单次检测入口：读一张图或抓一帧摄像头 → YOLO 推理 → 把结果以 JSON 打到 stdout。
#
# 为什么要单独一个脚本：
#   Harness 跑在系统 Python 上（无 torch），YOLO 依赖装在 D:\envs\yolo 虚拟环境里。
#   用子进程 + 这个脚本做「跨解释器桥接」，两边各自保持零耦合。
#
# 用法（必须用 venv 里的 python 运行）：
#   D:\envs\yolo\Scripts\python.exe detect_cli.py --source camera
#   D:\envs\yolo\Scripts\python.exe detect_cli.py --source path\to\img.jpg
#   D:\envs\yolo\Scripts\python.exe detect_cli.py --source camera --save out.jpg
#
# 输出（stdout 一行 JSON，便于 harness 解析）：
#   {"ok": true, "source": "camera", "count": 2, "fps_ms": 43.2, "saved": "...",
#    "objects": [{"label": "shoe", "conf": 0.62, "xyxy": [x1,y1,x2,y2]}, ...]}

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "infer"))

from model_loader import load_model    # noqa: E402


def detect(model, source: str, conf: float, imgsz: int):
    """对一帧画面做推理，返回 (result, 检测对象列表)。"""
    if source == "camera":
        import cv2
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            raise RuntimeError("无法打开摄像头 0（可能被其他程序占用，或当前环境无摄像头权限）")
        # 丢掉前几帧，等自动曝光稳定
        for _ in range(5):
            cap.read()
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError("摄像头读取失败")
    else:
        from ultralytics.utils.plotting import Annotator  # noqa: F401  (确保依赖在)
        import cv2
        frame = cv2.imread(source)
        if frame is None:
            raise RuntimeError(f"读不到图片：{source}")

    result = model.predict(frame, imgsz=imgsz, conf=conf, verbose=False)[0]

    objects = []
    if result.boxes is not None:
        names = result.names
        for box in result.boxes:
            cls_id = int(box.cls[0])
            objects.append({
                "label": names.get(cls_id, str(cls_id)),
                "conf": round(float(box.conf[0]), 3),
                "xyxy": [round(float(v), 1) for v in box.xyxy[0].tolist()],
            })
    return result, objects


def main() -> None:
    ap = argparse.ArgumentParser(description="YOLO 单次检测（输出 JSON）")
    ap.add_argument("--source", default="camera",
                    help="'camera' 表示抓摄像头一帧，否则视为图片路径")
    ap.add_argument("--conf", type=float, default=0.25, help="置信度阈值，默认 0.25")
    ap.add_argument("--imgsz", type=int, default=640, help="推理尺寸，默认 640")
    ap.add_argument("--save", default=None, help="可选：把画好框的图存到这个路径")
    ap.add_argument("--device", default="cuda:0", help="推理设备，默认 cuda:0")
    args = ap.parse_args()

    try:
        model = load_model(device=args.device)
        t0 = time.time()
        result, objects = detect(model, args.source, args.conf, args.imgsz)
        elapsed_ms = round((time.time() - t0) * 1000, 1)

        saved = None
        if args.save:
            import cv2
            cv2.imwrite(args.save, result.plot())
            saved = str(Path(args.save).resolve())

        print(json.dumps({
            "ok": True,
            "source": args.source,
            "count": len(objects),
            "elapsed_ms": elapsed_ms,
            "saved": saved,
            "objects": objects,
        }, ensure_ascii=False))

    except Exception as e:
        # 错误也以 JSON 输出，让 harness 侧能统一解析
        print(json.dumps({
            "ok": False,
            "source": args.source,
            "error": f"{type(e).__name__}: {e}",
        }, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
