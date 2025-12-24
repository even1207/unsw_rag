"""
初始化 RAG 数据库

功能:
1. 检查 PostgreSQL 连接
2. 安装 pgvector 扩展
3. 创建所有表
4. 创建索引

使用方法:
    python3 scripts/init_database.py
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from database.rag_schema import create_tables, create_indexes, drop_tables
from config.settings import settings


def check_postgres_connection(engine):
    """检查 PostgreSQL 连接"""
    print("\n1. 检查 PostgreSQL 连接...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"   ✓ PostgreSQL 连接成功")
            print(f"   版本: {version[:50]}...")
            return True
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        return False


def install_pgvector(engine):
    """安装 pgvector 扩展"""
    print("\n2. 安装 pgvector 扩展...")
    try:
        with engine.connect() as conn:
            # 检查是否已安装
            result = conn.execute(text(
                "SELECT * FROM pg_extension WHERE extname = 'vector'"
            ))
            if result.fetchone():
                print(f"   ✓ pgvector 已安装")
            else:
                # 安装扩展
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
                print(f"   ✓ pgvector 安装成功")
            return True
    except Exception as e:
        print(f"   ⚠️  pgvector 安装失败: {e}")
        print(f"   提示: 请先安装 pgvector:")
        print(f"     brew install pgvector")
        print(f"     或参考: https://github.com/pgvector/pgvector")
        return False


def init_tables(engine, drop_existing=False):
    """创建数据库表"""
    print(f"\n3. 创建数据库表...")

    if drop_existing:
        print(f"   ⚠️  删除现有表...")
        drop_tables(engine)
        print(f"   ✓ 现有表已删除")

    create_tables(engine)
    print(f"   ✓ 表创建成功")

    # 列出创建的表
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
        """))
        tables = [row[0] for row in result.fetchall()]
        print(f"   创建的表: {', '.join(tables)}")


def init_indexes(engine):
    """创建索引"""
    print(f"\n4. 创建索引...")
    try:
        create_indexes(engine)
        print(f"   ✓ 索引创建成功")
    except Exception as e:
        print(f"   ⚠️  索引创建失败: {e}")
        print(f"   提示: 确保 pgvector 已正确安装")


def print_stats(engine):
    """打印数据库统计"""
    print(f"\n5. 数据库统计:")
    with engine.connect() as conn:
        # Staff 数量
        result = conn.execute(text("SELECT COUNT(*) FROM staff"))
        staff_count = result.fetchone()[0]
        print(f"   Staff: {staff_count}")

        # Publications 数量
        result = conn.execute(text("SELECT COUNT(*) FROM publications"))
        pub_count = result.fetchone()[0]
        print(f"   Publications: {pub_count}")

        # Chunks 数量
        result = conn.execute(text("SELECT COUNT(*) FROM chunks"))
        chunk_count = result.fetchone()[0]
        print(f"   Chunks: {chunk_count}")

        # Embeddings 数量
        result = conn.execute(text("SELECT COUNT(*) FROM embeddings"))
        emb_count = result.fetchone()[0]
        print(f"   Embeddings: {emb_count}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='初始化 RAG 数据库')
    parser.add_argument('--drop', action='store_true', help='删除现有表并重新创建')
    parser.add_argument('--skip-pgvector', action='store_true', help='跳过 pgvector 安装（如果已安装）')
    args = parser.parse_args()

    print("="*80)
    print("RAG 数据库初始化")
    print("="*80)
    print(f"\n数据库连接: {settings.postgres_dsn}")

    # 创建引擎
    engine = create_engine(settings.postgres_dsn, echo=False)

    # 1. 检查连接
    if not check_postgres_connection(engine):
        return

    # 2. 安装 pgvector
    pgvector_ok = True
    if not args.skip_pgvector:
        pgvector_ok = install_pgvector(engine)
    else:
        print("\n2. 跳过 pgvector 安装（使用 --skip-pgvector）")

    # 3. 创建表
    drop_existing = args.drop
    if drop_existing:
        print("\n⚠️  将删除现有表（使用了 --drop 参数）")

    init_tables(engine, drop_existing)

    # 4. 创建索引
    if pgvector_ok:
        init_indexes(engine)

    # 5. 打印统计
    print_stats(engine)

    print("\n" + "="*80)
    print("✅ 数据库初始化完成!")
    print("="*80)
    print("\n下一步:")
    print("1. 运行 parse_publications_multisource_v2.py 生成 chunks")
    print("2. 运行 scripts/import_chunks_to_db.py 导入数据")
    print("3. 运行 scripts/generate_embeddings.py 生成向量嵌入")


if __name__ == "__main__":
    main()
