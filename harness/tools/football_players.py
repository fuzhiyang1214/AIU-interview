"""harness/tools/football_players.py — 球员资料与能力查询工具（复用任务五的球员库）

职责：让 Agent 具备「查球员」的能力 —— 按名字搜球员、按能力维度出榜单、
     拉单个球员的能力卡（总评 / 六维 / 身价 / 简介）。
输入：action（search / rank / card / stats）及对应参数
输出：人类可读的文本

★ 与 football_tactics 的实现方式不同：
  战术分析依赖 torch，必须走 subprocess 桥到 yolo venv；
  而球员库是**纯标准库**实现（csv + urllib），系统 Python 直接就能跑，
  所以这里直接 import —— 更快，也少一层进程。
  core 同样无感：本工具只是往注册表里多加了一个名字。
"""
import sys
from pathlib import Path

NAME = "football_players"

ROOT = Path(__file__).resolve().parents[2]
FOOTBALL_DIR = ROOT / "football"
if str(FOOTBALL_DIR) not in sys.path:
    sys.path.insert(0, str(FOOTBALL_DIR))

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "查询足球球员的资料与能力值（本地 EA FC 数据集，18494 名球员）。"
            "可以按名字搜索球员、按某项能力出排行榜、查看单个球员的能力卡。"
            "当用户问『梅西能力怎么样』『速度最快的前锋是谁』『帮我查哈兰德』"
            "『身价最高的球员』时使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "rank", "card", "stats"],
                    "description": "search=按名字搜球员；rank=能力排行榜；"
                                   "card=单个球员的能力卡；stats=球员库规模",
                },
                "query": {
                    "type": "string",
                    "description": "action=search 时的球员名（英文更容易命中）",
                },
                "player_id": {
                    "type": "string",
                    "description": "action=card 时的球员 id（search 结果里会给）",
                },
                "by": {
                    "type": "string",
                    "description": "action=rank 的排序维度：overall(总评) / potential(潜力) / "
                                   "pace(速度) / shooting(射门) / passing(传球) / "
                                   "dribbling(盘带) / defending(防守) / physical(身体) / "
                                   "value_eur(身价) / wage_eur(周薪) / age(年龄)",
                },
                "position": {
                    "type": "string",
                    "description": "位置过滤，如 ST / CM / GK / CB（可选）",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回条数，默认 10，最多 30",
                },
            },
            "required": ["action"],
        },
    },
}


def _money(v) -> str:
    """金额格式化：欧元 → 亿 / 万。"""
    if v is None:
        return "—"
    if v >= 1e8:
        return f"{v / 1e8:.2f}亿€"
    if v >= 1e4:
        return f"{v / 1e4:.1f}万€"
    return f"{v}€"


def _pos(p) -> str:
    return "/".join(p.get("positions") or []) or "-"


def _brief(i: int, p: dict) -> str:
    """一行式摘要（榜单 / 搜索结果）。"""
    return (f"{i:2d}. {p['display']}（{p.get('club') or '—'}）{_pos(p)}"
            f"｜总评 {p.get('overall') or '—'}｜潜力 {p.get('potential') or '—'}"
            f"｜身价 {_money(p.get('value_eur'))}｜id={p.get('id')}")


def run(action: str = "search", query: str = None, player_id: str = None,
        by: str = "overall", position: str = None, limit: int = 10) -> str:
    """执行一次球员查询。异常交给 core/executor.py 兜住。"""
    try:
        from players import search_players, rank_players, player_card, stats
    except Exception as e:
        return (f"球员库不可用：{type(e).__name__}: {e}\n"
                f"（请确认 football/data/players_ea_fc.csv 存在）")

    action = (action or "search").strip().lower()
    limit = max(1, min(int(limit or 10), 30))
    position = (position or "").strip() or None

    if action == "stats":
        s = stats()
        keys = "、".join(f"{v}({k})" for k, v in s["rank_keys"].items())
        return f"球员库共 {s['players']} 名球员（{s['dataset']}）。\n可排序维度：{keys}"

    if action == "search":
        if not query:
            return "请提供 query（球员名）。"
        rows = search_players(query, limit=limit, pos=position)
        if not rows:
            return f"没有找到与「{query}」匹配的球员（库内是英文名，试试 Messi / Haaland 这种写法）。"
        return f"球员搜索「{query}」命中 {len(rows)} 人：\n" + "\n".join(
            _brief(i, p) for i, p in enumerate(rows, 1))

    if action == "rank":
        rows = rank_players(by=by, limit=limit, pos=position)
        if not rows:
            return f"没有符合条件的球员（by={by}，位置={position or '不限'}）。"
        title = f"{by} 排行榜 TOP {len(rows)}"
        if position:
            title += f"（位置 {position}）"
        return title + "：\n" + "\n".join(
            _brief(i, p) for i, p in enumerate(rows, 1))

    if action == "card":
        if not player_id:
            return "请提供 player_id（先用 action=search 拿到 id）。"
        p = player_card(player_id, online=True)
        if not p:
            return f"查无此人（id={player_id}）。先用 action=search 搜名字拿 id。"
        six = " ".join(f"{k}{p.get(k) if p.get(k) is not None else '—'}"
                       for k in ("pace", "shooting", "passing", "dribbling", "defending", "physical"))
        lines = [
            f"{p['display']}（{p.get('name') or ''}）",
            f"  俱乐部：{p.get('club') or '—'}｜国籍：{p.get('nationality') or '—'}｜位置：{_pos(p)}",
            f"  总评 {p.get('overall') or '—'}｜潜力 {p.get('potential') or '—'}"
            f"｜年龄 {p.get('age') or '—'}｜{p.get('height_cm') or '—'}cm / {p.get('weight_kg') or '—'}kg"
            f"｜惯用脚 {p.get('foot') or '—'}",
            f"  身价 {_money(p.get('value_eur'))}｜周薪 {_money(p.get('wage_eur'))}",
            f"  六维：{six}",
        ]
        desc = (p.get("description") or "").strip()
        if desc:
            lines.append("  简介：" + desc[:400] + ("…" if len(desc) > 400 else ""))
        return "\n".join(lines)

    return f"未知 action：{action}（可选 search / rank / card / stats）"
