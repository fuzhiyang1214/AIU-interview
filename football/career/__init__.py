"""football/career/__init__.py — 「我的足球生涯」数据层入口

职责：把球员 / 阵容 / 比赛 / 统计四块打包成一个层次，调用方（app.py）不用关心表结构。

对外暴露：
  init_db()                        建库建表（服务启动时调一次）
  ratings_table()                  评分规则的描述（位置列表 / 六维名），前端据此建表单
  rate()                           六维 + 位置 → 总评（**求解总评只此一处**）
  list_players / create_player / update_player / delete_player / snapshots
  list_formations / create_formation / update_formation / delete_formation
  list_matches / get_match / create_match / update_match / delete_match
  career_summary()                 生涯总览统计

存储：SQLite（标准库），文件在 football/data/career.db，首次运行自动创建。
"""
from .db import DB_PATH, init as init_db
from .formations import (create_formation, delete_formation, get_formation,
                         list_formations, update_formation)
from .matches import (create_match, delete_match, get_match, list_matches,
                      update_match)
from .ratings import ATTR_CN, ATTRS, POSITIONS, rate, weights_table
from .squad import (create_player, delete_player, get_player, list_players,
                    snapshots, update_player)
from .stats import career_summary


def ratings_table() -> dict:
    """评分规则的完整描述（给前端：位置列表 + 六维名；权重供公开口径）。"""
    return {**weights_table(), "attrs_cn": ATTR_CN}


__all__ = [
    "init_db", "DB_PATH", "ratings_table", "rate", "ATTRS", "ATTR_CN", "POSITIONS",
    "list_players", "get_player", "create_player", "update_player",
    "delete_player", "snapshots",
    "list_formations", "get_formation", "create_formation",
    "update_formation", "delete_formation",
    "list_matches", "get_match", "create_match", "update_match", "delete_match",
    "career_summary",
]
