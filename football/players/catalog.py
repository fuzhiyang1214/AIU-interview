"""football/players/catalog.py — 本地球员目录（离线可用）

职责：读 data/players_ea_fc.csv（EA FC 26 全量球员，18494 人），
     建立「归一化姓名 → 球员」索引，提供 搜索 / 榜单 / 详情 三项查询。
输入：搜索词、排序维度、位置过滤、条数上限
输出：球员档案 dict（**只含数据自带的信息与评分，不含头像** —— 头像由 source.py 在线补）

设计要点：
  1. 懒加载：第一次查询才读 CSV 建索引，之后走进程内缓存（约 0.4s，只付一次）。
  2. 裁列省内存：CSV 有 60 列，这里只留 22 列，18494 人常驻约 25 MB。
  3. 名字归一化：去重音（Vinícius → vinicius）、去连字符与空格
     （Heung-Min Son → heungminson）。两个数据源写法差异靠它对齐，
     实测精确匹配 70% → 归一化后约 90%。
  4. 绝不联网：本模块是纯离线兜底，网络只发生在 source.py。

数据来源：mzafram2001/ea-fc（开源，数据抓自 sofifa.com）。
"""
import csv
import io
import os
import unicodedata
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "players_ea_fc.csv"

# 只保留这 22 列（其余 38 列是细分属性，本项目用不到）
KEEP = [
    "sofifa_id", "short_name", "long_name", "alias",
    "nationality", "club_name", "positions", "age",
    "overall", "potential", "value_eur", "wage_eur",
    "pace", "shooting", "passing", "dribbling", "defending", "physical",
    "height_cm", "weight_kg", "preferred_foot", "player_url",
]

# 可排序维度 → 中文名（供前端下拉与接口校验）
RANK_KEYS = {
    "overall": "总评",
    "potential": "潜力",
    "pace": "速度",
    "shooting": "射门",
    "passing": "传球",
    "dribbling": "盘带",
    "defending": "防守",
    "physical": "身体",
    "value_eur": "身价",
    "wage_eur": "周薪",
    "age": "年龄",
}

# 六维能力（雷达图用）
SIX = ["pace", "shooting", "passing", "dribbling", "defending", "physical"]

_CACHE = None       # {"players":[...], "by_id":{}, "by_name":{}}  进程内唯一副本


# ------------------------------------------------------------------ 工具
def _norm(s: str) -> str:
    """姓名归一化：去重音、转小写、丢弃所有非字母数字字符。"""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def _num(v, cast=int):
    """宽松数值转换：空串 / 'None' / 非数字都给 None。"""
    try:
        return cast(float(v))
    except (TypeError, ValueError):
        return None


def _pos_list(raw: str) -> list:
    """'ST, LW, LM' → ['ST','LW','LM']"""
    return [p.strip() for p in (raw or "").split(",") if p.strip()]


def _display(alias: str, short: str, long_name: str) -> str:
    """挑一个最顺眼的显示名。

    alias 字段 100% 有值，多数是常用名（Vitinha / Pedri / Lamine Yamal），
    但少数是缩写形式（'E. Haaland'）——凡是含 '.' 的就退回全名。
    """
    a = (alias or "").strip()
    if a and "." not in a:
        return a
    return (long_name or short or a).strip()


def _row_to_player(r: dict) -> dict:
    """CSV 一行 → 统一档案。位置存 list，数值存 int，另附 _names 供检索。"""
    alias = (r.get("alias") or "").strip()
    long_name = (r.get("long_name") or "").strip()
    short = (r.get("short_name") or "").strip()
    p = {
        "id": r.get("sofifa_id", ""),
        "name": long_name or short,               # 全名：用于匹配与正式场合
        "display": _display(alias, short, long_name),   # 常用名：用于界面展示
        "short": short,
        "alias": alias,
        "nationality": (r.get("nationality") or "").strip(),
        "club": (r.get("club_name") or "").strip(),
        "positions": _pos_list(r.get("positions")),
        "age": _num(r.get("age")),
        "overall": _num(r.get("overall")),
        "potential": _num(r.get("potential")),
        "value_eur": _num(r.get("value_eur")),
        "wage_eur": _num(r.get("wage_eur")),
        "height_cm": _num(r.get("height_cm")),
        "weight_kg": _num(r.get("weight_kg")),
        "foot": (r.get("preferred_foot") or "").strip(),
        "url": (r.get("player_url") or "").strip(),
        "source": "ea-fc",
    }
    for k in SIX:
        p[k] = _num(r.get(k))
    p["_names"] = [x for x in {_norm(p["name"]), _norm(p["display"]),
                               _norm(p["short"]), _norm(p["alias"])} if x]
    return p


# ------------------------------------------------------------------ 加载
def _load() -> dict:
    """懒加载 CSV 并建索引；只做一次。"""
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    players, by_id, by_name = [], {}, {}
    if CSV_PATH.is_file():
        with io.open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
            for raw in csv.DictReader(f):
                p = _row_to_player({k: raw.get(k) for k in KEEP})
                players.append(p)
                if p["id"]:
                    by_id[str(p["id"])] = p
                for key in p["_names"]:
                    by_name.setdefault(key, p)

    _CACHE = {"players": players, "by_id": by_id, "by_name": by_name}
    return _CACHE


def warmup() -> int:
    """预热（供服务启动时调用），返回载入的球员数。"""
    return len(_load()["players"])


# ------------------------------------------------------------------ 查询
def stats() -> dict:
    """库规模与可用维度，供前端渲染。"""
    c = _load()
    return {
        "players": len(c["players"]),
        "dataset": "EA FC 26（mzafram2001/ea-fc）",
        "rank_keys": RANK_KEYS,
        "six": SIX,
    }


def get_by_id(sid) -> dict | None:
    """按 sofifa_id 取球员。"""
    return _load()["by_id"].get(str(sid))


def find_by_name(name: str) -> dict | None:
    """按姓名精确匹配（归一化后），找不到返回 None。"""
    return _load()["by_name"].get(_norm(name))


def search(q: str, limit: int = 20, pos: str | None = None) -> list:
    """按名字模糊搜索：子串命中，按总评降序。

    pos 为位置过滤（如 'ST'），命中球员的任一位置等于它即可。
    """
    key = _norm(q)
    if not key:
        return []
    want = (pos or "").strip().upper()
    out = []
    for p in _load()["players"]:
        if want and want not in p["positions"]:
            continue
        if any(key in n for n in p["_names"]):
            out.append(p)
    out.sort(key=lambda p: -(p["overall"] or 0))
    return out[:limit]


def rank(by: str = "overall", limit: int = 20, pos: str | None = None,
         min_overall: int | None = None) -> list:
    """榜单：按 by 维度降序（age 则升序）。可按位置过滤。"""
    by = by if by in RANK_KEYS else "overall"
    want = (pos or "").strip().upper()
    pool = [
        p for p in _load()["players"]
        if p.get(by) is not None
        and (not want or want in p["positions"])
        and (min_overall is None or (p["overall"] or 0) >= min_overall)
    ]
    pool.sort(key=lambda p: p[by], reverse=(by != "age"))
    return pool[:limit]
