# data/ · 足球数据源层（当前不参与主流程）

> ⚠️ **状态：备用 / 历史实现。** 按最新需求，作品**不再做球队识别**，
> 因此本层不接入 `app.py` / `analyze_cli.py` 的主流程。保留在此，需要"认球队 / 查赛程"时再接回来。

把「两队球衣颜色」翻译成「球队名称」，并可查真实赛程。

| 文件 | 职责 |
|---|---|
| `teams.json` | 离线球队库：队名、联赛、球衣主/副色、惯用阵型、打法风格（24 队） |
| `sources.py` | 数据源接口：`OfflineSource`（默认）与 `OnlineSource`（拉 openfootball 公开赛程，免 key） |
| `matcher.py` | 按 HSV 颜色反查最像的球队，返回候选排序 |
| `__init__.py` | 对外暴露 `identify()` 与 `schedule()` |

## 为什么默认离线

本机网络（校园网/DNS）不稳定，实时拉取会拖垮体验，所以把 `teams.json` 作为**稳定数据源**；
在线源做成**可选增强**——`OnlineSource` 拉 openfootball（GitHub raw，免 key）的 5 大联赛赛程，
失败自动回退离线。

## 匹配算法

```
颜色距离 = 色调环形距离 + 30×饱和度差 + 15×亮度差
一支球队取「主色/副色」中距离最近者为准
```

纯启发式，结果为候选排序而非唯一答案 —— 同色队服会并列，需结合联赛/语境人工确认。

## 在线源的边界（重要）

公开数据源（openfootball / football-data.org）**都不提供球衣颜色字段**。
所以在线源的价值是**扩充球队库 + 查询赛程**，**不能替代**颜色匹配 ——
「颜色负责分两伙，数据源负责点名」是流水线上的上下道工序，不是替代关系。

## 对外接口

```python
from data import identify, schedule
idents = identify(color_hsv_team0, color_hsv_team1, source="online")
idents["team0"]["best"]        # {"name","league","formation","style","score","in_schedule"}
schedule("阿森纳")             # 近期赛程（走在线源，失败返回 []）
```

## 扩展成在线数据源

继承 `sources.TeamSource`，实现 `teams()`，在 `get_online()` / `get_source()` 里挂上即可，
`matcher.py` 不用动。
