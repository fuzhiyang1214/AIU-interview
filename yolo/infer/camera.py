# camera.py
# 摄像头推理模块：封装"抓帧 → 推理 → 得到带框画面"这一步。
# 只对外暴露 Camera 类，后端（app.py）不需要知道 cv2 / ultralytics 的任何细节。

import threading
import time

import cv2


class Camera:
    """在后台线程里持续抓帧并推理，缓存最新一帧的 JPEG 供前端拉取。

    单独开线程的原因：推理较慢（几十毫秒/帧），若在 HTTP 请求里同步推理，
    多个前端同时刷新会互相阻塞。这里只做一次推理，所有订阅者共享结果。
    """

    def __init__(self, model, camera_id: int = 0, imgsz: int = 640, conf: float = 0.25, jpeg_quality: int = 80):
        self.model = model
        self.camera_id = camera_id
        self.imgsz = imgsz
        self.conf = conf
        self.jpeg_quality = jpeg_quality

        self._jpeg: bytes | None = None  # 最新一帧（已画框，JPEG 编码）
        self._fps = 0.0  # 实测推理帧率
        self._boxes = 0  # 当前帧检测到的目标数
        self._lock = threading.Lock()  # 保护上面三个字段的并发读写
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """启动后台抓帧线程。"""
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """通知线程退出。"""
        self._stop.set()

    def _loop(self) -> None:
        cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)  # Windows 下 DSHOW 打开更快
        if not cap.isOpened():
            print(f"[camera] 无法打开摄像头 {self.camera_id}，请检查是否被其他程序占用")
            return

        t0, frames = time.time(), 0
        while not self._stop.is_set():
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.01)
                continue

            # 推理 + 画框：plot() 返回画好框和标签的 BGR 图
            result = self.model.predict(frame, imgsz=self.imgsz, conf=self.conf, verbose=False)[0]
            annotated = result.plot()
            n_boxes = 0 if result.boxes is None else len(result.boxes)

            ok_enc, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
            if not ok_enc:
                continue

            # 每秒统计一次帧率
            frames += 1
            now = time.time()
            if now - t0 >= 1.0:
                fps, frames, t0 = frames / (now - t0), 0, now

            with self._lock:
                self._jpeg, self._fps, self._boxes = buf.tobytes(), fps, n_boxes

        cap.release()

    def read(self) -> bytes | None:
        """取最新一帧的 JPEG 字节流，供前端订阅。"""
        with self._lock:
            return self._jpeg

    def stats(self) -> dict:
        """取当前统计信息（帧率、目标数）。"""
        with self._lock:
            return {"fps": round(self._fps, 1), "boxes": self._boxes}
