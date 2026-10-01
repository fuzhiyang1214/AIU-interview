# 项目日志

**本项目为AIU第二次面试实战题目 本人第一次尝试工程类项目 不妥之处请海涵！**

## 2026-10-01
### 本日使用AI模型及Agent : Workbuddy 5.6.2 （使用内置Deepseek V4.1-flash模型）

### 任务1-1 本地部署大模型
#### 准备部分
- 使用Workbuddy将面试题目要求喂给AI 获取一些“微小”的建议 并创建项目专门服务此次面试任务
- 初步学习如何使用Github创建Reposity
- 学习如何使用git
- 学习如何使用官方提供的Github Desktop进行项目管理
- 创建llm，yolo文件夹 分别存放本地部署大模型和yolo跑通所需要的项目文件
- 创建说明文件与日志
#### 基本信息与安装
- 电脑基础配置：RTX 5070 Laptop 8GB ＋ 24GB DDR5 RAM
- 模型版本 qwen2.5:7b（7.6B / Q4_K_M / 4.7GB）
- 官网下载Ollama 在官方网站的Models社区下载qwen2.5:7b 模型

#### 遇到的问题？
- 用终端下载模型时发生报错：ollama pull 报 `lookup registry.ollama.ai: no such host`
- 经过（AI大人）仔细排查：*发现本机 DNS 间歇性解析超时 顺带发现网络环境复杂：Radmin VPN 网卡 + 2 张 TAP 网卡 + Clash 代理同时存在，
   多套工具一起改路由表，放大了 DNS 抖动。*
- 最终解法：*写了个自动重试循环（ollama pull 支持断点续传），第 5 次成功。*（AI真是太好用了你们知道吗）

#### 性能测试环节
- 测试Prompt：`ollama run qwen2.5:7b "请用200字介绍人工智能的发展历史、当前现状和未来趋势" --verbose`
- 测试结果
- 冷启动 
```
total duration:       8.3544042s
load duration:        6.3478016s
prompt eval count:    37 token(s)
prompt eval duration: 210.822ms
prompt eval rate:     175.50 tokens/s
eval count:           124 token(s)
eval duration:        1.789872s
eval rate:            69.28 tokens/s
```
- 热启动
```
total duration:       2.7628054s
load duration:        9.1798ms
prompt eval count:    45 token(s)
prompt eval cached:   32 token(s)
prompt eval duration: 276.661ms
prompt eval rate:     46.99 tokens/s
eval count:           149 token(s)
eval duration:        2.45468s
eval rate:            60.70 tokens/s
```

## 2026-10-02

###