#!/bin/bash

# 文件整理脚本 - 将旧文件移动到对应位置
#
# 功能:
# 1. 将现有数据文件移动到 data/ 文件夹
# 2. 将旧的 Python 脚本归档到 archive/
# 3. 保持项目结构清晰

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "================================================================================"
echo "整理项目文件"
echo "================================================================================"
echo ""

# 创建目录结构
echo "1. 创建目录结构..."
mkdir -p data/raw
mkdir -p data/processed
mkdir -p data/cache
mkdir -p archive/old_scripts
mkdir -p archive/old_data
echo "✓ 目录创建完成"
echo ""

# 移动数据文件
echo "2. 移动数据文件..."

# 移动最新的完整数据到 processed
if [ -f "engineering_staff_with_profiles_cleaned.json" ]; then
    echo "  移动: engineering_staff_with_profiles_cleaned.json → data/processed/staff_with_profiles.json"
    cp engineering_staff_with_profiles_cleaned.json data/processed/staff_with_profiles.json
fi

# 移动最新的 RAG chunks
if [ -f "rag_chunks_multisource_v2.json" ]; then
    echo "  移动: rag_chunks_multisource_v2.json → data/processed/rag_chunks.json"
    cp rag_chunks_multisource_v2.json data/processed/rag_chunks.json
fi

# 移动进度文件到 cache
if [ -f "parsing_progress_multisource_v2.json" ]; then
    echo "  移动: parsing_progress_multisource_v2.json → data/cache/parsing_progress.json"
    cp parsing_progress_multisource_v2.json data/cache/parsing_progress.json
fi

if [ -f "parsing_statistics_multisource_v2.json" ]; then
    echo "  移动: parsing_statistics_multisource_v2.json → data/cache/parsing_statistics.json"
    cp parsing_statistics_multisource_v2.json data/cache/parsing_statistics.json
fi

echo "✓ 数据文件移动完成"
echo ""

# 归档旧的数据文件
echo "3. 归档旧数据文件..."
for file in engineering_staff_*.json parsing_*.json rag_chunks_*.json; do
    if [ -f "$file" ]; then
        echo "  归档: $file → archive/old_data/"
        mv "$file" archive/old_data/
    fi
done
echo "✓ 旧数据文件归档完成"
echo ""

# 归档旧的 Python 脚本
echo "4. 归档旧 Python 脚本..."
OLD_SCRIPTS=(
    "scrape_staff_profiles.py"
    "scrape_all_profiles.py"
    "parse_publications.py"
    "parse_publications_full.py"
    "parse_publications_multisource.py"
    "parse_publications_multisource_v2.py"
    "parse_publications_test.py"
    "improved_scraper.py"
    "analyze_results.py"
    "analyze_links.py"
    "analyze_page_structure.py"
    "analyze_data_quality.py"
    "check_progress.py"
    "clean_bad_pubmed_data.py"
    "clean_links.py"
    "verify_data_accuracy.py"
    "verify_publications.py"
    "test_*.py"
)

for script in "${OLD_SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        echo "  归档: $script → archive/old_scripts/"
        mv "$script" archive/old_scripts/
    fi
done
echo "✓ 旧脚本归档完成"
echo ""

# 归档旧的 shell 脚本
echo "5. 归档旧 shell 脚本..."
if [ -f "run_fetcher_v2.sh" ]; then
    mv run_fetcher_v2.sh archive/old_scripts/
fi
if [ -f "monitor_progress.sh" ]; then
    mv monitor_progress.sh archive/old_scripts/
fi
echo "✓ 旧 shell 脚本归档完成"
echo ""

# 归档旧的日志文件
echo "6. 归档日志文件..."
for log in *.log; do
    if [ -f "$log" ]; then
        echo "  归档: $log → archive/old_data/"
        mv "$log" archive/old_data/
    fi
done
echo "✓ 日志文件归档完成"
echo ""

# 归档旧的文档
echo "7. 归档旧文档..."
OLD_DOCS=(
    "DATABASE_CONNECTION_GUIDE.md"
    "DATABASE_SETUP.md"
    "PROJECT_STATUS.md"
    "QUICKSTART_DATABASE.md"
    "README_DATABASE.md"
    "README_PUBMED_FIX.md"
    "SUMMARY_修复完成.md"
    "SUMMARY_完成状态.md"
)

mkdir -p archive/old_docs
for doc in "${OLD_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        echo "  归档: $doc → archive/old_docs/"
        mv "$doc" archive/old_docs/
    fi
done
echo "✓ 旧文档归档完成"
echo ""

# 归档临时 HTML 文件
if [ -f "page_source.html" ]; then
    mv page_source.html archive/old_data/
fi

# 显示当前项目结构
echo "================================================================================"
echo "✓ 文件整理完成!"
echo "================================================================================"
echo ""
echo "当前项目结构:"
echo ""
echo "unsw_ai_rag/"
echo "├── pipeline/              # 核心处理流程"
echo "│   ├── step1_fetch_staff.py"
echo "│   ├── step2_parse_publications.py"
echo "│   └── step3_import_to_database.py"
echo "├── database/              # 数据库模块"
echo "├── config/                # 配置文件"
echo "├── data/"
echo "│   ├── processed/         # 处理后的数据"
echo "│   └── cache/             # 缓存和进度文件"
echo "├── archive/               # 归档的旧文件"
echo "│   ├── old_scripts/"
echo "│   ├── old_data/"
echo "│   └── old_docs/"
echo "├── run_pipeline.sh        # 主执行脚本"
echo "└── PIPELINE_README.md     # 使用文档"
echo ""
echo "下一步:"
echo "  1. 查看 PIPELINE_README.md 了解使用方法"
echo "  2. 运行 ./run_pipeline.sh 测试完整流程"
echo ""
