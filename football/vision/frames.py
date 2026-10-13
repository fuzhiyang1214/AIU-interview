"""football/vision/frames.py — 帧的来源（图像输入）

职责：把「前端上传的 data URL」与「本机摄像头」两种来源，统一成 BGR 帧，
      交给 `vision.analyze_image()` 处理。

为什么放在 vision 层而不是主程序：
  解码与采集都要碰 OpenCV 与图像类型，属视觉层的职责。
  主程序（app.py）因此**不必 import cv2 / numpy**，做到「只做组装」。
"""
import base64

import cv2
import numpy as np


def decode_data_url(data_url: str):
    """把 `data:image/...;base64,xxx` 解成 BGR 图像。

    Returns:
        BGR ndarray；解码失败返回 None（由调用方决定报什么错）。
    """
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    buf = np.frombuffer(base64.b64decode(data_url), np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def grab_camera(index: int = 0, warmup: int = 5):
    """抓摄像头一帧。

    先空读几帧再取：大多数摄像头刚打开时自动曝光 / 白平衡还没稳定，
    第一帧往往过曝或全黑。

    Raises:
        RuntimeError: 打不开设备或读帧失败（由 app.py 统一转成 500）。
    """
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开摄像头 {index}（可能被占用，或运行环境无摄像头权限）")
    try:
        for _ in range(max(0, warmup)):
            cap.read()
        ok, frame = cap.read()
    finally:
        cap.release()
    if not ok:
        raise RuntimeError("摄像头读取失败")
    return frame
