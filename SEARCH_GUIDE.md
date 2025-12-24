# 混合搜索系统使用指南

## 🎯 方案C - 专业版实现完成！

已实现完整的混合检索系统：

```
用户查询
    ↓
BM25 + Vector 并行检索
    ↓
RRF 融合
    ↓
Reranker 重排序
    ↓
Citation 格式化
    ↓
返回结果
```

---

## 📋 前置步骤

### 1. 确保数据已导入

```bash
# 检查数据库中是否有数据
psql -U your_username -d unsw_rag -c "SELECT COUNT(*) FROM chunks;"
```

如果没有数据，先运行：
```bash
./run_pipeline.sh
```

### 2. 生成 Embeddings

这是**必须**的步骤，否则无法进行向量搜索：

```bash
# 使用 OpenAI API (推荐)
export OPENAI_API_KEY="your-api-key"
python3 pipeline/step4_generate_embeddings.py

# 或使用本地模型（免费，但稍慢）
python3 pipeline/step4_generate_embeddings.py --model local
```

**预计时间**:
- OpenAI: 约 10-20 分钟（27,000 chunks）
- 本地模型: 约 30-60 分钟

### 3. 安装额外依赖

```bash
pip3 install sentence-transformers  # Reranker 需要
pip3 install numpy  # 向量计算
```

---

## 🚀 快速开始

### 基本搜索

```bash
# 测试搜索功能
python3 test_search.py --query "Industry 4.0"

# 返回更多结果
python3 test_search.py --query "Digital Twin" --top-k 20
```

### 搜索特定类型

```bash
# 只搜索论文
python3 test_search.py --query "machine learning" --publications-only

# 只搜索研究人员
python3 test_search.py --query "robotics" --researchers-only
```

### 运行示例查询

```bash
# 运行多个示例查询
python3 test_search.py --examples
```

### 不使用 Reranker（更快）

```bash
python3 test_search.py --query "sustainability" --no-reranker
```

---

## 💻 编程方式使用

### 基本示例

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from search.hybrid_search import HybridSearchEngine
from pipeline.step4_generate_embeddings import EmbeddingGenerator

# 连接数据库
engine = create_engine(settings.postgres_dsn)
Session = sessionmaker(bind=engine)
session = Session()

# 初始化 embedding generator
embedding_gen = EmbeddingGenerator(model_type="openai")

# 初始化搜索引擎
search_engine = HybridSearchEngine(
    session=session,
    embedding_generator=embedding_gen,
    use_reranker=True
)

# 执行搜索
response = search_engine.search(
    query="Industry 4.0 applications",
    top_k=10
)

# 查看结果
for citation in response['citations']:
    print(f"[{citation['citation_id']}] {citation['citation']['title']}")
```

### 高级搜索

```python
# 只搜索最近5年的论文
response = search_engine.search_publications_only(
    query="Digital Twin",
    top_k=10,
    year_from=2020,
    year_to=2025,
    has_abstract=True
)

# 按学院搜索研究人员
response = search_engine.search_researchers_only(
    query="artificial intelligence",
    top_k=5,
    school="Computer Science and Engineering"
)

# 自定义 chunk 类型
response = search_engine.search(
    query="sustainability",
    top_k=10,
    chunk_types=["publication_abstract", "person_biography"]
)
```

---

## 📊 返回结果格式

搜索返回的JSON格式：

```json
{
  "query": "Industry 4.0",
  "total_results": 150,
  "returned_results": 10,
  "citations": [
    {
      "citation_id": 1,
      "chunk_id": "pub_abstract_...",
      "chunk_type": "publication_abstract",
      "relevance_scores": {
        "bm25": 12.5,
        "vector": 0.87,
        "rrf": 0.032,
        "rerank": 0.92,
        "final": 0.92
      },
      "content_preview": "This paper explores...",
      "citation": {
        "type": "publication",
        "title": "Industry 4.0 in Labor Intensive Industries",
        "authors": ["Shiva Abdoli", "L. Djukic"],
        "year": 2025,
        "venue": "Procedia CIRP",
        "doi": "10.1016/j.procir.2025.08.036",
        "url": "https://doi.org/10.1016/j.procir.2025.08.036",
        "citations_count": 5,
        "is_open_access": true,
        "keywords": ["Industry 4.0", "Manufacturing"],
        "formatted": "Abdoli, S. & Djukic, L. (2025)...",
        "staff": {
          "name": "Dr Shiva Abdoli",
          "email": "s.abdoli@unsw.edu.au",
          "school": "Mechanical and Manufacturing Engineering"
        }
      }
    }
  ],
  "search_metadata": {
    "bm25_results": 45,
    "vector_results": 48,
    "fused_results": 78,
    "reranked": true
  }
}
```

---

## 🔧 组件说明

### 1. BM25 搜索 (`search/bm25_search.py`)

**功能**: 基于关键词的全文搜索

**优势**:
- 精确匹配关键词
- 速度快
- 不需要 embeddings

**使用场景**:
- 已知技术术语（"Digital Twin", "Industry 4.0"）
- 精确的名词搜索

### 2. Vector 搜索 (`search/vector_search.py`)

**功能**: 基于语义的相似度搜索

**优势**:
- 理解语义相似性
- 同义词也能匹配
- 概念级别搜索

**使用场景**:
- 模糊查询（"提高生产效率"）
- 概念搜索（"可持续发展"）

### 3. RRF 融合 (`search/fusion.py`)

**功能**: 合并 BM25 和 Vector 的结果

**算法**: Reciprocal Rank Fusion

**公式**: `Score = Σ 1/(k + rank)`

**优势**:
- 不需要归一化分数
- 鲁棒性好
- 简单有效

### 4. Reranker (`search/reranker.py`)

**功能**: 使用 Cross-Encoder 精细重排序

**模型**: `cross-encoder/ms-marco-MiniLM-L-6-v2`

**优势**:
- 最高精度
- 理解 query-document 交互
- 可以根据元数据增强

**可选模型**:
- 本地: `cross-encoder/ms-marco-MiniLM-L-6-v2` (快速)
- 本地: `cross-encoder/ms-marco-MiniLM-L-12-v2` (更精确)
- Cohere: Rerank API (需要 API key)

### 5. Citation (`search/citation.py`)

**功能**: 格式化引用

**支持格式**:
- APA
- IEEE
- MLA

**特性**:
- 自动链接 DOI
- 包含作者信息
- 显示 UNSW staff
- 可追溯到原文

---

## ⚡ 性能优化

### 当前性能（使用 JSON 存储向量）

- **BM25**: ~50ms
- **Vector**: ~2-5 秒（27,000 chunks）
- **RRF**: ~10ms
- **Reranker**: ~500ms (top 80 → 10)
- **总计**: ~3-6 秒

### 优化方案：启用 pgvector

```sql
-- 安装 pgvector 扩展
CREATE EXTENSION vector;

-- 修改 vector 列类型
ALTER TABLE embeddings
ALTER COLUMN vector TYPE vector(1536)
USING vector::vector;

-- 创建 HNSW 索引
CREATE INDEX embeddings_vector_idx
ON embeddings
USING hnsw (vector vector_cosine_ops);
```

**优化后性能**:
- Vector: ~50-100ms ⚡
- 总计: ~1 秒以内

---

## 🐛 故障排除

### 问题1: ModuleNotFoundError

```bash
# 安装缺失的包
pip3 install sentence-transformers numpy openai
```

### 问题2: Embeddings 未生成

```bash
# 检查
python3 -c "
from sqlalchemy import create_engine
from config.settings import settings
from database.rag_schema import Embedding
from sqlalchemy.orm import sessionmaker

engine = create_engine(settings.postgres_dsn)
Session = sessionmaker(bind=engine)
session = Session()
count = session.query(Embedding).count()
print(f'Embeddings count: {count}')
"

# 如果是 0，需要运行 step4
python3 pipeline/step4_generate_embeddings.py
```

### 问题3: BM25 搜索无结果

```bash
# 设置全文搜索
python3 -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from search.bm25_search import BM25Searcher

engine = create_engine(settings.postgres_dsn)
Session = sessionmaker(bind=engine)
session = Session()

bm25 = BM25Searcher(session)
bm25.setup_full_text_search()
print('✓ Full-text search setup complete')
"
```

### 问题4: Reranker 太慢

```bash
# 禁用 reranker
python3 test_search.py --query "your query" --no-reranker
```

或使用更小的模型：

```python
search_engine = HybridSearchEngine(
    session=session,
    embedding_generator=embedding_gen,
    use_reranker=True,
    reranker_model="local"  # 使用轻量级模型
)
```

---

## 📈 下一步

1. **启用 pgvector** - 大幅提升向量搜索性能
2. **添加 LLM 摘要** - 使用 GPT-4 生成带引用的答案
3. **Web UI** - 创建可视化搜索界面
4. **API 服务** - 部署为 REST API
5. **批量评估** - 测试不同查询的效果

---

## 📝 示例查询

尝试这些查询：

1. **技术查询**:
   - "Industry 4.0 applications in manufacturing"
   - "Digital Twin for building management"
   - "sustainable energy systems"

2. **研究人员查询**:
   - "professors working on machine learning"
   - "robotics researchers"
   - "experts in circular economy"

3. **混合查询**:
   - "recent papers on artificial intelligence"
   - "UNSW research on climate change"
   - "publications about automated manufacturing"

---

最后更新: 2024-12-18
