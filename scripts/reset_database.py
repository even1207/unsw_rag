"""
重置数据库：删除所有表并重新创建

警告: 这会删除所有现有数据！
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine
from database.rag_schema import Base, drop_tables, create_tables
from config.settings import settings

def main():
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == '--force':
        print("⚠️  强制模式: 跳过确认")
    else:
        print("⚠️  警告: 这将删除所有现有数据！")
        response = input("确认要继续吗？(输入 'YES' 继续): ")

        if response != 'YES':
            print("取消操作")
            return

    engine = create_engine(settings.postgres_dsn, echo=True)

    print("\n删除所有表...")
    drop_tables(engine)

    print("\n创建新表...")
    create_tables(engine)

    print("\n✓ 数据库重置完成!")

if __name__ == "__main__":
    main()
