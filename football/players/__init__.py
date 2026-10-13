"""football/players/__init__.py — 球员库入口

职责：把「本地球员目录 + 在线资料源」打包成三个动作，调用方无需知道底下有几个源。

对外暴露：
  search_players(q, limit, pos, online)   搜索球员（默认联网补头像）
  player_card(sid, online)                单张球员卡（评分 + 头像 + 简介）
  rank_players(by, limit, pos, online)    榜单（默认纯离线）
  stats()                                 库规模与可用排序维度
  warmup()                                预热，服务启动时调一次

数据分工：
  catalog.py  EA FC 数据集（本地、离线、18494 人、含全部评分）
  source.py   TheSportsDB（在线、免 key、头像/抠图/简介）
"""
from .catalog import RANK_KEYS, SIX, stats, warmup
from .merge import player_card, rank_players, search_players

__all__ = [
    "search_players", "player_card", "rank_players",
    "stats", "warmup", "RANK_KEYS", "SIX",
]
