#!/bin/bash
# 实时监控 Step 2 进度

echo "监控 Step 2 进度 (按 Ctrl+C 退出)"
echo "========================================"
echo ""

while true; do
    clear
    echo "UNSW AI RAG Pipeline - Step 2 进度监控"
    echo "========================================"
    echo ""

    # 检查进程
    if pgrep -f "step2_parse_publications.py" > /dev/null; then
        echo "✓ Step 2 正在运行"
    else
        echo "✗ Step 2 已停止"
        echo ""
        echo "查看最终统计:"
        echo "  cat /Users/z5241339/Documents/unsw_ai_rag/data/cache/parsing_statistics.json | python3 -m json.tool"
        break
    fi

    echo ""
    echo "最新进度 (最后10行):"
    echo "----------------------------------------"
    tail -30 /Users/z5241339/Documents/unsw_ai_rag/data/cache/parsing.log 2>/dev/null | \
        grep -E "^\[|chunks created|Progress saved|STATISTICS" | tail -10

    echo ""
    echo "----------------------------------------"
    date
    echo ""
    echo "刷新中... (每5秒更新一次)"

    sleep 5
done
