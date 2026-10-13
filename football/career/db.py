"""football/career/db.py — 生涯数据库（SQLite）

职责：建表、提供连接、定义 schema。用 Python 标准库 sqlite3，**零新增依赖**。

数据文件：football/data/career.db（个人生涯数据，不应提交到仓库；
          仓库里靠 .gitignore 排除，程序首次运行会自动建库建表）

五张表：
  my_player    自建球员（六维能力 + 位置 + 基本信息）
  player_snap  能力快照：每次改动留一条，用于画「成长曲线」
  formation    战术板存档（我方/对手站位 + 球位，坐标存 JSON）
  matches      比赛记录（对手 / 比分 / 赛事 / 备注）
  appearance   出场明细（谁上了、踢哪、进球、助攻、评分）

设计取舍：
  每次操作新建一个连接（本地文件开销在微秒级），换取「多线程下绝对安全」——
  Flask 是 threaded=True，共享连接会踩 sqlite 的线程限制。
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

# career/ → football/ → data/career.db
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = Path(os.environ.get("FOOTBALL_CAREER_DB", DATA_DIR / "career.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS my_player (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    position    TEXT    NOT NULL DEFAULT 'CM',
    age         INTEGER,
    shirt_no    INTEGER,
    foot        TEXT    DEFAULT '右脚',
    pace        INTEGER NOT NULL DEFAULT 60,
    shooting    INTEGER NOT NULL DEFAULT 60,
    passing     INTEGER NOT NULL DEFAULT 60,
    dribbling   INTEGER NOT NULL DEFAULT 60,
    defending   INTEGER NOT NULL DEFAULT 60,
    physical    INTEGER NOT NULL DEFAULT 60,
    potential   INTEGER,
    note        TEXT    DEFAULT '',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS player_snap (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id  INTEGER NOT NULL,
    overall    INTEGER NOT NULL,
    position   TEXT,
    taken_at   TEXT    NOT NULL,
    FOREIGN KEY (player_id) REFERENCES my_player(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_snap_player ON player_snap(player_id, id);

CREATE TABLE IF NOT EXISTS formation (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    my_label   TEXT    DEFAULT '我方',
    opp_label  TEXT    DEFAULT '对手',
    slots      TEXT    NOT NULL,
    ball       TEXT,
    note       TEXT    DEFAULT '',
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    played_on     TEXT    NOT NULL,
    competition   TEXT    DEFAULT '',
    my_team       TEXT    NOT NULL,
    opponent      TEXT    NOT NULL,
    goals_for     INTEGER NOT NULL DEFAULT 0,
    goals_against INTEGER NOT NULL DEFAULT 0,
    formation_id  INTEGER,
    note          TEXT    DEFAULT '',
    created_at    TEXT    NOT NULL,
    FOREIGN KEY (formation_id) REFERENCES formation(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS appearance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER NOT NULL,
    player_id   INTEGER,
    player_name TEXT    NOT NULL,
    side        TEXT    NOT NULL DEFAULT 'me',
    position    TEXT,
    minutes     INTEGER DEFAULT 0,
    goals       INTEGER DEFAULT 0,
    assists     INTEGER DEFAULT 0,
    rating      REAL,
    note        TEXT    DEFAULT '',
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_app_match ON appearance(match_id);
CREATE INDEX IF NOT EXISTS idx_app_player ON appearance(player_id);
"""


def now() -> str:
    """统一的本地时间戳（SQLite 自带 CURRENT_TIMESTAMP 是 UTC，不用它）。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def conn():
    """拿一个连接，正常结束自动提交、异常自动回滚、无论如何都关闭。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")      # 否则 ON DELETE CASCADE 不生效
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init() -> str:
    """建库建表（幂等）。返回数据库文件路径，便于启动时打印。"""
    with conn() as c:
        c.executescript(SCHEMA)
    return str(DB_PATH)


def rows_to_dicts(rows) -> list:
    return [dict(r) for r in rows]


def load_json(text, default=None):
    """读 JSON 列，坏数据不抛异常（返回 default）。"""
    if not text:
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default
