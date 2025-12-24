# 数据库表结构 (Database Schema)

## 📊 数据存储方式

目前采用 **关系型数据库 + JSON** 存储方式：

- **结构化字段**: 基本信息、索引字段
- **JSON字段**: 复杂嵌套数据（authors, concepts, metadata）
- **向量字段**: 暂时用JSON存储，未来迁移到pgvector

---

## 🗂️ 表结构总览

```
┌─────────────────┐
│     staff       │  (教职员工表)
│  PK: email      │
└────────┬────────┘
         │ 1
         │
         │ N
    ┌────┴──────────────────┐
    │                       │
    ↓ N                     ↓ N
┌──────────────┐      ┌──────────────┐
│ publications │      │   chunks     │  (RAG文本块表)
│  PK: id      │      │ PK: chunk_id │
└──────┬───────┘      └──────┬───────┘
       │ 1                   │ 1
       │                     │
       │ N                   │ 1
       ↓                     ↓
   ┌───────────┐       ┌────────────┐
   │  chunks   │       │ embeddings │  (向量嵌入表)
   └───────────┘       │ PK:chunk_id│
                       └────────────┘
```

---

## 📋 详细表结构

### 1️⃣ staff (教职员工表)

**存储内容**: UNSW Engineering 教职员工的基本信息和个人简介

| 字段名 | 类型 | 索引 | 说明 | 示例 |
|--------|------|------|------|------|
| **email** | String(255) | 🔑 PK | 邮箱（主键） | `s.abdoli@unsw.edu.au` |
| **full_name** | String(255) | 📇 Index | 全名 | `Dr Shiva Abdoli` |
| first_name | String(100) | | 名 | `Shiva` |
| last_name | String(100) | | 姓 | `Abdoli` |
| role | String(255) | | 职位 | `Senior Lecturer` |
| **faculty** | String(255) | 📇 Index | 学院 | `Engineering` |
| **school** | String(255) | 📇 Index | 学系 | `Mechanical and Manufacturing Engineering` |
| phone | String(50) | | 电话 | `+61 2 9385...` |
| profile_url | String(512) | | Profile URL | `https://www.unsw.edu.au/staff/...` |
| photo_url | String(512) | | 照片URL | `https://api.research.unsw.edu.au/...` |
| summary | Text | | 简短介绍 | `Doctor Shiva Abdoli is a researcher...` |
| **biography** | Text | | 详细简历 | 完整的个人简介文本 |
| **research_text** | Text | | 研究方向 | `Climate adaptation & built environment...` |
| created_at | DateTime | | 创建时间 | 自动生成 |
| updated_at | DateTime | | 更新时间 | 自动更新 |

**关系**:
- `publications`: 1对多 → publications表
- `chunks`: 1对多 → chunks表

**当前数据量**: ~278 条记录

---

### 2️⃣ publications (论文表)

**存储内容**: 教职员工发表的学术论文信息

| 字段名 | 类型 | 索引 | 说明 | 示例 |
|--------|------|------|------|------|
| **id** | String(255) | 🔑 PK | 主键（DOI或hash） | `10.1016/j.procir.2025.08.036` |
| **doi** | String(255) | 📇 Unique | DOI | `10.1016/j.procir.2025.08.036` |
| **title** | Text | | 论文标题 | `Industry 4.0 in Labor Intensive Industries...` |
| **publication_year** | Integer | 📇 Index | 发表年份 | `2025` |
| **pub_type** | String(100) | 📇 Index | 论文类型 | `Journal Articles`, `Conference Papers` |
| venue | String(512) | | 发表期刊/会议 | `Procedia CIRP` |
| **abstract** | Text | | 摘要 | 完整的论文摘要文本 |
| **abstract_source** | String(50) | 📇 Index | 摘要来源 | `OpenAlex`, `Semantic Scholar` |
| **authors** | JSON | | 作者列表 | `[{"name": "Shiva Abdoli"}, {"name": "..."}]` |
| citations_count | Integer | | 引用次数 | `42` |
| is_open_access | Boolean | | 是否开放获取 | `true` / `false` |
| pdf_url | String(512) | | PDF链接 | `https://...` |
| **concepts** | JSON | | 关键词/概念 | `[{"name": "Industry 4.0", "score": 0.85}]` |
| **has_doi** | Boolean | 📇 Index | 是否有DOI | `true` / `false` |
| **staff_email** | String(255) | 📇 FK | 关联的staff | `s.abdoli@unsw.edu.au` |
| created_at | DateTime | | 创建时间 | 自动生成 |
| updated_at | DateTime | | 更新时间 | 自动更新 |

**关系**:
- `staff`: 多对1 ← staff表 (通过 staff_email)
- `chunks`: 1对多 → chunks表

**当前数据量**: ~5,000-7,000 条记录

**JSON字段示例**:

```json
// authors 字段
[
  {"name": "Shiva Abdoli"},
  {"name": "L. Djukic"}
]

// concepts 字段
[
  {"name": "Industry 4.0", "score": 0.85},
  {"name": "Digital Twin", "score": 0.72},
  {"name": "Manufacturing", "score": 0.68}
]
```

---

### 3️⃣ chunks (RAG文本块表)

**存储内容**: 用于向量检索的文本块，是RAG系统的核心数据

| 字段名 | 类型 | 索引 | 说明 | 示例 |
|--------|------|------|------|------|
| **chunk_id** | String(255) | 🔑 PK | 块ID | `person_basic_s.abdoli@unsw.edu.au` |
| **chunk_type** | String(50) | 📇 Index | 块类型 | `person_basic`, `publication_abstract` 等 |
| **content** | Text | | 文本内容 | 实际的文本内容 |
| **chunk_metadata** | JSON | | 元数据 | 包含所有相关信息 |
| **staff_email** | String(255) | 📇 FK | 关联的staff | `s.abdoli@unsw.edu.au` |
| publication_id | String(255) | 📇 FK | 关联的publication | DOI或hash (可为空) |
| created_at | DateTime | | 创建时间 | 自动生成 |

**Chunk类型 (chunk_type)**:

| 类型 | 说明 | 数量 | 内容示例 |
|------|------|------|----------|
| `person_basic` | Staff基本信息 | 278 | 姓名、职位、学院、联系方式 |
| `person_biography` | Staff个人简介 | ~220 | 详细简历、研究方向 |
| `publication_title` | 论文标题和基本信息 | ~7,000 | 标题、作者、年份、引用数 |
| `publication_abstract` | 论文摘要 | ~3,200 | 完整的论文摘要 |
| `publication_keywords` | 论文关键词 | ~2,500 | 研究领域关键词 |

**关系**:
- `staff`: 多对1 ← staff表 (通过 staff_email)
- `publication`: 多对1 ← publications表 (通过 publication_id)
- `embedding`: 1对1 → embeddings表

**当前数据量**: ~27,000+ 条记录

**JSON字段示例 (chunk_metadata)**:

```json
// person_basic chunk 的 metadata
{
  "person_name": "Dr Shiva Abdoli",
  "person_email": "s.abdoli@unsw.edu.au",
  "role": "Senior Lecturer",
  "school": "Mechanical and Manufacturing Engineering",
  "faculty": "Engineering",
  "profile_url": "https://www.unsw.edu.au/staff/shiva-abdoli"
}

// publication_abstract chunk 的 metadata
{
  "person_name": "Dr Shiva Abdoli",
  "person_email": "s.abdoli@unsw.edu.au",
  "person_school": "Mechanical and Manufacturing Engineering",
  "pub_title": "Industry 4.0 in Labor Intensive Industries...",
  "pub_year": 2025,
  "pub_doi": "10.1016/j.procir.2025.08.036",
  "pub_venue": "Procedia CIRP",
  "citations_count": 5,
  "is_open_access": true,
  "has_abstract": true,
  "abstract_source": "OpenAlex"
}
```

**content字段示例**:

```text
// person_basic chunk
Dr Shiva Abdoli
Position: Senior Lecturer
School: Mechanical and Manufacturing Engineering
Faculty: Engineering

// publication_abstract chunk
Paper: Industry 4.0 in Labor Intensive Industries, Opportunities and Challenges
Author: Dr Shiva Abdoli (Mechanical and Manufacturing Engineering)
Year: 2025

Abstract:
This paper explores the implementation of Industry 4.0 technologies
in labor-intensive industries. It examines both the opportunities
for automation and digitalization, as well as the challenges related
to workforce adaptation and economic constraints...

[Source: OpenAlex]
```

---

### 4️⃣ embeddings (向量嵌入表)

**存储内容**: 文本块的向量表示，用于语义搜索

| 字段名 | 类型 | 索引 | 说明 | 示例 |
|--------|------|------|------|------|
| **chunk_id** | String(255) | 🔑 PK, FK | 关联的chunk | `person_basic_s.abdoli@unsw.edu.au` |
| **vector** | JSON | 🔍 HNSW | 向量数组 (1536维) | `[0.123, -0.456, 0.789, ...]` |
| model | String(100) | | 嵌入模型 | `text-embedding-ada-002` |
| created_at | DateTime | | 创建时间 | 自动生成 |

**关系**:
- `chunk`: 1对1 ← chunks表 (通过 chunk_id)

**当前状态**: ❌ **空表** - 尚未生成向量

**向量索引**:
- 类型: HNSW (Hierarchical Navigable Small World)
- 距离度量: Cosine Similarity
- 维度: 1536 (OpenAI text-embedding-ada-002)

**注意**:
- 目前使用JSON存储向量（临时方案）
- 未来将迁移到 pgvector 类型以提升性能
- 需要启用 pgvector 扩展

---

## 🔗 表关系图

```
staff (1) ──────────> (*) publications
  │                        │
  │ email                  │ id
  │                        │
  ↓                        ↓
chunks (*)               chunks (*)
  │
  │ chunk_id
  │
  ↓
embeddings (1)
```

---

## 📊 数据统计

| 表名 | 记录数 | 存储大小 | 状态 |
|------|--------|----------|------|
| staff | 278 | ~1 MB | ✅ 已填充 |
| publications | ~5,000-7,000 | ~10 MB | ✅ 已填充 |
| chunks | ~27,000 | ~50 MB | ✅ 已填充 |
| embeddings | 0 | 0 MB | ❌ 空表 |

---

## 🗃️ 数据流转

```
JSON文件 (staff_with_profiles.json)
    ↓ Step 2
RAG Chunks JSON (rag_chunks.json)
    ↓ Step 3
PostgreSQL 数据库
    ↓ Step 4 (待完成)
生成 Embeddings
    ↓
RAG 语义搜索
```

---

## 🔍 查询示例

### 查看所有表记录数

```sql
SELECT
    'staff' as table_name,
    COUNT(*) as count
FROM staff

UNION ALL

SELECT
    'publications',
    COUNT(*)
FROM publications

UNION ALL

SELECT
    'chunks',
    COUNT(*)
FROM chunks

UNION ALL

SELECT
    'embeddings',
    COUNT(*)
FROM embeddings;
```

### 查看 Chunk 类型分布

```sql
SELECT
    chunk_type,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
FROM chunks
GROUP BY chunk_type
ORDER BY count DESC;
```

### 查看有 Abstract 的论文比例

```sql
SELECT
    COUNT(*) as total_publications,
    SUM(CASE WHEN abstract IS NOT NULL THEN 1 ELSE 0 END) as with_abstract,
    ROUND(
        100.0 * SUM(CASE WHEN abstract IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) as percentage
FROM publications;
```

### 查看某个 Staff 的所有数据

```sql
-- 基本信息
SELECT * FROM staff WHERE email = 's.abdoli@unsw.edu.au';

-- 论文列表
SELECT title, publication_year, citations_count
FROM publications
WHERE staff_email = 's.abdoli@unsw.edu.au'
ORDER BY publication_year DESC;

-- Chunks
SELECT chunk_type, LEFT(content, 100) as preview
FROM chunks
WHERE staff_email = 's.abdoli@unsw.edu.au';
```

### 查询JSON字段

```sql
-- 查询特定关键词的论文
SELECT
    p.title,
    p.publication_year,
    c->>'name' as concept_name,
    (c->>'score')::float as score
FROM publications p,
     jsonb_array_elements(p.concepts::jsonb) c
WHERE c->>'name' ILIKE '%Industry 4.0%'
ORDER BY (c->>'score')::float DESC;
```

---

## ⚡ 索引策略

### 当前索引

| 表 | 字段 | 类型 | 用途 |
|----|------|------|------|
| staff | email | PRIMARY KEY | 主键查询 |
| staff | full_name | B-Tree | 按名字搜索 |
| staff | faculty | B-Tree | 按学院筛选 |
| staff | school | B-Tree | 按学系筛选 |
| publications | id | PRIMARY KEY | 主键查询 |
| publications | doi | UNIQUE | DOI查询 |
| publications | publication_year | B-Tree | 按年份筛选 |
| publications | pub_type | B-Tree | 按类型筛选 |
| publications | abstract_source | B-Tree | 按来源筛选 |
| publications | staff_email | B-Tree (FK) | Join查询 |
| chunks | chunk_id | PRIMARY KEY | 主键查询 |
| chunks | chunk_type | B-Tree | 按类型筛选 |
| chunks | staff_email | B-Tree (FK) | Join查询 |
| chunks | publication_id | B-Tree (FK) | Join查询 |

### 未来索引 (待实现)

| 表 | 字段 | 类型 | 用途 |
|----|------|------|------|
| embeddings | vector | **HNSW** | 向量相似度搜索 |
| chunks | content | **GIN (全文)** | 全文搜索 |

---

## 🚀 下一步：生成向量

要实现真正的RAG语义搜索，需要：

1. **生成Embeddings** - 为所有chunks生成向量
2. **安装pgvector** - 启用PostgreSQL向量扩展
3. **创建向量索引** - HNSW索引加速搜索
4. **实现相似度搜索** - 基于余弦相似度检索

详见: `PIPELINE_README.md` 中的向量化步骤

---

最后更新: 2024-12-18
