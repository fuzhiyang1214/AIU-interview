"""任务二训练入口：读取 config/train.yaml 里的超参数，启动 YOLOv8 训练。

本模块只负责「组装」——模型路径、数据配置、训练参数分别来自
常量与 config/ 下的 yaml，训练细节全部交给 ultralytics。

⚠️ Windows 必须在 `if __name__ == '__main__':` 里启动训练：
DataLoader 用 spawn 起子进程时会重新导入本模块，若入口没有保护，
子进程会再跑一遍 train()，报
`RuntimeError: ... before the current process has finished its bootstrapping phase`。
"""

import yaml
from ultralytics import YOLO

MODEL = 'yolov8n.pt'  # 模型权重文件路径（可以找其他的模型权重）
DATA = 'config/dataset.yaml'  # 数据集配置文件路径


def main():
    """加载训练参数并启动训练（参数来自 config/train.yaml）。"""
    # 加载训练参数
    with open('config/train.yaml', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    YOLO(MODEL).train(data=DATA, **cfg)


if __name__ == '__main__':
    main()
