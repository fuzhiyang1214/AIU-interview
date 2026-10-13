"""football/tactics/__init__.py — 手动战术板入口

职责：给「用户自己摆站位」这条路提供分析能力，与图像检测那条路并列。

对外暴露：
  analyze_board(slots, ball, size)   站位 → 与图像分析同构的结果
  summarize(analysis, labels)        压成一句人话
  preset_slots(name, team)           一键铺开起点站位
  catalog()                          位置列表与模板列表
  PITCH_W / PITCH_H                  逻辑画布尺寸

与 vision/ 的关系：本模块**不重写判定逻辑**，只把坐标喂给 vision/pitch.py。
两条输入路径（检测 / 手动）最终汇入同一个判定内核，结论口径天然一致。
"""
from .board import PITCH_H, PITCH_W, analyze_board, summarize
from .positions import POSITIONS_CN, PRESETS, catalog, preset_slots

__all__ = [
    "analyze_board", "summarize", "preset_slots", "catalog",
    "POSITIONS_CN", "PRESETS", "PITCH_W", "PITCH_H",
]
