# UNSW AI RAG 系统交接文档

**GitHub 仓库**: https://github.com/even1207/unsw_rag
**交接日期**: 2026-03-27
**技术栈**: Python · FastAPI · PostgreSQL + pgvector · OpenAI API

---

## 1. 项目简介

本项目是一个面向 UNSW（新南威尔士大学）的 **研究人员知识库问答系统**，核心能力：

- 自动爬取各 Faculty 教职工 Profile（姓名、职位、简介、论文等）
- 从多个学术数据源（OpenAlex / Semantic Scholar / Crossref / PubMed）获取论文摘要
- 将内容向量化存入 PostgreSQL + pgvector，支持混合检索（BM25 + 语义向量）
- 通过 FastAPI 提供 RAG 问答接口，接入 OpenAI GPT 模型生成回答

典型使用场景：
- "谁在研究 digital twin？"
- "Wenjie Zhang 和 Zhengyi Yang 有哪些合作论文？"
- "UNSW 商学院有哪些金融方向的研究人员？"

---

## 2. 系统架构

```
用户提问
    │
    ▼
FastAPI Server (api_server.py)
    │
    ├── 混合检索 (search/)
    │     ├── BM25 全文检索 (bm25_search.py)
    │     ├── 向量检索 (vector_search.py)
    │     ├── RRF 融合 (fusion.py)
    │     └── Reranker 重排 (reranker.py)
    │
    └── RAG 生成 (rag_generator.py)
          └── OpenAI GPT → 回答 + 引用来源
```

数据流（Pipeline）：
```
Step 1: 爬取 Staff Profiles     → data/processed/staff_{faculty}_profiles.json
Step 2: 解析论文 + 抓取摘要      → data/processed/rag_chunks.json
Step 3: 导入 PostgreSQL          → staff / publications / chunks 表
Step 4: 生成向量 Embeddings      → embeddings 表 (pgvector)
```

---

## 3. 目录结构

```
unsw_ai_rag/
├── api_server.py              # 主入口：FastAPI 服务器
├── api/
│   ├── server.py              # 另一个服务入口（模块化版本）
│   └── routes/
│       ├── rag.py             # /ask 问答路由
│       ├── search.py          # /search 检索路由
│       └── collaboration.py   # /collaboration 合作关系路由
├── pipeline/
│   ├── step1_fetch_staff.py   # 爬取教职工 Profile
│   ├── step2_parse_publications.py  # 解析论文 + 获取摘要
│   ├── step3_import_to_database.py  # 导入数据库
│   └── step4_generate_embeddings.py # 生成向量
├── search/
│   ├── hybrid_search.py       # 混合搜索引擎（主入口）
│   ├── bm25_search.py         # BM25 全文检索
│   ├── vector_search.py       # pgvector 语义检索
│   ├── fusion.py              # RRF 融合算法
│   ├── reranker.py            # Reranker 重排模型
│   ├── rag_generator.py       # RAG 回答生成
│   └── citation.py            # 引用格式化
├── database/
│   ├── schema.sql             # 基础表结构（staff / publications）
│   ├── rag_schema.py          # 完整 SQLAlchemy ORM（含 chunks / embeddings）
│   ├── models.py              # 简单数据类
│   └── db.py                  # 数据库连接
├── scripts/                   # 各类一次性/维护脚本
├── config/
│   ├── settings.py            # 全局配置（读取 .env）
│   └── logging.conf           # 日志配置
├── data/
│   ├── processed/             # 爬虫输出的 JSON 文件
│   └── cache/                 # 断点续传缓存（不入库）
├── tests/                     # 测试文件
├── .env.example               # 环境变量模板
└── requirements.txt           # Python 依赖
```

---

## 4. 环境配置

### 4.1 系统依赖

- Python 3.10+
- PostgreSQL 14+ with pgvector 扩展
- （可选）本地 Sentence Transformers 模型（用于 Reranker）

### 4.2 安装步骤

```bash
# 1. 克隆仓库
git clone git@github.com:even1207/unsw_rag.git
cd unsw_rag

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入以下内容：
#   OPENAI_API_KEY=sk-...
```

### 4.3 数据库配置

```bash
# 安装 pgvector 扩展（macOS Homebrew 示例）
brew install postgresql@16
brew install pgvector

# 创建数据库
createdb unsw_rag

# 在 psql 中启用 pgvector
psql unsw_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 初始化表结构
python scripts/init_database.py
# 或者手动执行：
psql unsw_rag < database/schema.sql
```

`config/settings.py` 中默认连接串为：
```
postgresql://z5241339@localhost:5432/unsw_rag
```
**接手时需修改为实际部署的用户名**，可在 `.env` 中覆盖：
```
POSTGRES_DSN=postgresql://your_user@localhost:5432/unsw_rag
```

---

## 5. 数据流水线（Pipeline）

按顺序运行以下四步，完成数据从爬取到可查询的全流程：

### Step 1：爬取教职工数据

```bash
# 查看支持的 Faculty 列表
python pipeline/step1_fetch_staff.py --list

# 爬取某个 Faculty（支持断点续传）
python pipeline/step1_fetch_staff.py --faculty engineering
python pipeline/step1_fetch_staff.py --faculty arts
python pipeline/step1_fetch_staff.py --faculty business
python pipeline/step1_fetch_staff.py --faculty science
python pipeline/step1_fetch_staff.py --faculty medicine
python pipeline/step1_fetch_staff.py --faculty canberra

# 强制重新爬取（忽略断点）
python pipeline/step1_fetch_staff.py --faculty engineering --fresh

# 仅保存 JSON，不写数据库
python pipeline/step1_fetch_staff.py --faculty engineering --no-db
```

数据源：UNSW Funnelback 搜索 API（校内服务，需校园网或 VPN）

### Step 2：解析论文 + 抓取摘要

```bash
python pipeline/step2_parse_publications.py
```

从 OpenAlex → Semantic Scholar → Crossref → PubMed 依次尝试获取 abstract。
输出：`data/processed/rag_chunks.json`

### Step 3：导入数据库

```bash
python pipeline/step3_import_to_database.py
```

### Step 4：生成向量 Embeddings

```bash
python pipeline/step4_generate_embeddings.py
```

使用 OpenAI text-embedding-3-small 模型，**会产生 OpenAI API 费用**。

---

## 6. 启动 API 服务

```bash
# 启动服务器（默认端口 8000）
python api_server.py

# 自定义端口
python api_server.py --port 8080

# 开发模式（热重载）
python api_server.py --reload
```

看到以下日志说明启动成功：
```
✓ SERVER READY - All models loaded successfully!
```

访问接口文档：http://localhost:8000/docs

### 主要 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/ask` | RAG 问答（主要接口） |
| GET  | `/ask` | RAG 问答（curl 友好版） |
| GET  | `/search` | 纯检索，不生成回答 |
| GET  | `/collaboration` | 查询合作关系 |
| GET  | `/health` | 健康检查 |

问答示例：
```bash
curl -X POST "http://localhost:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "Who works on digital twin research?",
       "max_context": 10,
       "include_sources": true,
       "include_kg": true
     }'
```

---

## 7. 关键配置说明

| 配置项 | 文件 | 说明 |
|--------|------|------|
| `OPENAI_API_KEY` | `.env` | OpenAI API 密钥（必填） |
| `POSTGRES_DSN` | `.env` / `config/settings.py` | 数据库连接串 |
| `funnelback_base_url` | `config/settings.py` | UNSW Funnelback API 地址 |

`config/settings.py` 中的 `funnelback_base_url` 当前为占位值，接手时需确认真实 URL（可在 UNSW 网络内抓包获取）。

---

## 8. 常见问题

**Q: Pipeline Step 1 爬取结果为 0？**
检查是否连接了 UNSW 校园网 / VPN。Funnelback 是校内服务，外网无法直接访问。

**Q: pgvector 安装失败？**
参考 [pgvector 官方文档](https://github.com/pgvector/pgvector)，也可用 Docker 启动带 pgvector 的 PostgreSQL：
```bash
docker run -d -e POSTGRES_DB=unsw_rag -e POSTGRES_PASSWORD=password \
  -p 5432:5432 ankane/pgvector
```

**Q: OpenAI API 费用如何控制？**
Embeddings 生成（Step 4）和 RAG 问答都会调用 OpenAI API。
- 建议先小批量测试（Engineering Faculty 约 790 人）
- `/ask` 接口的 `max_context` 参数控制每次请求的 token 数量，默认 10

**Q: 如何刷新数据？**
定期重跑 Pipeline 的 Step 1 → Step 4 即可。支持断点续传，中断后可继续。

---

## 9. 数据现状（截至交接日）

已爬取的 Faculty 数据（JSON 文件在 `data/processed/`）：

| Faculty | 文件 |
|---------|------|
| Arts, Design & Architecture | `staff_arts_profiles.json` |
| Business School | `staff_business_profiles.json` |
| Canberra | `staff_canberra_profiles.json` |
| Medicine | `staff_medicine_profiles.json` |
| Science | `staff_science_profiles.json` |

Engineering 数据通过 OpenAlex 持续补充（进度记录在 `scripts/.openalex_progress.json`）。

---

## 10. 后续建议

- [ ] 补全 Engineering Faculty 的爬取（目前部分依赖 OpenAlex API 补充）
- [ ] 接入 Law & Justice Faculty（入口可能与其他 Faculty 不同，需单独调查）
- [ ] 将 Pipeline 配置为定期任务（如 cron job），保持数据新鲜
- [ ] 部署到服务器时建议用 `systemd` 或 `Docker Compose` 管理进程
- [ ] 考虑增加认证层（目前 API 无鉴权）
