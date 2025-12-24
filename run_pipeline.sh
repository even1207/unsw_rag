#!/bin/bash

# UNSW AI RAG Pipeline - 完整数据处理流程
#
# 功能:
# 1. 爬取 UNSW Engineering staff 数据
# 2. 解析 publications 并获取 abstract
# 3. 导入到数据库
#
# 使用方法:
#   chmod +x run_pipeline.sh
#   ./run_pipeline.sh [step_number]
#
# 参数:
#   step_number (可选): 1, 2, 或 3 (运行特定步骤)
#   如果不指定，将运行完整流程

set -e  # 遇到错误立即退出

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "================================================================================"
echo "UNSW AI RAG Pipeline"
echo "================================================================================"
echo ""

# 检查 Python 版本
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✓ Python 版本: $PYTHON_VERSION"
echo ""

# 检查必要的包
echo "检查依赖..."
python3 -c "import requests, bs4, sqlalchemy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ 错误: 缺少必要的 Python 包"
    echo "请运行: pip3 install -r requirements.txt"
    exit 1
fi
echo "✓ 依赖检查通过"
echo ""

# 函数: 运行步骤 1
run_step1() {
    echo "================================================================================"
    echo "Step 1: 爬取 UNSW Engineering Staff 数据"
    echo "================================================================================"
    echo ""

    python3 pipeline/step1_fetch_staff.py

    if [ $? -eq 0 ]; then
        echo ""
        echo "✓ Step 1 完成"
        echo ""
    else
        echo ""
        echo "❌ Step 1 失败"
        exit 1
    fi
}

# 函数: 运行步骤 2
run_step2() {
    echo "================================================================================"
    echo "Step 2: 解析 Publications 并获取 Abstract"
    echo "================================================================================"
    echo ""

    # 检查输入文件
    if [ ! -f "data/processed/staff_with_profiles.json" ]; then
        echo "❌ 错误: 未找到 data/processed/staff_with_profiles.json"
        echo "请先运行 Step 1"
        exit 1
    fi

    python3 pipeline/step2_parse_publications.py

    if [ $? -eq 0 ]; then
        echo ""
        echo "✓ Step 2 完成"
        echo ""
    else
        echo ""
        echo "❌ Step 2 失败"
        exit 1
    fi
}

# 函数: 运行步骤 3
run_step3() {
    echo "================================================================================"
    echo "Step 3: 导入 Chunks 到数据库"
    echo "================================================================================"
    echo ""

    # 检查输入文件
    if [ ! -f "data/processed/rag_chunks.json" ]; then
        echo "❌ 错误: 未找到 data/processed/rag_chunks.json"
        echo "请先运行 Step 2"
        exit 1
    fi

    python3 pipeline/step3_import_to_database.py

    if [ $? -eq 0 ]; then
        echo ""
        echo "✓ Step 3 完成"
        echo ""
    else
        echo ""
        echo "❌ Step 3 失败"
        exit 1
    fi
}

# 主逻辑
STEP=$1

if [ -z "$STEP" ]; then
    # 运行完整流程
    echo "运行完整流程 (Step 1 → 2 → 3)"
    echo ""
    run_step1
    run_step2
    run_step3

    echo "================================================================================"
    echo "✓ 完整流程执行完成!"
    echo "================================================================================"
    echo ""
    echo "数据文件位置:"
    echo "  - Staff 数据: data/processed/staff_with_profiles.json"
    echo "  - RAG Chunks: data/processed/rag_chunks.json"
    echo "  - 进度缓存: data/cache/"
    echo ""

elif [ "$STEP" = "1" ]; then
    run_step1

elif [ "$STEP" = "2" ]; then
    run_step2

elif [ "$STEP" = "3" ]; then
    run_step3

else
    echo "❌ 错误: 无效的步骤编号: $STEP"
    echo ""
    echo "使用方法:"
    echo "  ./run_pipeline.sh       # 运行完整流程"
    echo "  ./run_pipeline.sh 1     # 只运行 Step 1"
    echo "  ./run_pipeline.sh 2     # 只运行 Step 2"
    echo "  ./run_pipeline.sh 3     # 只运行 Step 3"
    exit 1
fi
