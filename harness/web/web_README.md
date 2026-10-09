# web/ — Web 前端

`cli.py` 的兄弟：**同一套事件、不同的前端**。core 完全不知道谁在监听。

## 文件

| 文件 | 职责 |
|---|---|
| `server.py` | HTTP 服务 + SSE 桥接（订阅事件 → 推给浏览器；接收提问 → 交给 loop） |
| `static/index.html` | 页面，只订阅 SSE 并渲染 |

**零新增依赖** —— 只用标准库 `http.server` / `json` / `queue` / `threading`，不需要 Flask。

## 启动

```bash
python harness/main.py --web            # 默认 8000 端口
python harness/main.py --web --port 8080
```

然后浏览器打开 `http://127.0.0.1:8000`。

## 为什么用 SSE 而不是 WebSocket

| 方案 | 评价 |
|---|---|
| **SSE**（本实现） | 标准库就能做，**单向推送正合适**（后端推事件 → 前端展示），零依赖 |
| WebSocket | 需要第三方库，双向通信这里用不到 |

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 页面 |
| GET | `/events` | SSE 事件流（长连接 + 心跳） |
| POST | `/ask` | 提交问题，body `{"text": "..."}` |
| GET | `/stats` | 当前连接的浏览器数 |

## 事件映射

`core` 里 `bus.emit(事件名, ...)` → SSE 帧 `event: 事件名\ndata: {...}`：

| 事件 | 前端怎么渲染 |
|---|---|
| `turn_start` | 「提问」行 |
| `model_response` | 「判断」行（仅当有 tool_calls 时） |
| `tool_start` | 「调用」行，等宽字体 |
| `tool_end` | 「返回」行，超 300 字截断 |
| `turn_end` | 绿色答案块 + 轮次统计 |
| `error` | 红色错误行 |

## 加第三个前端

只要再写一个订阅同样事件的类即可（比如将来的桌面通知、飞书机器人），
`core/` 依然一个字都不改 —— 这就是规范第 4 条"前后端高度解耦"的实证。
