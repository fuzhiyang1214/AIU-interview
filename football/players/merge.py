"""football/players/merge.py — 两源合并（本模块是球员库的唯一对外入口）

职责：把 catalog（本地评分，离线、快、全）与 source（在线头像/简介，慢、少）
     缝成一张统一的球员卡，对外只暴露三个动作：搜索 / 取卡 / 榜单。
输入：搜索词、球员 id、榜单维度
输出：统一的球员卡 dict

合并策略：
  · **catalog 是主体** —— 身份、评分、俱乐部、位置都以本地为准；
  · **在线源只做补充** —— 头像、抠图、生日、简介；慢一点、可能失败，都是可选项；
  · 匹配靠归一化姓名：TheSportsDB 用英文全名（'Erling Haaland'），本地用 long_name，
    写法差异靠 catalog._norm 对齐；再叠一层「词序无关」兜底
    （'Son Heung-min' ↔ 'Heung Min Son'）。
  · **在线失败 = 静默降级**：返回纯离线卡（有评分、没头像），绝不报错、绝不白屏。

请求预算（重要的设计约束）：
  · 搜索列表：本地 + **1 次**在线搜索（把头像贴到结果上），约 1.5s；
  · 球员详情：**≤2 次**在线请求（搜索定位 → 拉简介），约 3s；
  · 榜单：默认**纯离线**（一屏 20 人逐个联网要 30s，不可接受）。
"""
import re
import unicodedata

from . import catalog
from . import source as _src


# ------------------------------------------------------------------ 名称工具
def _strip_accent(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c))


def _wordkey(s: str) -> str:
    """词序无关的姓名键：'Son Heung-min' 与 'Heung Min Son' 得到同一个值。"""
    parts = re.split(r"[^A-Za-z0-9]+", _strip_accent(s))
    return "".join(sorted(p.lower() for p in parts if p))


def _two_way(a: str, b: str) -> bool:
    """两种归一化都试一遍，任一相等即算同一个人。"""
    return catalog._norm(a) == catalog._norm(b) or _wordkey(a) == _wordkey(b)


def _match_online(p: dict, hits: list) -> dict | None:
    """在在线候选里找与本地球员 p 对应的那一条。"""
    for h in hits:
        if any(_two_way(n, h["name"]) for n in (p["name"], p["display"], p["alias"]) if n):
            return h
    return None


def _public(p: dict) -> dict:
    """去掉内部字段（_names 等），只留可以序列化的部分。"""
    return {k: v for k, v in p.items() if not k.startswith("_")}


# ------------------------------------------------------------------ 对外动作
def search_players(q: str, limit: int = 20, pos: str | None = None,
                   online: bool = True) -> list:
    """搜索球员：本地结果为骨架，联网把头像一个请求批量贴上去。"""
    rows = catalog.search(q, limit=limit, pos=pos)
    if not rows:
        return []

    if online:
        hits = _src.search(q, limit=10)          # 一次请求
        if hits:
            for p in rows:
                h = _match_online(p, hits)
                if h:
                    p["photo"] = h["cutout"] or h["thumb"]
                    p["tsdb_id"] = h["tsdb_id"]

    return [_public(p) for p in rows]


def player_card(sid, online: bool = True) -> dict | None:
    """取一张完整球员卡：本地评分 + 在线的头像与简介。"""
    p = catalog.get_by_id(sid)
    if not p:
        return None
    card = _public(p)

    if online:
        hits = _src.search(p["name"], limit=5)   # 第 1 次请求：定位
        h = _match_online(p, hits)
        if h:
            if not h.get("description") and h.get("tsdb_id"):
                h = _src.lookup(h["tsdb_id"]) or h    # 第 2 次请求：拿简介
            card["photo"] = h.get("cutout") or h.get("thumb") or ""
            card["description"] = h.get("description") or ""
            card["born"] = h.get("born") or ""
            card["tsdb_id"] = h.get("tsdb_id") or ""
            card["team_now"] = h.get("team") or ""
    return card


def rank_players(by: str = "overall", limit: int = 20, pos: str | None = None,
                 online: bool = False) -> list:
    """榜单。默认纯离线（快）；online=True 时给前几名补头像，慎用。"""
    rows = catalog.rank(by=by, limit=limit, pos=pos)
    if online and rows:
        for p in rows[:5]:                       # 只给前 5 名补，控制请求数
            hits = _src.search(p["name"], limit=3)
            h = _match_online(p, hits)
            if h:
                p["photo"] = h["cutout"] or h["thumb"]
    return [_public(p) for p in rows]
