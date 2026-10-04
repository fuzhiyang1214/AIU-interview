#!/usr/bin/env bash
# ============================================================
# 本地大模型性能测试 · 一键复现
#
# 用法：  bash llm/test/bench.sh
# 前提：  1) Ollama 服务已在 http://127.0.0.1:11434 运行
#         2) 已下载模型 qwen2.5:7b
# 输出：  raw-cold.json / raw-hot.json（覆盖更新）+ 指标汇总
# ============================================================
set -u

# ollama 可执行文件：优先取 PATH，找不到再试常见安装位置；均可用 OLLAMA_BIN= 覆盖
find_ollama() {
    local found
    found="$(command -v ollama 2>/dev/null | tr -d '\r')"
    [ -n "$found" ] && { echo "$found"; return; }
    for c in "$HOME/AppData/Local/Programs/Ollama/ollama.exe" \
             "/c/Program Files/Ollama/ollama.exe" \
             "/usr/local/bin/ollama" "/usr/bin/ollama"; do
        [ -x "$c" ] && { echo "$c"; return; }
    done
}

OLLAMA_BIN="${OLLAMA_BIN:-$(find_ollama)}"
if [ -z "$OLLAMA_BIN" ]; then
    echo "错误：找不到 ollama。请把它加入 PATH，或指定 OLLAMA_BIN=/path/to/ollama" >&2
    exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python}"
MODEL="qwen2.5:7b"
PROMPT="请用200字介绍人工智能的发展历史、当前现状和未来趋势。"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR" || exit 1

echo "===== 1. 环境 ====="
"$OLLAMA_BIN" --version
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
"$OLLAMA_BIN" list

echo
echo "===== 2. 冷启动准备（卸载模型并等待显存释放） ====="
"$OLLAMA_BIN" stop "$MODEL" >/dev/null 2>&1
sleep 10
echo -n "当前显存占用: "
nvidia-smi --query-gpu=memory.used --format=csv,noheader

REQ=$(printf '{"model":"%s","prompt":"%s","stream":false,"options":{"temperature":0,"num_predict":512}}' "$MODEL" "$PROMPT")

echo
echo "===== 3. 冷启动请求 ====="
curl --noproxy '*' -s -m 600 -X POST http://127.0.0.1:11434/api/generate -d "$REQ" -o raw-cold.json
echo "已写入 raw-cold.json"

echo "===== 4. 热启动请求（紧接上一次） ====="
curl --noproxy '*' -s -m 600 -X POST http://127.0.0.1:11434/api/generate -d "$REQ" -o raw-hot.json
echo "已写入 raw-hot.json"

echo
echo "===== 5. 资源占用 ====="
"$OLLAMA_BIN" ps
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader

echo
echo "===== 6. 指标汇总 ====="
"$PYTHON_BIN" - <<'PY'
import json, os

for f in ("raw-cold", "raw-hot"):
    p = f + ".json"
    if not os.path.exists(p):
        print("[%s] 文件缺失" % f)
        continue
    d = json.load(open(p, encoding="utf-8"))
    sec = lambda k: d.get(k, 0) / 1e9
    ld, pe, ed, td = sec("load_duration"), sec("prompt_eval_duration"), sec("eval_duration"), sec("total_duration")
    pc, ec = d.get("prompt_eval_count", 0), d.get("eval_count", 0)
    print("[%s]" % f)
    print("  首字延迟 TTFT = %.2f s   (加载 %.3f s + 提示 %.3f s)" % (ld + pe, ld, pe))
    print("  提示处理速度  = %.1f tok/s" % (pc / pe if pe else 0))
    print("  生成速度      = %.1f tok/s   (%d tokens / %.3f s)" % (ec / ed if ed else 0, ec, ed))
    print("  总耗时        = %.2f s" % td)
PY

echo
echo "完成。"
