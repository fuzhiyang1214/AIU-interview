"""football/players/source.py — 在线球员资料源（TheSportsDB，免 key）

职责：补本地 CSV 没有的东西 —— 球员头像 / 抠图 PNG、出生日期、现效力球队、
     身高体重、惯用脚、文字简介。
输入：搜索词，或 TheSportsDB 的球员 id
输出：统一的补充信息 dict；**任何失败都返回空，绝不抛异常**

与 data/sources.py 同款约定：
  1. TIMEOUT=8：校园网慢，但也不能无限等 —— 超了就当作没联网。
  2. ProxyHandler({})：禁代理，否则会被系统代理劫持（与 brain/llm.py 一致）。
  3. 进程内缓存：同一个查询不重复联网。
  4. 只用公开测试 key（'3'）：TheSportsDB 允许免注册访问，无需申请。

★ 诚实声明：TheSportsDB **不提供能力评分** —— 评分来自本地的 EA FC 数据集
  （见 catalog.py）。本模块只负责「脸和信息」。
"""
import json
import urllib.parse
import urllib.request

BASE = "https://www.thesportsdb.com/api/v1/json/3"
TIMEOUT = 8

_CACHE = {}


def _get(path: str) -> dict:
    """发一次 GET，返回 JSON；任何异常（超时/断网/坏 JSON）都返回 {}。"""
    url = f"{BASE}/{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "football-tactics/1.0"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return {}


def _pick(raw: dict) -> dict:
    """原始 JSON → 我们关心的字段。"""
    return {
        "tsdb_id": raw.get("idPlayer") or "",
        "name": (raw.get("strPlayer") or "").strip(),
        "team": (raw.get("strTeam") or "").strip(),
        "thumb": (raw.get("strThumb") or "").strip(),      # 头像（方形 jpg）
        "cutout": (raw.get("strCutout") or "").strip(),     # 抠图（透明 png，优先用）
        "nationality": (raw.get("strNationality") or "").strip(),
        "born": (raw.get("dateBorn") or "").strip(),
        "position": (raw.get("strPosition") or "").strip(),
        "number": (raw.get("strNumber") or "").strip(),
        "height": (raw.get("strHeight") or "").strip(),
        "weight": (raw.get("strWeight") or "").strip(),
        "foot": (raw.get("strSide") or "").strip(),
        "status": (raw.get("strStatus") or "").strip(),
        "description": (raw.get("strDescriptionEN") or "").strip(),
        "wikidata": (raw.get("idWikidata") or "").strip(),
    }


def search(name: str, limit: int = 5) -> list:
    """按姓名搜球员，返回候选列表（含头像）。失败返回 []。"""
    key = ("search", name.strip().lower(), limit)
    if key in _CACHE:
        return _CACHE[key]
    data = _get("searchplayers.php?" + urllib.parse.urlencode({"p": name}))
    out = [_pick(x) for x in (data.get("player") or [])[:limit]]
    _CACHE[key] = out
    return out


def lookup(tsdb_id: str) -> dict | None:
    """按 TheSportsDB 球员 id 取详情（含简介）。失败返回 None。"""
    if not tsdb_id:
        return None
    key = ("lookup", str(tsdb_id))
    if key in _CACHE:
        return _CACHE[key]
    data = _get("lookupplayer.php?" + urllib.parse.urlencode({"id": tsdb_id}))
    arr = data.get("players") or []
    out = _pick(arr[0]) if arr else None
    _CACHE[key] = out
    return out


def clear_cache():
    """清空缓存（调试用）。"""
    _CACHE.clear()
