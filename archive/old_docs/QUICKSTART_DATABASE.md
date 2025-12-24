# 数据库导入 - 快速开始

5 分钟将 JSON 数据导入数据库

## ✅ 前置检查

```bash
# 1. 确保 PostgreSQL 运行
brew services list | grep postgresql

# 2. 确保数据库存在
psql -l | grep unsw_rag
# 如果不存在：createdb unsw_rag

# 3. 确保 V2 已完成
ls -lh rag_chunks_multisource_v2.json
```

## 🚀 三步导入

### 步骤 1: 初始化数据库（首次）

```bash
python3 scripts/init_database.py
```

选择 `N` (不删除现有表，如果首次运行会自动创建)

### 步骤 2: 导入数据

```bash
python3 scripts/import_chunks_to_db.py
```

**预计时间:** 1-5 分钟（取决于数据量）

### 步骤 3: 验证

```bash
psql unsw_rag << 'EOF'
SELECT COUNT(*) as staff FROM staff;
SELECT COUNT(*) as publications FROM publications;
SELECT COUNT(*) as chunks FROM chunks;
SELECT COUNT(*) as no_doi FROM publications WHERE has_doi = FALSE;
EOF
```

## 📊 预期结果

```
     staff
-----------
      649

 publications
--------------
     ~60000

    chunks
-----------
   ~150000

   no_doi
----------
    ~23838  (28%)
```

## ✅ 完成！

数据已导入，可以：
1. 查询数据：`psql unsw_rag`
2. 生成 embeddings (下一步)
3. 构建 RAG 检索系统

---

**遇到问题？** 查看 [README_DATABASE.md](README_DATABASE.md) 完整文档
