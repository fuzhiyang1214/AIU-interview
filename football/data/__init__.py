"""football/data/__init__.py — 数据层入口

对外暴露：
  identify()  —— 把两队球衣颜色翻译成球队名称候选；
  schedule()  —— 查一支球队的近期赛程（走在线源，失败返回空）。
"""
from .matcher import identify, match_team, hex_to_hsv, schedule
from .sources import get_source, get_online

__all__ = ["identify", "match_team", "hex_to_hsv", "schedule", "get_source", "get_online"]
