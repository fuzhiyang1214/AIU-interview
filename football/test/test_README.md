# football/test/ — 创意作品测试证据

三类证据：**可复现的脚本 + 跑出来的完整终端输出 + 界面截图**。
脚本全部走「临时生涯库」，**不碰真实的 `career.db`**，跑完自动清理 —— 可以放心复跑。

## 环境

| 项 | 值 |
|---|---|
| 运行时 | `D:\envs\yolo`（Python 3.14 / torch 2.11.0+cu128 / ultralytics 8.4.173 / Flask 3.1.3） |
| 模型 | qwen2.5:7b（Ollama，`127.0.0.1:11434`）|
| 日期 | 2026-10-13 |

## 怎么复现

```bash
cd football\test

# ① 全接口自测（21 个路由 + 错误分支；约 35 s，含 YOLO 冷启 + 两张图）
D:\envs\yolo\Scripts\python.exe test_api.py

# ② 球衣分队自测（纯 cv2 合成画面，秒级）
D:\envs\yolo\Scripts\python.exe test_team_split.py

# ③ 攻守判定 + 预处理自测（纯 CPU，秒级）
D:\envs\yolo\Scripts\python.exe test_judge.py
```

留证据（重定向到文件即可逐行 diff）：

```bash
D:\envs\yolo\Scripts\python.exe test_api.py > api_result.txt 2>&1
D:\envs\yolo\Scripts\python.exe test_team_split.py > team_split_result.txt 2>&1
D:\envs\yolo\Scripts\python.exe test_judge.py > judge_result.txt 2>&1
```

## ① 接口自测：47 / 47 通过

用 Flask `test_client`，**不起真实端口**。负向用例（缺参数 → 400、查无此 id → 404）与正向用例**分开统计**。

| 分区 | 覆盖 | 实测耗时 |
|---|---|---|
| 页面与静态接口 | `/`、`/api/state`、`/api/tactics/meta` | < 5 ms |
| 球员库 | 搜索 / 11 维榜单 / 能力卡 / 统计（`online=0` 强制离线） | 9.6 ms ｜ 7.8 ms |
| 战术板 | 空板 400 ｜ 正常推演 ｜ 单人不崩 | 0.4 ms |
| 我的生涯 | 规则表 / **实时总评** / 球员 / 阵容 / 比赛 / 出场明细 全 CRUD + 快照 | 0.2~75 ms |
| 战术推理 | `/api/advise`、`/api/ask`（需 Ollama 在跑） | 2.8 s ｜ 0.9 s |
| 图像分析 | 缺 `image` → 400 ｜ 普通照片（走「返回整幅」分支）｜ **球场实拍图（走「裁到球场」分支）** | 2.5 s（热）/ 12.4 s（冷启） |
| **错误分支** | 缺 `q` / 空球员名 / 空队名 / 空战术板 / 空问题 / 缺 image / id 不存在 | < 1 ms |

结果（完整输出见 `api_result.txt`）：

```
结果：47 / 47 通过
```

> 为什么图像分析要跑**两张**图：`pitch_roi` 有「返回整幅」和「裁到球场」两条分支，
> 前者返回纯 Python int、后者历史上返回的是 `np.int32`。普通照片只走前者 ——
> 于是「`TypeError: Object of type int32 is not JSON serializable`」能一路躲过测试。
> 现在用仓库里的 `11_tactic_before.png`（真实球场截图）把后一条分支也钉住。

> 同一张图还挂着一条 **CHECK 用例**（`unassigned 结构化 + 人数守恒`）：
> `/api/analyze` 里的 `unassigned` 必须是**结构化字段**（`{count, gk, unknown}`），
> 不能是判定层那个裸 int —— 前端靠 `a.unassigned.count` 才渲染「未计入（门将 / 裁判）」那一行。
> 它曾经被 `**geo` 展开时**同名覆盖** ⇒ 界面上**那一行永远不出现**
> （截图里「球员总数 9 = 5 + 3 + 1」，却看不到多出来的那 1 人）。
> 用例顺手守住人数守恒：`players == on_pitch + unassigned.count`。

> `/api/career/rate`（前端拖滑块的实时总评）实测 **0.2~0.6 ms** ——
> 比浏览器里自己算还快，所以把评分收回后端**不会**拖慢交互。

## ② 分队自测：10 / 10 通过

`team_split` 重写后的回归用例。合成画面**带草地背景**（复刻直播帧实测的草色 H≈39），
专门盯住旧实现的三个失效场景。

| # | 用例 | 预期 | 结果 |
|---|---|---|---|
| S1 | 基线 5v5（红 vs 蓝） | 5 / 5 | ✅ |
| S2 | 5v5 + **两个绿门将** | 5 / 5，门将**不计入** | ✅ |
| S3 | 5v5 + **黑衣裁判** | 5 / 5，裁判**不计入** | ✅ |
| S4 | 局部特写 2v1 + 绿门将 | 2 / 1，门将不计入 | ✅ |
| S5 | 红 vs **白**（一队无彩） | 5 / 5（走亮度通道） | ✅ |
| S6 | 红 vs 红（**两队同色**） | 6 / 0，**不硬分** | ✅ |
| E1 | 零球员 | 0 / 0，不崩 | ✅ |
| E2 | 单球员 | 1 / 0 | ✅ |
| E3 | 超小框（< 10px） | 不崩 | ✅ |
| E4 | `pitch.analyze` 跳过 `team=-1` | 人数不计入，`unassigned=1` | ✅ |

结果（完整输出见 `team_split_result.txt`）：

```
结果：10 / 10 通过
```

## ③ 攻守判定自测：15 / 15 通过

盯的是**把攻守判反**这条老账 —— 用例里站位**故意造得跟球权相反**，结论必须跟着「球在谁脚下」走。

| # | 用例 | 钉住的规则 |
|---|---|---|
| J1 | 球在 T1 脚下，站位却全在 T0 侧 | **谁控球谁进攻**（旧口径会按人数判反） |
| J2 | 球在 T0 脚下，站位却全在 T1 侧 | 同上，反向 |
| J3 | 球离所有球员都远 | **球权不明 → 相持**，不硬判 |
| J4 | 球没检出来（图像路径） | 同上：宁可说不知道 |
| J5 | 画面口径 | 纵深 = 画面**横轴**、通道 = 纵轴 |
| J6 | 战术板口径 | 纵深 = 画布**纵轴**、通道 = 横轴 |
| J7 | 空当统计 | 按**防守方**算，方向词要能对回画面 |
| J8 | 战术板不摆球 | 才走**越线人数**兜底 |
| J9 | 战术板摆球在对手脚下 | 走**控球判定**（压过兜底） |
| K1 | `pitch_roi` | 框住草地（带外扩）、不裁错 |
| K2 | 画面里没有草地 | 返回整幅（宁可不动） |
| K3 | `auto_imgsz` | 2.4 倍、32 整数倍、封顶 3200 |
| K4 | `filter_crowd` | 剔看台、留场上球员（含**踩白线**的） |
| K5 | `pick_ball` | 优先「在球员身上」的候选 |
| K6 | `pitch_roi` 返回值可 JSON 序列化 | **钉死「numpy 整数进不了 jsonify」这类坑** |

结果（完整输出见 `judge_result.txt`）：

```
结果：15 / 15 通过
```

> K6 的来历：`cv2.connectedComponentsWithStats` 返回的 `stats` 是 **np.int32**，
> 被直接塞进 `/api/analyze` 的响应里 → Flask 报
> `TypeError: Object of type int32 is not JSON serializable`。
> 坑在于**只有「真裁到球场」这条分支才踩得到**，普通照片（走「返回整幅」分支）测不出来 ——
> 所以单独立一条用例把它钉住。

## 两个设计点

| 设计 | 意义 |
|---|---|
| **生涯库自动指向临时文件** | 跑一百遍也不污染真实数据，考官可放心复跑 |
| **负向用例显式声明期望值** | 400 / 404 分支单独统计，不是只跑 happy path |

## 截图

| 文件 | 内容 |
|---|---|
| `11_tactic_before.png` | 战术分析 · **修 bug 前**（真实帧被读成 7 : 3） |
| `12_tactic_advise.png` | 战术分析 + 本地大模型的战术建议 |
| `13_tactics_board.png` | 手动战术板（4-4-2 摆位） |
| `14_career_squad.png` | 我的球队（自建球员 / 六维滑块） |
| `15_career_stats.png` | 生涯（战绩总览，空库状态） |
| `16_players.png` | 球员库（搜索 + 能力榜） |
| `17_analyze_possession.png` | 战术分析 · **修 bug 后**的标注图（攻守按「谁控球谁进攻」判对了） |
| `18_analyze_ui.png` | 战术分析 · **整页界面**（画面 / 分析结果 / 本地大模型的战术建议） |

> 待补：`01_api_test.png`、`02_team_split.png`、`03_judge.png`（三个自测脚本的终端输出）。
>
> ⚠️ `18_analyze_ui.png` 是**修 `**geo` 覆盖 bug 之前**截的，所以缺「未计入（门将 / 裁判）」
> 那一行（画面里「球员总数 9 = 5 + 3 + 1」，那一行本该出现）。
> 重启后端 + 浏览器硬刷新（Ctrl+F5）后重截一张，就凑齐「带未计入行」的正证。
