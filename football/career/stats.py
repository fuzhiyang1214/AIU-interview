"""football/career/stats.py — 生涯统计聚合

职责：把「比赛 + 出场 + 自建球员」三张表合成生涯视角的数字，供生涯页直接渲染。

口径说明（写清楚，免得数字对不上）：
  · 场次/胜平负只算 matches 表，不看出场明细。
  · 球员生涯数据只统计 side='me' 的出场行。
  · 归并键：优先 player_id；没选「我的球队」而是手打名字的，按名字归并
    （COALESCE 让两类条目落在同一套分组里，不会出现同名两人两行）。
  · 场均评分只对填了评分的场次求平均，不会把空评分当 0 拉低。
"""
from . import db
from .squad import list_players


def _record() -> dict:
    """战绩汇总 + 进球/失球。"""
    with db.conn() as c:
        r = c.execute("""
            SELECT COUNT(*)                                              AS played,
                   COALESCE(SUM(goals_for > goals_against), 0)           AS won,
                   COALESCE(SUM(goals_for = goals_against), 0)           AS drawn,
                   COALESCE(SUM(goals_for < goals_against), 0)           AS lost,
                   COALESCE(SUM(goals_for), 0)                           AS goals_for,
                   COALESCE(SUM(goals_against), 0)                       AS goals_against
            FROM matches
        """).fetchone()
    d = dict(r)
    played = d["played"] or 0
    d["win_rate"] = round(100.0 * d["won"] / played, 1) if played else 0.0
    d["avg_for"] = round(d["goals_for"] / played, 2) if played else 0.0
    d["avg_against"] = round(d["goals_against"] / played, 2) if played else 0.0
    return d


def _per_player() -> dict:
    """按球员归并的出场统计。key = player_id(int) 或 'n:名字'。"""
    with db.conn() as c:
        rows = c.execute("""
            SELECT COALESCE(CAST(player_id AS TEXT), 'n:' || player_name) AS key,
                   MAX(player_name)                                        AS player_name,
                   COUNT(*)                                                AS apps,
                   COALESCE(SUM(goals), 0)                                 AS goals,
                   COALESCE(SUM(assists), 0)                               AS assists,
                   COALESCE(SUM(minutes), 0)                               AS minutes,
                   AVG(rating)                                             AS avg_rating
            FROM appearance
            WHERE side = 'me'
            GROUP BY key
        """).fetchall()
    out = {}
    for r in rows:
        d = dict(r)
        d["avg_rating"] = round(d["avg_rating"], 2) if d["avg_rating"] is not None else None
        out[d.pop("key")] = d
    return out


def career_summary(recent: int = 5) -> dict:
    """生涯总览：战绩 + 我的球员生涯榜 + 最近比赛 + 个人纪录。"""
    rec = _record()
    by_key = _per_player()

    roster = []
    for p in list_players():
        s = by_key.pop(str(p["id"]), None) or {}
        roster.append({
            "player_id": p["id"],
            "name": p["name"],
            "position": p["position"],
            "overall": p["overall"],
            "best_position": p["best_position"],
            "apps": s.get("apps", 0),
            "goals": s.get("goals", 0),
            "assists": s.get("assists", 0),
            "minutes": s.get("minutes", 0),
            "avg_rating": s.get("avg_rating"),
        })
    # 只出现在比赛记录里、但没进「我的球队」的手动球员
    for key, s in by_key.items():
        if key.startswith("n:"):
            roster.append({
                "player_id": None, "name": s["player_name"], "position": None,
                "overall": None, "best_position": None,
                "apps": s["apps"], "goals": s["goals"], "assists": s["assists"],
                "minutes": s["minutes"], "avg_rating": s["avg_rating"],
            })

    roster.sort(key=lambda x: (x["goals"], x["assists"], x["apps"]), reverse=True)

    with db.conn() as c:
        rows = c.execute(
            "SELECT id, played_on, competition, my_team, opponent,"
            " goals_for, goals_against FROM matches"
            " ORDER BY played_on DESC, id DESC LIMIT ?",
            (max(1, int(recent)),)).fetchall()
    timeline = []
    for r in rows:
        m = dict(r)
        m["result"] = ("胜" if m["goals_for"] > m["goals_against"]
                       else "平" if m["goals_for"] == m["goals_against"] else "负")
        timeline.append(m)

    scorers = [x for x in roster if x["goals"] > 0][:5]
    return {
        "record": rec,
        "roster": roster,
        "timeline": timeline,
        "top_scorers": scorers,
        "players_tracked": sum(1 for x in roster if x["apps"] > 0),
    }
