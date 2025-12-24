# UNSW AI RAG Pipeline - 完整数据处理流程

这个项目用于爬取 UNSW Engineering 教职员工数据和他们的出版物信息，并构建 RAG (Retrieval-Augmented Generation) 系统的知识库。

## 📋 目录

- [流程概述](#流程概述)
- [项目结构](#项目结构)
- [环境配置](#环境配置)
- [使用方法](#使用方法)
- [详细步骤说明](#详细步骤说明)
- [数据库配置](#数据库配置)
- [故障排除](#故障排除)

---

## 🔄 流程概述

完整的数据处理流程包含 3 个步骤:

```
Step 1: 爬取 Staff 数据
   ↓
   从 Funnelback API 获取 staff 基本信息
   爬取每个 staff 的详细 profile 页面
   保存到: data/processed/staff_with_profiles.json

Step 2: 解析 Publications
   ↓
   解析 profile 中的 publication 文本
   从多个源获取 abstract (OpenAlex, Semantic Scholar, Crossref, PubMed)
   生成 RAG chunks
   保存到: data/processed/rag_chunks.json

Step 3: 导入到数据库
   ↓
   创建数据库表结构 (staff, publications, chunks)
   导入所有数据到 PostgreSQL
```

---

## 📁 项目结构

```
unsw_ai_rag/
├── pipeline/                    # 核心处理流程
│   ├── step1_fetch_staff.py         # Step 1: 爬取 staff 数据
│   ├── step2_parse_publications.py  # Step 2: 解析 publications
│   └── step3_import_to_database.py  # Step 3: 导入数据库
│
├── database/                    # 数据库模块
│   ├── rag_schema.py               # RAG 数据库表结构
│   ├── schema.py                   # 旧版表结构
│   └── db.py                       # 数据库连接工具
│
├── config/                      # 配置文件
│   └── settings.py                 # 数据库连接配置
│
├── data/                        # 数据存储
│   ├── processed/                  # 处理后的数据
│   │   ├── staff_with_profiles.json
│   │   └── rag_chunks.json
│   └── cache/                      # 缓存和进度文件
│       ├── parsing_progress.json
│       └── parsing_statistics.json
│
├── run_pipeline.sh              # 主执行脚本
├── requirements.txt             # Python 依赖
└── PIPELINE_README.md          # 本文档
```

---

## ⚙️ 环境配置

### 1. Python 环境

需要 Python 3.8 或更高版本:

```bash
python3 --version
```

### 2. 安装依赖

```bash
pip3 install -r requirements.txt
```

主要依赖:
- `requests` - HTTP 请求
- `beautifulsoup4` - HTML 解析
- `sqlalchemy` - 数据库 ORM
- `psycopg2-binary` - PostgreSQL 驱动

### 3. 数据库配置

编辑 `config/settings.py` 设置数据库连接:

```python
class Settings:
    postgres_dsn = "postgresql://用户名:密码@主机:端口/数据库名"
```

---

## 🚀 使用方法

### 快速开始 - 运行完整流程

```bash
# 赋予执行权限
chmod +x run_pipeline.sh

# 运行完整流程 (Step 1 → 2 → 3)
./run_pipeline.sh
```

### 单独运行某个步骤

```bash
# 只运行 Step 1
./run_pipeline.sh 1

# 只运行 Step 2
./run_pipeline.sh 2

# 只运行 Step 3
./run_pipeline.sh 3
```

### 直接运行 Python 脚本

```bash
# Step 1: 爬取 staff 数据
python3 pipeline/step1_fetch_staff.py

# Step 2: 解析 publications
python3 pipeline/step2_parse_publications.py

# Step 3: 导入数据库
python3 pipeline/step3_import_to_database.py
```

---

## 📖 详细步骤说明

### Step 1: 爬取 Staff 数据

**功能:**
1. 从 Funnelback API 获取 UNSW Engineering 所有 staff 的基本信息
2. 爬取每个 staff 的详细 profile 页面
3. 提取 publications、研究兴趣、个人简介等信息

**输出文件:**
- `data/processed/staff_with_profiles.json`
- `data/cache/staff_basic.json` (中间文件)

**特性:**
- 自动分页获取所有 staff
- 每爬取 10 个 profile 自动保存进度
- 礼貌延迟避免过于频繁请求

**预计时间:** 约 20-30 分钟 (取决于 staff 数量)

---

### Step 2: 解析 Publications

**功能:**
1. 解析 profile 中的 publication 文本，提取标题和 DOI
2. 从多个数据源获取 abstract 和 metadata:
   - **OpenAlex** (优先) - 最全面的 metadata
   - **Semantic Scholar** - 高质量 abstract + TLDR
   - **Crossref** - 权威的出版数据
   - **PubMed** - 生物医学领域论文
3. 生成 RAG chunks (用于向量搜索)

**输出文件:**
- `data/processed/rag_chunks.json`
- `data/cache/parsing_progress.json` (进度文件，支持断点续传)
- `data/cache/parsing_statistics.json` (统计信息)
- `data/cache/parsing.log` (日志)

**特性:**
- **多线程处理** - 默认 5 个并发线程，加快处理速度
- **断点续传** - 可随时中断，下次运行会从上次位置继续
- **智能缓存** - DOI 查询结果会被缓存，避免重复请求
- **自动保存** - 每处理 5 个 staff 自动保存进度

**生成的 Chunk 类型:**
- `person_basic` - Staff 基本信息
- `person_biography` - Staff 个人简介和研究兴趣
- `publication_title` - 论文标题、作者、引用数
- `publication_abstract` - 论文摘要
- `publication_keywords` - 论文关键词

**预计时间:** 约 1-3 小时 (取决于 publication 数量和 API 响应速度)

---

### Step 3: 导入到数据库

**功能:**
1. 创建数据库表结构 (如果不存在)
2. 将 chunks 导入到 PostgreSQL
3. 建立 staff、publications、chunks 之间的关联

**数据库表结构:**
- `staff` - 教职员工信息
- `publications` - 论文信息
- `chunks` - RAG 文本块
- `embeddings` - 向量嵌入 (待实现)

**特性:**
- 自动创建表结构
- Upsert 逻辑 - 已存在的记录会被跳过或更新
- 批量提交 - 每 1000 条记录提交一次
- 详细统计报告

**预计时间:** 约 5-10 分钟

---

## 🗄️ 数据库配置

### PostgreSQL 安装

#### macOS (使用 Homebrew)

```bash
brew install postgresql@14
brew services start postgresql@14
```

#### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### 创建数据库

```bash
# 进入 PostgreSQL
psql postgres

# 创建数据库
CREATE DATABASE unsw_rag;

# 创建用户
CREATE USER rag_user WITH PASSWORD 'your_password';

# 授权
GRANT ALL PRIVILEGES ON DATABASE unsw_rag TO rag_user;
```

### 配置连接字符串

编辑 `config/settings.py`:

```python
class Settings:
    postgres_dsn = "postgresql://rag_user:your_password@localhost:5432/unsw_rag"
```

### 验证数据库连接

```bash
python3 -c "
from config.settings import settings
from sqlalchemy import create_engine
engine = create_engine(settings.postgres_dsn)
print('✓ 数据库连接成功!')
"
```

---

## 🐛 故障排除

### 问题 1: 找不到 Python 包

**错误信息:**
```
ModuleNotFoundError: No module named 'requests'
```

**解决方法:**
```bash
pip3 install -r requirements.txt
```

---

### 问题 2: 数据库连接失败

**错误信息:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**解决方法:**
1. 检查 PostgreSQL 是否运行:
   ```bash
   # macOS
   brew services list

   # Linux
   sudo systemctl status postgresql
   ```

2. 检查 `config/settings.py` 中的连接字符串是否正确

3. 测试连接:
   ```bash
   psql -U rag_user -d unsw_rag -h localhost
   ```

---

### 问题 3: API 请求失败

**错误信息:**
```
requests.exceptions.Timeout: ...
```

**解决方法:**
1. 检查网络连接
2. 减少并发线程数 (编辑 `pipeline/step2_parse_publications.py`):
   ```python
   CONFIG = {
       "max_workers": 3,  # 从 5 减少到 3
       ...
   }
   ```

---

### 问题 4: 中断后如何继续

Step 2 支持断点续传，如果中途中断 (Ctrl+C)，直接再次运行即可:

```bash
python3 pipeline/step2_parse_publications.py
```

进度保存在 `data/cache/parsing_progress.json`

如果想从头开始，删除进度文件:

```bash
rm data/cache/parsing_progress.json
```

---

### 问题 5: 查看处理进度

查看日志:

```bash
tail -f data/cache/parsing.log
```

查看统计信息:

```bash
cat data/cache/parsing_statistics.json | python3 -m json.tool
```

---

## 📊 数据统计

运行完成后，可以查看统计信息:

### Step 2 统计

```bash
cat data/cache/parsing_statistics.json
```

包含:
- 总 staff 数量
- 总 publication 数量
- 有 DOI 的论文数量
- 获取到 abstract 的论文数量
- 各数据源的使用统计
- 错误日志

### 数据库统计

```sql
-- 进入数据库
psql -U rag_user -d unsw_rag

-- 查看各表记录数
SELECT 'staff' as table_name, COUNT(*) FROM staff
UNION ALL
SELECT 'publications', COUNT(*) FROM publications
UNION ALL
SELECT 'chunks', COUNT(*) FROM chunks;

-- 查看各类型 chunk 数量
SELECT chunk_type, COUNT(*)
FROM chunks
GROUP BY chunk_type;

-- 查看有 abstract 的论文比例
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN abstract IS NOT NULL THEN 1 ELSE 0 END) as with_abstract,
    ROUND(100.0 * SUM(CASE WHEN abstract IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as percentage
FROM publications;
```

---

## 🎯 下一步

完成数据导入后，可以:

1. **生成 Embeddings** - 为 chunks 生成向量嵌入
2. **构建 RAG API** - 实现语义搜索和问答功能
3. **可视化分析** - 分析研究领域、合作网络等

---

## 📝 注意事项

1. **爬虫礼貌** - 已设置合理的延迟，请勿修改过短
2. **数据隐私** - staff 数据来自公开网站，但请妥善保管数据库
3. **API 限制** - 某些 API 有速率限制，如遇到大量失败请减少并发数
4. **存储空间** - 完整数据约需 200-500 MB 磁盘空间

---

## 🤝 贡献

如有问题或改进建议，欢迎提 Issue 或 Pull Request。

---

## 📄 许可

此项目仅用于研究和教育目的。
