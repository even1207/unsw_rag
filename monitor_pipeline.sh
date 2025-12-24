#!/bin/bash
# Pipeline 监控脚本

echo "==============================================="
echo "UNSW AI RAG Pipeline 监控"
echo "==============================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查 Step 2 进程状态
echo -e "${BLUE}Step 2: 解析 Publications${NC}"
echo "-----------------------------------------------"
if pgrep -f "step2_parse_publications.py" > /dev/null; then
    echo -e "状态: ${GREEN}运行中 ✓${NC}"

    # 显示进度
    echo ""
    echo "最新进度:"
    tail -30 /Users/z5241339/Documents/unsw_ai_rag/data/cache/parsing.log 2>/dev/null | \
        grep -E "^\[" | tail -5 | \
        while read line; do
            echo "  $line"
        done

    # 统计信息
    echo ""
    echo "统计信息:"
    if [ -f /Users/z5241339/Documents/unsw_ai_rag/data/cache/parsing_progress.json ]; then
        python3 << 'PYEOF'
import json
from pathlib import Path

progress_file = Path('/Users/z5241339/Documents/unsw_ai_rag/data/cache/parsing_progress.json')
if progress_file.exists():
    with open(progress_file, 'r') as f:
        progress = json.load(f)

    processed = len(progress.get('processed_staff_urls', []))
    cache_size = len(progress.get('publication_cache', {}))

    print(f'  已处理 staff: {processed}/649 ({processed/649*100:.1f}%)')
    print(f'  缓存的 publications: {cache_size}')
PYEOF
    fi
else
    echo -e "状态: ${RED}已停止${NC}"
    echo ""
    echo "最后输出:"
    tail -10 /Users/z5241339/Documents/unsw_ai_rag/data/cache/parsing.log 2>/dev/null | tail -5
fi

echo ""
echo "-----------------------------------------------"

# 检查输出文件
echo ""
echo -e "${BLUE}输出文件状态:${NC}"
echo "-----------------------------------------------"

if [ -f /Users/z5241339/Documents/unsw_ai_rag/data/processed/rag_chunks.json ]; then
    echo -e "rag_chunks.json: ${GREEN}存在${NC}"
    python3 << 'PYEOF'
import json
with open('/Users/z5241339/Documents/unsw_ai_rag/data/processed/rag_chunks.json', 'r') as f:
    chunks = json.load(f)
print(f'  总 chunks: {len(chunks)}')
PYEOF
else
    echo -e "rag_chunks.json: ${YELLOW}不存在${NC}"
fi

echo ""
echo "-----------------------------------------------"

# 快捷命令提示
echo ""
echo -e "${BLUE}快捷命令:${NC}"
echo "  查看完整日志: tail -f /Users/z5241339/Documents/unsw_ai_rag/data/cache/parsing.log"
echo "  查看进度文件: cat /Users/z5241339/Documents/unsw_ai_rag/data/cache/parsing_progress.json | python3 -m json.tool"
echo "  查看统计: cat /Users/z5241339/Documents/unsw_ai_rag/data/cache/parsing_statistics.json | python3 -m json.tool"
echo ""
echo "==============================================="
