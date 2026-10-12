"""football/data/sources.py — 足球数据源（可插拔）

职责：提供「球队资料从哪里来」的统一接口，并额外提供「查赛程」能力。
输入：无（或数据源名 / 查询参数）
输出：球队资料列表 [{"name","en","league","colors_hex",...}, ...]

两个数据源：
  - OfflineSource  读同目录 teams.json（24 队，含球衣颜色），**始终可用**，是兜底。
  - OnlineSource   拉 openfootball（GitHub 上的公开赛程库，**免 key**），
                   把「真实联赛 + 真实赛程」带进来，队色由本地库补。

设计要点（对应出题人「做减法」）：
  1. 离线优先：默认走本地 JSON，不联网也能跑；在线源只在显式指定时启用。
  2. 失败必回落：在线源任何异常（超时/断网/字段缺失）都被吞掉，
     由 get_source() 回退到离线，绝不让网络问题拖垮主流程。
  3. 归一到同一字段：在线队也会被规范成与 teams.json 相同的结构，
     matcher.py / brain/ 完全不用改。

★ 诚实声明：openfootball **不提供球衣颜色**，所以在线源只贡献
  「队名 + 联赛 + 赛程」，颜色仍由本地 teams.json 维护 —— 两者互补而非替代。
"""
import json
import urllib.request
from pathlib import Path

JSON_PATH = Path(__file__).resolve().parent / "teams.json"

# openfootball 赛程库的 raw 地址（免 key，公开仓库）
OPENFOOTBALL_RAW = "https://raw.githubusercontent.com/openfootball/football.json/master"

# 支持的联赛 → (文件路径, 中文名, 国家)。想加联赛在这里加一行即可。
LEAGUES = {
    "英超": ("2024-25/en.1.json", "英超", "英格兰"),
    "西甲": ("2024-25/es.1.json", "西甲", "西班牙"),
    "德甲": ("2024-25/de.1.json", "德甲", "德国"),
    "意甲": ("2024-25/it.1.json", "意甲", "意大利"),
    "法甲": ("2024-25/fr.1.json", "法甲", "法国"),
}

TIMEOUT = 8  # 秒。校园网慢，但也不能无限等 —— 超时就回落离线。


class TeamSource:
    """数据源接口。想接第三方 API，继承它并实现 teams() 即可。"""

    name = "base"

    def teams(self) -> list:
        raise NotImplementedError

    def schedule(self, team_name: str, limit: int = 5) -> list:
        """查一支球队的近期赛程。基类默认不支持，返回空。"""
        return []


class OfflineSource(TeamSource):
    """离线数据源：读同目录的 teams.json（含球衣颜色），永远可用。"""

    name = "offline"

    def teams(self) -> list:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)["teams"]


class OnlineSource(TeamSource):
    """在线数据源：openfootball 公开赛程库（免 key）。

    拉真实联赛的球队与赛程，规范成与 teams.json 相同字段。
    颜色不来自这里（数据源没有），留待 matcher 用本地库匹配。
    """

    name = "online"

    def __init__(self, leagues: list | None = None, timeout: int = TIMEOUT):
        self.leagues = leagues or list(LEAGUES.keys())
        self.timeout = timeout
        self._cache = None          # 拉到的原始赛程，进程内缓存，避免重复下载

    # ---------------------------------------------------------- 底层请求
    def _fetch(self, path: str) -> dict:
        """下载一个联赛 json，失败返回空 dict（绝不抛给上层）。"""
        url = f"{OPENFOOTBALL_RAW}/{path}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "football-tactics/1.0"})
            # 禁代理：与 brain/llm.py 同款，避免被系统代理劫持
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            return {}

    def _load(self) -> list:
        """拉取并缓存所有联赛的 matches。"""
        if self._cache is not None:
            return self._cache
        matches = []
        for _, (path, cn, country) in LEAGUES.items():
            data = self._fetch(path)
            for m in data.get("matches", []):
                matches.append({
                    "league": cn,
                    "country": country,
                    "round": m.get("round", ""),
                    "date": m.get("date", ""),
                    "team1": m.get("team1", ""),
                    "team2": m.get("team2", ""),
                    "score": m.get("score") or {},
                })
        self._cache = matches
        return matches

    # ---------------------------------------------------------- 对外能力
    def teams(self) -> list:
        """把赛程里出现的球队去重，输出与 teams.json 同结构的最小档案。"""
        seen = {}
        for m in self._load():
            for key in ("team1", "team2"):
                name = m[key]
                if name and name not in seen:
                    seen[name] = {
                        "name": name,                       # 在线源原名（英文）
                        "en": name,
                        "league": m["league"],
                        "country": m["country"],
                        "colors_hex": [],                   # ★ 数据源不提供颜色
                        "formation": None,
                        "style": None,
                        "source": "openfootball",
                    }
        return list(seen.values())

    def schedule(self, team_name: str, limit: int = 5) -> list:
        """查某队近期赛程（按日期升序）。team_name 支持中/英文模糊匹配。

        openfootball 只有英文名，所以中文（如「阿森纳」）会先查本地库翻成英文，
        再用英文去匹配赛程 —— 让用户怎么问都查得到。
        """
        if not team_name:
            return []
        # 中文队名 → 英文别名（用本地 teams.json 做小词典）
        aliases = {_norm(team_name)}
        alias = _zh2en(team_name)
        if alias:
            aliases.add(_norm(alias))

        out = []
        for m in self._load():
            t1, t2 = _norm(m["team1"]), _norm(m["team2"])
            if any(a and (a in t1 or a in t2) for a in aliases):
                out.append({
                    "league": m["league"], "round": m["round"], "date": m["date"],
                    "home": m["team1"], "away": m["team2"],
                    "score": _fmt_score(m["score"]),
                })
        out.sort(key=lambda x: x["date"])
        return out[:limit]


def _zh2en(name: str) -> str | None:
    """中文队名 → 英文名（查本地 teams.json 的小词典）；查不到返回 None。"""
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            for t in json.load(f)["teams"]:
                if name == t["name"]:
                    return t.get("en")
    except Exception:
        pass
    return None


def _norm(s: str) -> str:
    """队名归一化：小写、去常见后缀、去空格，便于模糊匹配。"""
    s = (s or "").lower()
    for suffix in (" fc", " afc", " sc", " cf", " ac"):
        s = s.replace(suffix, "")
    return s.replace(" ", "").strip()


def _fmt_score(score: dict) -> str:
    """把 {'ft':[2,1]} 之类渲染成 '2-1'；没有则返回空串。"""
    ft = score.get("ft")
    if isinstance(ft, list) and len(ft) == 2:
        return f"{ft[0]}-{ft[1]}"
    return ""


def get_source(name: str = "offline") -> TeamSource:
    """按名字取数据源；在线源不可用时**自动回退离线**。"""
    if name == "online":
        online = OnlineSource()
        try:
            if online.teams():          # 拿不到任何球队 → 视为不可用
                return online
        except Exception:
            pass
    return OfflineSource()


def get_online() -> OnlineSource:
    """直接拿在线源实例，供「查赛程」这类需要真实数据的场景使用。

    与 get_source 不同：这里**不做回落**，调用方需要自行处理空结果。
    """
    return OnlineSource()
