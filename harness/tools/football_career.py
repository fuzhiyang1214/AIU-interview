"""harness/tools/football_career.py — 「我的足球生涯」查询工具（复用任务五的生涯库）

职责：让 Agent 具备"看自己生涯"的能力 —— 生涯总览、我的球队名单、单个球员的
      能力卡与成长曲线、比赛记录、单场出场明细、评分规则。

输入：action（summary / players / player / matches / match / ratings）及对应参数
输出：人类可读的文本

★ 刻意只做"读"：
  自建球员、录入比赛这类"写"动作全部留给前端（football/static/index.html）。
  让模型自由发挥去填年龄 / 能力值 / 比分，很容易写进一堆脏数据，而且结构化录入
  本来就是表单更擅长的事。Agent 在这里的价值是"读 + 解读"，不是当录入器。

★ 不用子进程桥接（同 football_players.py）：生涯库只用 sqlite3 + 标准库，
  系统 Python 直接 import 即可。判断标准仍是那句：**要不要 torch？**
"""
import sys
from pathlib import Path

NAME = "football_career"

ROOT = Path(__file__).resolve().parents[2]
FOOTBALL_DIR = ROOT / "football"
if str(FOOTBALL_DIR) not in sys.path:
    sys.path.insert(0, str(FOOTBALL_DIR))

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "查询用户在《我的足球生涯》里记录的数据（自建球员、比赛、战报统计）。"
            "可以看生涯总览（战绩 / 进球榜 / 最近比赛）、我的球队名单、"
            "单个球员的能力卡与成长曲线、比赛记录、单场出场明细。"
            "当用户问『我生涯几胜几负』『我的球队里谁进球最多』"
            "『上次那场比赛谁进球了』『我建的球员能力怎么样』时使用。"
            "（这是用户自己的数据，不是真实球员资料 —— 查真实球员请用 football_players）"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["summary", "players", "player", "matches", "match", "ratings"],
                    "description": "summary=生涯总览（战绩+球员榜+最近比赛，默认）；"
                                   "players=我的球队名单；player=单个球员能力卡+成长曲线；"
                                   "matches=比赛列表；match=单场出场明细；"
                                   "ratings=总评的算法与位置权重表",
                },
                "player_id": {
                    "type": "integer",
                    "description": "action=player 时的球员 id（从 action=players 的结果里取）",
                },
                "match_id": {
                    "type": "integer",
                    "description": "action=match 时的比赛 id（从 action=matches 的结果里取）",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回条数，默认 10，最多 50",
                },
            },
            "required": ["action"],
        },
    },
}


def _result(m: dict) -> str:
    """胜 / 平 / 负。"""
    gf, ga = m.get("goals_for", 0), m.get("goals_against", 0)
    return "胜" if gf > ga else "平" if gf == ga else "负"


def _line(i: int, p: dict) -> str:
    """球队名单里的一行。"""
    parts = [f"{i:2d}. {p['name']}（{p.get('position') or '-'}）总评 {p.get('overall')}"]
    if p.get("age"):
        parts.append(f"{p['age']} 岁")
    if p.get("best_position") and p["best_position"] != p.get("position"):
        parts.append(f"建议位置 {p['best_position']}({p['best_overall']})")
    parts.append(f"id={p.get('id')}")
    return "｜".join(parts)


def _app_line(a: dict) -> str:
    """出场明细里的一行。"""
    bits = [f"{a['player_name']}（{a.get('position') or '-'}）"]
    if a.get("minutes"):
        bits.append(f"{a['minutes']}′")
    if a.get("goals"):
        bits.append(f"进球{a['goals']}")
    if a.get("assists"):
        bits.append(f"助攻{a['assists']}")
    if a.get("rating") is not None:
        bits.append(f"评分{a['rating']}")
    return "｜".join(bits)


def run(action: str = "summary", player_id=None, match_id=None, limit: int = 10) -> str:
    """执行一次生涯查询。异常交给 core/executor.py 兜住。"""
    try:
        from career import (ATTR_CN, ATTRS, career_summary, get_match, get_player,
                            init_db, list_matches, list_players, ratings_table,
                            snapshots)
    except Exception as e:
        return (f"生涯库不可用：{type(e).__name__}: {e}\n"
                f"（请确认 football/career/ 完整）")

    init_db()          # 幂等：首次调用时建库建表
    action = (action or "summary").strip().lower()
    limit = max(1, min(int(limit or 10), 50))

    # ---- 评分规则 ----------------------------------------------------------
    if action == "ratings":
        t = ratings_table()
        lines = ["总评 = 该位置六维能力的加权平均（每个位置的权重和为 1）。",
                 "六维：" + "、".join(f"{ATTR_CN[k]}({k})" for k in ATTRS),
                 "各位置最看重的三项能力："]
        for pos in t["positions"]:
            w = t["weights"][pos]
            top = sorted(w.items(), key=lambda kv: kv[1], reverse=True)[:3]
            lines.append(f"  {pos:3s} " + " / ".join(
                f"{ATTR_CN[k]} {int(v * 100 + 0.5)}%" for k, v in top))
        return "\n".join(lines)

    # ---- 我的球队 ----------------------------------------------------------
    if action == "players":
        rows = list_players()
        if not rows:
            return "我的球队还是空的 —— 在前端「我的球队」页新建球员（本工具只读，不代建）。"
        return (f"我的球队共 {len(rows)} 人（按总评从高到低，展示前 {min(limit, len(rows))} 人）：\n"
                + "\n".join(_line(i, p) for i, p in enumerate(rows[:limit], 1)))

    # ---- 单个球员 ----------------------------------------------------------
    if action == "player":
        if player_id in (None, ""):
            return "请提供 player_id（先用 action=players 拿 id）。"
        p = get_player(int(player_id))
        if not p:
            return f"查无此人（id={player_id}）。先用 action=players 看名单。"
        six = " ".join(f"{ATTR_CN[k]}{p.get(k)}" for k in ATTRS)
        lines = [f"{p['name']}（{p.get('position') or '-'}）总评 {p.get('overall')}",
                 f"  {p.get('age') or '-'} 岁｜{p.get('foot') or '-'}"
                 f"｜号码 {p.get('shirt_no') or '-'}｜潜力 {p.get('potential') or '-'}",
                 f"  六维：{six}"]
        if p.get("best_position") and p["best_position"] != p.get("position"):
            lines.append(f"  建议位置：{p['best_position']}（总评 {p['best_overall']}）")
        snaps = snapshots(int(player_id))
        if snaps:
            curve = " → ".join(str(s["overall"]) for s in snaps)
            lines.append(f"  成长曲线（{len(snaps)} 条快照）：{curve}")
        if (p.get("note") or "").strip():
            lines.append("  备注：" + p["note"].strip())
        return "\n".join(lines)

    # ---- 比赛列表 ----------------------------------------------------------
    if action == "matches":
        rows = list_matches(limit=limit)
        if not rows:
            return "还没有比赛记录 —— 在前端「比赛记录」页录入。"
        lines = [f"最近 {len(rows)} 场比赛（新的在前）："]
        for m in rows:
            lines.append(
                f"  {m['played_on']} {m.get('competition') or '—'} "
                f"{m['my_team']} {m['goals_for']}-{m['goals_against']} {m['opponent']} "
                f"{_result(m)}（出场 {len(m.get('appearances') or [])} 人）｜id={m['id']}")
        return "\n".join(lines)

    # ---- 单场明细 ----------------------------------------------------------
    if action == "match":
        if match_id in (None, ""):
            return "请提供 match_id（先用 action=matches 拿 id）。"
        m = get_match(int(match_id))
        if not m:
            return f"查无此比赛（id={match_id}）。先用 action=matches 看列表。"
        lines = [f"{m['played_on']} {m.get('competition') or '—'}",
                 f"{m['my_team']} {m['goals_for']}-{m['goals_against']} "
                 f"{m['opponent']}（{_result(m)}）"]
        apps = m.get("appearances") or []
        for side, label in (("me", "我方"), ("opp", "对手")):
            group = [a for a in apps if a.get("side") == side]
            if not group:
                continue
            lines.append(f"{label}出场 {len(group)} 人：")
            lines.extend("  " + _app_line(a) for a in group)
        if (m.get("note") or "").strip():
            lines.append("备注：" + m["note"].strip())
        return "\n".join(lines)

    # ---- 生涯总览（默认）---------------------------------------------------
    if action == "summary":
        s = career_summary(recent=min(limit, 20))
        r = s["record"]
        lines = [f"我的足球生涯：共 {r['played']} 场"
                 f"（胜 {r['won']} / 平 {r['drawn']} / 负 {r['lost']}，胜率 {r['win_rate']}%），"
                 f"进 {r['goals_for']} 失 {r['goals_against']}"
                 f"（场均 {r['avg_for']} - {r['avg_against']}）"]
        roster = s["roster"][:min(limit, 10)]
        if roster:
            lines.append(f"球员生涯榜（共 {s['players_tracked']} 人有出场，按进球排序）：")
            for i, x in enumerate(roster, 1):
                tail = (f"｜场均评分 {x['avg_rating']}"
                        if x.get("avg_rating") is not None else "")
                lines.append(f"  {i:2d}. {x['name']}（{x.get('position') or '—'}）"
                             f"出场 {x['apps']}｜进球 {x['goals']}"
                             f"｜助攻 {x['assists']}{tail}")
        if s["timeline"]:
            lines.append("最近比赛：")
            for m in s["timeline"]:
                lines.append(f"  {m['played_on']} {m['my_team']} "
                             f"{m['goals_for']}-{m['goals_against']} "
                             f"{m['opponent']} {m['result']}")
        return "\n".join(lines)

    return f"未知 action：{action}（可选 summary / players / player / matches / match / ratings）"
