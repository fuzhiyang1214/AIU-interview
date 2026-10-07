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
- 创建[llm](llm/)，yolo文件夹 分别存放本地部署大模型和yolo跑通所需要的项目文件
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
### （耍起游戏和FPGA学习了 暂时搁置了一下~）
### 插曲：本地模型和 Codex 突然连不上了

- 现象：关掉加速器后，Codex 和 Ollama 反而集体连不上，甚至无法正常下载游戏。必须开着才正常。
- 排查：询问Workbuddy *显示`netstat` 抓到 codex.exe 一直在往 `127.0.0.1:7890` 发 SYN_SENT，而该端口已无进程监听*
- 后续：多次反复追问AI 多次重启程序与电脑 总算搞定了这个问题（以后一定要注意代理的使用）

## 2026-10-03

### 本日使用AI模型及Agent : Workbuddy 5.6.2 （使用内置Deepseek V4.1-flash模型）

### 任务1-1（补充收尾）
- 在[llm/](llm/)中加入[test](llm/test/)文件夹 存放与本地部署大模型的对话与测试相关截图
- **重跑测试** 截图放入[test](llm/test/)文件夹
- 创建[test_report](llm/test/test_report.md)文件（*AI测试报告*）
- 创建[test_README](llm/test/test_README.md)（*AI测试说明文件*）
- 在[llm/](llm/)根目录创建[llm_README](llm/llm_README.md)说明文件（*整个大模型部署、智能体搭建环节的说明文件*）
- 初步搭建[README](README.md)（*项目总体说明文件*）框架
- 测试报告、说明文件编写、复现脚本主力为WorkBuddy 
- 对AI生成的说明文件与报告进行删繁就简 同时修改一下表达


### 任务1-2 本地智能体搭建
#### 准备部分
- 采用Dify本地部署方案（AI最推荐方案）
- 第一步 通过终端命令安装Docker Desktop
- (*此后摸鱼 遂24点已过*)

## 2026-10-04
### 本日使用AI模型及Agent : Workbuddy 5.6.2 （使用内置Deepseek V4.1-flash模型）


### 任务1-2 本地智能体搭建（续）
#### 准备部分（续）
- 第二步 通过终端命令拉取并下载Dify
- 第三步 创建Dify管理员账号，配置供应商为Ollama，添加qwen2.5:7b模型，自此准备工作告一段落
- 第四步 在[llm](llm/)根目录下创建[agent](llm/agent/)文件夹，存放代码、程序、测试截图等内容
#### 实践部分
- 考虑到实践难度 选择Cli和Web应用形式
- 在完成最麻烦的下载与配置之后 实践部分实际上更简单 交给Agent搓一下代码就行
- 成品即为 [cli.py](llm/agent/cli.py)(Cli)和[index.html](llm/agent/index.html)(web形式)
- 为了隐私 没有直接写出来API密钥（笑）
- 进行Cli跑通测试 在powershell中输入指令调用大模型
- 进行Web网页对话测试
#### 核验检查
- 根据会长大人指示，先进行人工自查，再输入他给的提示词封装程序，编写REAMDE\
以便增加项目可读性
#### 遇到的问题？
##### 准备阶段
- 终端拉取Dify镜像文件时报错，后来查证到原因是
```
WorkBuddy:

先认错：那个端口是假的

54881 是我从我这边的运行环境里读到的变量值，不是你机器上的。我没核实就让你填了——结果 Docker 拿着一个没人监听的端口去连，当然是 connection refused，十几个镜像全军覆没。
```
- 由于AI幻觉，错误地引导我去Docker Desktop的Resource界面配置代理（假端口）
- 重新改回正确端口后，下载仍然报错，这次是DNS污染造成的
- 尝试科学上网，在AI指导下打开Allow LAN，更改Docker配置后 终于拉取成功

##### 实践阶段
- 跑通Cli时 当我输入
```
cd C:\Users\FU\Desktop\ai-interview\llm\agent
$env:DIFY_API_KEY="保密"
"你好，用一句话说明你是谁`n我刚才问了你什么" | python cli.py
```
- 得到回答
```
你好！看起来你输入了一些无法辨识的符号。能告诉我具体的问题或需要帮助的内容吗？我会尽力提供帮助。
```
- 这实际上是因为 *Windows PowerShell 5.1 的 $OutputEncoding 默认是 US-ASCII* 也就是说中文输进去会变成乱码

- 添加如下语句
```
$OutputEncoding = New-Object System.Text.UTF8Encoding   # 送出去的
$env:PYTHONUTF8 = "1"                                    # 收进来的
"你好`n我刚才问了你什么" | python cli.py
```
即可正常回答问题

- 测试Web对话时发生报错`转发失败: 'latin-1' codec can't encode characters in position 11-14: ordinal not in range(256)`
- 原因：一行环境变量我直接输入的是`$env:DIFY_API_KEY = "app-你的密钥" `
一开始是为了保密，但后来测试忘记输入真实的APIkey了。。。

### 任务2-1 yolo的跑通

### 准备阶段

- 参考学长博客`https://blog.csdn.net/linmoqian/article/details/157656782?spm=1001.2014.3001.5501`
- 对照自身设备环境，决定对其中内容做出取舍 将博客喂给Workbuddy，与其共同研究出来一条适应当前设备环境的技术路线
- Workbuddy指出用Miniforge下载对RTX 5070可能存在风险 建议我用venv下载管理 先试一试这条路线
- 下载成功 
- 下载标注软件X-AnyLabeling，这里直接下载CUDA12版本 直接集成GPU加速功能

## 2026-10-05
### 本日使用AI模型及Agent : Workbuddy 5.6.2 （使用内置Deepseek V4.1-flash模型）
### 任务2-1 yolo的跑通（续）
- 沿用博客中技术路线 使用给的10张示例图进行训练
- 先用X-AnyLabeling进行标注
- 标注完毕 运行脚本（此处用Agent辅助运行~）
- 类别映射修改 → 数据集划分 → 开始训练！
- 刚开始训练 一直报错
- 询问AI后发现 是代码中少了一行保护（详见遇到的问题）
- 修改main.py 训练成功!(用的默认参数)
### 遇到的问题？
- 终端运行main.py时出现了报错
```
C:\Users\FU\Desktop\ai-interview\yolo\main.py:19: SyntaxWarning: "\ " is an invalid escape sequence. Such sequences will not work in the future. Did you mean "\\ "? A raw string is also an option.
  O\ = /O
```
- 询问AI后 他说：
```
这个警告跟训练没关系，是学长 main.py 里那段"佛祖保佑"ASCII art 引起的。
```
- 也就是这个大佛。。。
```
# 佛祖保佑，永无BUG
"""
                  _ooOoo_
                 o8888888o
                 88" . "88
                 (| -_- |)
                 O\ = /O
              ____/`---'\____
            .' \\| |// `
           / \\||| : |||// 
          / _||||| -:- |||||- 
          | | \\\ - /// | |
          | \_| ''\---/'' | |
          \ .-\__ `-` ___/-. /
        ___`. .' /--.--\ `. . __
     ."" '< `.___\_<|>_/___.' >'""
    | | : `- \`.;`\ _ /`;.`/ - ` : | |
    \ \ `-. \_ __\ /__ _/ .-` / /
======`-.____`-.___\_____/___.-`____.-'======
                  `=---='
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
           佛祖保佑 永无BUG
"""
```
- 里面的 \ 、\_、\`` 被新版本的Python（我的是3.14） 当成**无效转义序列**。第 19 行正是 O\ = /O`，和报错行号完全对上。
- 不得已 删掉大佛之后就可以正常运行~（佛祖保佑）
- 训练时又出现问题！**一直报错**，连续折腾了好几轮
- 终端报错：
```
An attempt has been made to start a new process before the
current process has finished its bootstrapping phase.
...
if name == 'main':
freeze_support()
```
- 真实原因？
```
Workbuddy

找到真凶了：不是网络、不是 GPU、不是环境 —— 是 main.py 缺一行保护
机理（一句话）
Windows 下 dataloader 用 spawn 起子进程 → 子进程会重新 import __main__ → 而 main.py 顶层没有 if __name__ == '__main__': 保护，于是子进程又跑了一遍 YOLO().train() → 无限套娃 → worker 崩溃。

需要加一行
if __name__ == '__main__':
    main()
```
- 再次终端运行 终于成功

## 2026-10-07
### 本日使用AI模型及Agent : Workbuddy 5.7.6 （使用内置Deepseek V4.1-flash模型）
### 任务2-2 yolo实时推理 + 任务2-3 yolo接入web
- 这两个任务可以一起进行，把训练好的模型接到摄像头，做成 Web 应用
- 让AI参考题目要求浏览开源库，最终选 Flask + MJPEG
- py脚本和html文件由AI编写，我负责拍摄＋寻找网上图片进行标注
- 使用鞋子为素材进行训练 图片为自拍＋网上寻找素材 涵盖多个角度 单只一双等多种情况 总共60张图片
- 用X-AnyLabeling进行图片的标注
- 标注完成 用脚本进行训练
- 先运行脚本启动摄像头推理 再打开网站 进行实时推理测试
### 遇到的问题？
- 网站成功使用 但是识别不出来鞋子 这个问题很严重
- 再次尝试 拿真实鞋子出来识别不出来 但是手机里面的可以识别出来
- 调低了台灯亮度 减少了过曝光之后 可以识别出来真实的鞋子 但是泛化能力比较差 需要摆好角度 距离 
- 经过AI分析 原因是**训练数据和推理时的实际画面差异太大*
- 我的训练图片主要是手机特写拍摄，背景干净，主体突出，画质清晰
- 台灯调暗之后就能识别，说明光照的影响比较大
- 泛化能力差的原因：数据量太少（只有 60 张），而且拍摄条件太单一（基本只有一个角度和一种光线）
- 后续改进方向：
  - 用**电脑摄像头**在实际推理的位置和光线下补拍 40~60 张，混进原来的数据重新训练
  - 或者调整数据增强参数，让模型适应不同的光照和角度