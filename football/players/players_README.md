# players/ · 球员库

> 任务五扩展。给「AI 战术分析师」补上一块球员资料库：**搜球员、看能力、出榜单**。
> 18494 名球员离线可查，点开一张卡就能看到总评、六维能力、身价和简介。

## 数据从哪来

| 用途 | 数据源 | 获取方式 | 实测 |
|---|---|---|---|
| **评分与属性** | [`mzafram2001/ea-fc`](https://github.com/mzafram2001/ea-fc) | 一次性下载 CSV 入库 | 5.7 MB ｜ **18494 人** ｜ 60 列 |
| **头像与简介** | [TheSportsDB](https://www.thesportsdb.com/) | 运行时按需拉取 | 免 key ｜ 单次 1.0 ~ 1.7 s |

> EA FC 数据集抓自 sofifa.com，覆盖 **FIFA 07 → EA FC 27** 共 21 个版本，本项目取最新一版（EA FC 26）。
> 仓库里的 `data/players_ea_fc.csv` 是**原始全量文件**（60 列），加载时只取需要的 22 列。

## 三个文件

| 文件 | 职责 | 关键约束 |
|---|---|---|
| `catalog.py` | 读 CSV、建索引、搜索 / 榜单 / 详情 | **纯离线**，绝不联网 |
| `source.py` | TheSportsDB 客户端（头像 / 简介） | 超时 8 s，**任何失败都返回空** |
| `merge.py` | 两源合并，对外唯一入口 | 在线失败 → 静默降级成纯离线卡 |

依赖是单向的：`merge → catalog / source`，谁都不反向依赖。

## 名字怎么对上（最容易翻车的地方）

两边写法不一样：TheSportsDB 叫 `Son Heung-min`，数据集里是 `Heung-Min Son`。做了两层归一化：

1. **抹平字符差异** —— 重音（`Vinícius` → `vinicius`）、连字符、空格、大小写
2. **词序无关兜底** —— 把名字拆词排序后比较，`Son Heung-min` 与 `Heung Min Son` 得到同一个键

抽样实测：**精确匹配 70%**（10 个名字里 3 个未命中），加归一化后可覆盖绝大多数常见写法差异。

**显示名也做了优选**：`alias` 字段 100% 有值，多数是常用名（`Vítor Machado Ferreira` → `Vitinha`、
`Pedro González López` → `Pedri`）；但少数是缩写（`E. Haaland`），凡是含 `.` 的就退回全名 ——
所以榜单上看到的是 `Vitinha`，而不是一长串法定全名。

## 请求预算（这是设计约束，不是实现细节）

联网慢，所以每个动作都定了上限：

| 动作 | 在线请求数 | 实测耗时 |
|---|---|---|
| 搜索 | **1 次**（一次把头像是批量贴到结果上） | ~1.0 s |
| 球员详情 | **≤2 次**（先定位，再拉简介） | ~1.2 ~ 1.7 s |
| 榜单 | **0 次**（默认纯离线） | ~10 ms |

> 榜单默认不联网：一屏 20 人逐个拉要 30 秒，不可接受。需要头像时接口支持 `?online=1`。

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/player/stats` | 库规模与可用排序维度 |
| GET | `/api/player/search?q=&limit=&pos=&online=` | 按名字搜球员 |
| GET | `/api/player/rank?by=&limit=&pos=&online=` | 能力榜 |
| GET | `/api/player/<sid>?online=` | 球员详情卡 |

可排序维度：`overall` 总评 ｜ `potential` 潜力 ｜ `pace` 速度 ｜ `shooting` 射门 ｜ `passing` 传球 ｜
`dribbling` 盘带 ｜ `defending` 防守 ｜ `physical` 身体 ｜ `value_eur` 身价 ｜ `wage_eur` 周薪 ｜ `age` 年龄

## 怎么用

**Web** —— 打开 `http://127.0.0.1:8100`，顶部切到「球员库」，搜索或直接看榜单。

**Python**
```python
from players import search_players, player_card, rank_players

search_players("haaland", limit=5)            # 搜索（联网补头像）
player_card("239085")                         # 球员卡
rank_players(by="pace", pos="ST", limit=10)   # 速度最快的前锋
```

**Harness** —— 新增 `football_players` 工具，Agent 可直接查：
```
python harness\main.py --ask "速度最快的前锋是谁？顺便看看哈兰德的能力"
```

## 已知局限

| 局限 | 说明 |
|---|---|
| **球员名是英文** | 数据集与 TheSportsDB 都是英文名；中文名需另挂 Wikidata（数据集里有 `idWikidata` 字段，**未做**） |
| **能力值来自游戏** | EA FC 的能力值是**游戏设定**，不是真实比赛数据 —— 适合横向比较，不代表实际水平 |
| **匹配靠名字** | 极冷门球员或译名差异大的可能匹配不上头像（**评分不受影响**，评分走本地库） |
| **榜单默认无头像** | 榜单离线加载以保速度；要头像请加 `?online=1` |
