# 数据库导入指南

将 V2 生成的 JSON 数据导入到 PostgreSQL 数据库

## 📊 数据库结构

### 表设计

```
staff (教职工)
├── email (PK)
├── full_name
├── role, school, faculty
├── biography, research_text
└── ...

publications (论文)
├── id (PK) - DOI 或 hash
├── title, doi
├── publication_year, pub_type
├── abstract, abstract_source
├── authors (JSON)
├── has_doi (Boolean)
└── staff_email (FK → staff)

chunks (RAG 文本块)
├── chunk_id (PK)
├── chunk_type (person_basic, publication_title, etc.)
├── content (文本内容)
├── metadata (JSON)
├── staff_email (FK → staff)
└── publication_id (FK → publications)

embeddings (向量嵌入)
├── chunk_id (PK, FK → chunks)
├── vector (pgvector, 1536维)
└── model (embedding 模型名称)
```

## 🚀 快速开始

### 前置要求

1. **PostgreSQL** (推荐 14+)
   ```bash
   # macOS
   brew install postgresql@14
   brew services start postgresql@14
   ```

2. **pgvector** (向量扩展)
   ```bash
   brew install pgvector
   ```

3. **Python 依赖**
   ```bash
   pip install sqlalchemy psycopg2-binary pgvector
   ```

### 步骤 1: 创建数据库

```bash
# 创建数据库
createdb unsw_rag

# 或使用 psql
psql postgres
CREATE DATABASE unsw_rag;
\q
```

### 步骤 2: 配置连接

检查 [config/settings.py](config/settings.py):

```python
postgres_dsn: str = "postgresql://z5241339@localhost:5432/unsw_rag"
```

根据你的环境修改：
- `z5241339` → 你的用户名
- `localhost:5432` → 数据库地址
- `unsw_rag` → 数据库名

### 步骤 3: 初始化数据库

```bash
python3 scripts/init_database.py
```

这会：
- ✅ 检查 PostgreSQL 连接
- ✅ 安装 pgvector 扩展
- ✅ 创建所有表
- ✅ 创建索引

### 步骤 4: 导入 Chunks

**确保 V2 已完成运行**，生成了 `rag_chunks_multisource_v2.json`:

```bash
# 检查文件是否存在
ls -lh rag_chunks_multisource_v2.json

# 导入数据
python3 scripts/import_chunks_to_db.py
```

导入过程：
- 读取 JSON 文件
- 提取 staff, publications, chunks 数据
- 批量导入到数据库
- 自动去重和更新

**预计时间:** 根据数据量，约 1-5 分钟

## 📈 查看数据

### 使用 psql

```bash
psql unsw_rag

-- 查看表
\dt

-- 统计数据
SELECT COUNT(*) FROM staff;
SELECT COUNT(*) FROM publications;
SELECT COUNT(*) FROM chunks;
SELECT COUNT(*) FROM embeddings;

-- 查看 staff
SELECT email, full_name, school FROM staff LIMIT 5;

-- 查看 publications
SELECT id, title, publication_year, has_doi
FROM publications
LIMIT 5;

-- 查看 chunks 分布
SELECT chunk_type, COUNT(*)
FROM chunks
GROUP BY chunk_type;

-- 查看无 DOI 的论文
SELECT COUNT(*) FROM publications WHERE has_doi = FALSE;
```

### 使用 Python

```python
from sqlalchemy import create_engine
from database.rag_schema import Staff, Publication, Chunk

engine = create_engine("postgresql://z5241339@localhost:5432/unsw_rag")

from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)
session = Session()

# 查询示例
staff = session.query(Staff).filter_by(email="someone@unsw.edu.au").first()
print(staff.full_name, staff.school)

# 查询论文
pubs = session.query(Publication).filter_by(staff_email=staff.email).all()
for pub in pubs:
    print(pub.title, pub.has_doi)

# 查询 chunks
chunks = session.query(Chunk).filter_by(
    staff_email=staff.email,
    chunk_type='publication_abstract'
).all()
```

## 🔍 数据质量检查

### 检查脚本

```bash
python3 << 'EOF'
from sqlalchemy import create_engine, text

engine = create_engine("postgresql://z5241339@localhost:5432/unsw_rag")

with engine.connect() as conn:
    # 1. 总体统计
    print("=== 总体统计 ===")
    result = conn.execute(text("SELECT COUNT(*) FROM staff"))
    print(f"Staff: {result.fetchone()[0]}")

    result = conn.execute(text("SELECT COUNT(*) FROM publications"))
    print(f"Publications: {result.fetchone()[0]}")

    result = conn.execute(text("SELECT COUNT(*) FROM chunks"))
    print(f"Chunks: {result.fetchone()[0]}")

    # 2. 有/无 DOI 分布
    print("\n=== 论文 DOI 分布 ===")
    result = conn.execute(text("""
        SELECT has_doi, COUNT(*)
        FROM publications
        GROUP BY has_doi
    """))
    for row in result:
        print(f"{'有 DOI' if row[0] else '无 DOI'}: {row[1]}")

    # 3. Chunk 类型分布
    print("\n=== Chunk 类型分布 ===")
    result = conn.execute(text("""
        SELECT chunk_type, COUNT(*)
        FROM chunks
        GROUP BY chunk_type
        ORDER BY COUNT(*) DESC
    """))
    for row in result:
        print(f"{row[0]}: {row[1]}")

    # 4. Abstract 来源分布
    print("\n=== Abstract 来源 ===")
    result = conn.execute(text("""
        SELECT abstract_source, COUNT(*)
        FROM publications
        WHERE abstract IS NOT NULL
        GROUP BY abstract_source
        ORDER BY COUNT(*) DESC
    """))
    for row in result:
        print(f"{row[0]}: {row[1]}")
EOF
```

## 🎯 下一步：生成 Embeddings

数据导入后，下一步是生成向量嵌入用于 RAG 检索：

```bash
# 生成 embeddings（需要 OpenAI API key）
python3 scripts/generate_embeddings.py
```

这会：
1. 读取所有 chunks
2. 调用 OpenAI API 生成向量
3. 存储到 `embeddings` 表
4. 创建向量索引

**注意：** 需要配置 `OPENAI_API_KEY` 环境变量

## 🛠️ 常见问题

### Q1: 连接失败 "psycopg2.OperationalError: could not connect"

**解决：**
```bash
# 检查 PostgreSQL 是否运行
brew services list | grep postgresql

# 启动 PostgreSQL
brew services start postgresql@14

# 检查连接
psql -l
```

### Q2: "extension 'vector' does not exist"

**解决：**
```bash
# 安装 pgvector
brew install pgvector

# 手动创建扩展
psql unsw_rag
CREATE EXTENSION vector;
```

### Q3: "relation already exists"

说明表已存在，选择：

**选项 1:** 重新初始化（会删除数据）
```bash
python3 scripts/init_database.py
# 选择 'y' 删除现有表
```

**选项 2:** 直接导入（会跳过已存在的数据）
```bash
python3 scripts/import_chunks_to_db.py
```

### Q4: 导入速度慢

**优化：**
1. 临时禁用索引
2. 使用批量插入（脚本已实现）
3. 增加 `work_mem` 设置

```sql
-- PostgreSQL 配置优化
ALTER SYSTEM SET work_mem = '256MB';
SELECT pg_reload_conf();
```

## 📝 Schema 更新

如果需要修改表结构：

1. 修改 [database/rag_schema.py](database/rag_schema.py)
2. 重新初始化数据库
3. 重新导入数据

或使用数据库迁移工具（推荐 Alembic）:

```bash
pip install alembic
alembic init migrations
# 配置并创建迁移
```

## 🔐 安全建议

**生产环境：**
1. 使用密码认证
2. 限制数据库访问权限
3. 使用 SSL 连接
4. 定期备份

```python
# 生产环境配置示例
postgres_dsn: str = "postgresql://user:password@host:5432/unsw_rag?sslmode=require"
```

## 📊 性能监控

```sql
-- 查看表大小
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 查看索引使用情况
SELECT
    indexname,
    idx_scan as scans,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

---

**最后更新:** 2025-12-18
**状态:** ✅ 就绪
**下一步:** 等待 V2 运行完成 → 导入数据 → 生成 embeddings
