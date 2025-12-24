#!/bin/bash
# 运行改进版的 Publication Fetcher

echo "=================================="
echo "Publication Fetcher V2 启动器"
echo "=================================="
echo ""

# 检查 Python 版本
python_version=$(python3 --version 2>&1)
echo "Python 版本: $python_version"
echo ""

# 选项菜单
echo "请选择操作:"
echo "1. 测试 PubMed 修复（推荐首次运行）"
echo "2. 清理旧的错误数据"
echo "3. 运行新版本获取脚本（多线程）"
echo "4. 查看进度和统计"
echo "5. 查看日志（实时）"
echo ""
read -p "输入选项 [1-5]: " choice

case $choice in
    1)
        echo ""
        echo "运行 PubMed 修复测试..."
        echo "=================================="
        python3 test_pubmed_fix.py
        ;;
    2)
        echo ""
        echo "清理旧的错误 PubMed 数据..."
        echo "=================================="
        read -p "确认要清理吗? (y/n): " confirm
        if [ "$confirm" = "y" ]; then
            python3 clean_bad_pubmed_data.py
        else
            echo "操作已取消"
        fi
        ;;
    3)
        echo ""
        echo "运行新版本获取脚本..."
        echo "=================================="
        echo "提示: 按 Ctrl+C 可以安全中断"
        echo ""
        python3 parse_publications_multisource_v2.py
        ;;
    4)
        echo ""
        echo "进度和统计信息"
        echo "=================================="

        if [ -f "parsing_progress_multisource_v2.json" ]; then
            echo ""
            echo "📊 进度文件:"
            processed=$(cat parsing_progress_multisource_v2.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data['processed_staff_emails']))")
            cache_size=$(cat parsing_progress_multisource_v2.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data['publication_cache']))")
            echo "  已处理 staff: $processed"
            echo "  缓存的出版物: $cache_size"
        else
            echo "  ⚠️  进度文件不存在"
        fi

        if [ -f "parsing_statistics_multisource_v2.json" ]; then
            echo ""
            echo "📈 统计信息:"
            cat parsing_statistics_multisource_v2.json | python3 -m json.tool | head -30
        else
            echo "  ⚠️  统计文件不存在"
        fi
        ;;
    5)
        echo ""
        echo "查看实时日志 (Ctrl+C 退出)..."
        echo "=================================="
        if [ -f "parsing_v2.log" ]; then
            tail -f parsing_v2.log
        else
            echo "  ⚠️  日志文件不存在"
        fi
        ;;
    *)
        echo "无效选项"
        exit 1
        ;;
esac
