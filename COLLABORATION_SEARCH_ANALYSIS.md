# 合作论文搜索问题分析与解决方案

## 问题诊断

### 当前问题
查询: `"zhengyi yang and wenjie zhang's cooperated paper"`
结果: 返回了 https://dl.acm.org/doi/10.1145/3487553.3526094，但这篇论文的authors字段为空

### 根本原因

#### 1. 数据收集问题
- **Zhengyi Yang不在staff数据库中**
  ```sql
  SELECT full_name FROM staff WHERE full_name ILIKE '%yang%' AND full_name ILIKE '%zheng%';
  -- 结果: 0 rows
  ```
- 只收录了UNSW staff的信息,非UNSW的合作者没有被收录

#### 2. 数据结构问题
- **publications.authors 字段为空**
  ```sql
  SELECT doi, authors FROM publications WHERE doi = '10.1145/3487553.3526094';
  -- authors: []
  ```
- 数据抓取时authors字段没有正确填充
- 当前系统是 **单staff-多publication** 的一对多关系
- 缺少 **多对多关系**: publication ↔ staff

#### 3. 系统架构问题
```
当前架构:
Staff (1) -----> (N) Publications
      ↓
   Chunks

缺失的架构:
Staff (M) <-----> (N) Publications  (多对多)
Staff (M) <-----> (N) Staff         (合作关系图)
```

#### 4. 搜索策略问题
- 当前搜索: 简单的文本匹配 (BM25 + Vector)
- 缺少: 实体识别 → 关系推理 → 图查询

---

## 数据验证

### 检查Wenjie Zhang的论文
```sql
SELECT
    p.title,
    p.authors::text,
    s.full_name
FROM publications p
JOIN staff s ON p.staff_email = s.email
WHERE s.full_name ILIKE '%wenjie%zhang%'
LIMIT 5;
```

结果显示:
- 187篇论文关联到 Wenjie Zhang
- 但 `authors` 字段普遍为空 `[]`

### 检查合作论文
```sql
SELECT COUNT(*)
FROM publications
WHERE authors::text ILIKE '%yang%'
  AND authors::text ILIKE '%zhang%';
-- 结果: 0 rows (因为authors字段为空)
```

---

## 解决方案

### 方案A: 最小化修复 (快速但不完美)

#### 1. 修复authors字段数据
**目标**: 填充publications表的authors字段

```python
# 在 pipeline/step2_parse_publications.py 中
# _fetch_openalex() 已经返回了authors,但可能没有正确保存

# 检查代码:
def _fetch_openalex(self, doi: str) -> Optional[Dict]:
    # ...
    return {
        "authors": [
            {"name": a.get("author", {}).get("display_name")}
            for a in data.get("authorships", [])
        ],
        # ...
    }
```

**问题**: 这个数据可能在导入数据库时丢失了
**解决**: 检查 `step3_import_to_database.py` 确保authors正确写入

#### 2. 增强搜索策略
在BM25搜索中添加对authors字段的检索:
```python
# search/bm25_search.py
def search(self, query, ...):
    # 当前只搜索 content
    # 改进: 同时搜索 publications.authors

    # 步骤1: 识别查询中的人名 (简单版本)
    words = query.lower().split()
    potential_names = [w for w in words if len(w) > 3]

    # 步骤2: 在authors字段中搜索
    sql = """
        SELECT ... FROM publications
        WHERE authors::text ILIKE %any_name%
    """
```

#### 3. 实现简单的实体识别
```python
# search/entity_recognition.py
def extract_person_names(query: str) -> List[str]:
    """从查询中提取人名"""
    # 使用简单的模式匹配或NER模型
    # 例如: "zhengyi yang and wenjie zhang" → ["zhengyi yang", "wenjie zhang"]
    pass

def search_collaborations(names: List[str], session) -> List[Publication]:
    """搜索这些人的合作论文"""
    # 查找authors字段包含所有这些名字的论文
    pass
```

---

### 方案B: 图数据库增强 (完整解决方案)

#### 1. 扩展数据模型

**新增表: staff_publication_authorship (多对多关系)**
```python
class StaffPublicationAuthorship(Base):
    __tablename__ = 'staff_publication_authorship'

    staff_email = Column(String, ForeignKey('staff.email'), primary_key=True)
    publication_id = Column(String, ForeignKey('publications.id'), primary_key=True)
    author_position = Column(Integer)  # 第几作者
    is_corresponding = Column(Boolean)
```

**新增表: staff_collaboration (合作关系图)**
```python
class StaffCollaboration(Base):
    __tablename__ = 'staff_collaborations'

    staff1_email = Column(String, ForeignKey('staff.email'), primary_key=True)
    staff2_email = Column(String, ForeignKey('staff.email'), primary_key=True)
    collaboration_count = Column(Integer)  # 合作次数
    publications = Column(JSON)  # 合作论文列表
    first_collaboration_year = Column(Integer)
    last_collaboration_year = Column(Integer)
```

#### 2. 新增数据处理步骤

**pipeline/step2.5_build_collaboration_graph.py**
```python
def build_collaboration_graph():
    """
    从publications.authors字段构建合作关系图

    步骤:
    1. 读取所有publications的authors
    2. 对每篇论文,找出哪些authors是UNSW staff
    3. 创建 staff_publication_authorship 记录
    4. 统计每对staff的合作次数,创建 staff_collaborations 记录
    """
    pass
```

#### 3. 增强搜索引擎

**search/collaboration_search.py**
```python
class CollaborationSearchEngine:
    """合作关系搜索引擎"""

    def search_coauthored_papers(
        self,
        author_names: List[str]
    ) -> List[Publication]:
        """
        搜索多个作者的合作论文

        步骤:
        1. 识别查询中的人名
        2. 在staff表中查找这些人
        3. 在 staff_publication_authorship 中找到共同的publication_id
        4. 返回这些论文
        """

        # 示例SQL:
        sql = """
            SELECT p.*
            FROM publications p
            JOIN staff_publication_authorship spa1
                ON p.id = spa1.publication_id
            JOIN staff_publication_authorship spa2
                ON p.id = spa2.publication_id
            WHERE spa1.staff_email IN (...)
              AND spa2.staff_email IN (...)
        """
        pass

    def find_collaboration_network(
        self,
        staff_email: str,
        depth: int = 2
    ) -> Dict:
        """
        查找staff的合作网络
        返回: 合作者列表,合作论文,合作强度等
        """
        pass
```

#### 4. 集成到主搜索引擎

**search/hybrid_search.py 增强**
```python
class HybridSearchEngine:
    def search(self, query, ...):
        # 步骤0: 查询理解
        query_intent = self.analyze_query_intent(query)

        if query_intent == "collaboration_search":
            # 使用合作关系搜索
            names = extract_person_names(query)
            return self.collaboration_searcher.search_coauthored_papers(names)
        else:
            # 原有的混合搜索流程
            # BM25 + Vector + RRF + Reranker
            pass

    def analyze_query_intent(self, query):
        """分析查询意图"""
        keywords = ["cooperate", "collaborate", "co-author", "together", "and"]
        if any(kw in query.lower() for kw in keywords):
            if self.has_multiple_person_names(query):
                return "collaboration_search"
        return "general_search"
```

---

### 方案C: 使用现有authors字段 (如果数据已存在)

如果 `publications.authors` 字段实际上有数据,只是在某些情况下为空:

#### 1. 检查数据质量
```sql
-- 检查有多少论文有authors数据
SELECT
    COUNT(*) as total,
    COUNT(CASE WHEN authors IS NOT NULL AND authors::text != '[]' THEN 1 END) as with_authors,
    COUNT(CASE WHEN authors IS NULL OR authors::text = '[]' THEN 1 END) as without_authors
FROM publications;
```

#### 2. 直接在authors字段上搜索
```python
def search_by_multiple_authors(author_names: List[str], session):
    """在authors JSON字段中搜索"""

    # PostgreSQL JSON查询
    sql = """
        SELECT * FROM publications
        WHERE
            -- 检查authors数组中是否包含所有给定的名字
            (SELECT COUNT(DISTINCT name)
             FROM jsonb_array_elements(authors)
             WHERE name ILIKE ANY(:names)
            ) >= :min_matches
    """

    return session.execute(
        text(sql),
        {"names": [f"%{name}%" for name in author_names],
         "min_matches": len(author_names)}
    ).fetchall()
```

---

## 推荐实施顺序

### 阶段1: 数据修复 (1-2天)
1. ✅ 检查publications.authors字段的数据完整性
2. ✅ 如果数据缺失,重新运行 step2 或编写补丁脚本修复
3. ✅ 验证修复后的数据

### 阶段2: 基础功能 (2-3天)
1. ✅ 实现简单的人名提取 (正则表达式或SpaCy NER)
2. ✅ 在authors字段上实现合作论文搜索
3. ✅ 集成到现有搜索引擎

### 阶段3: 图数据增强 (3-5天)
1. ✅ 创建多对多关系表
2. ✅ 构建合作关系图
3. ✅ 实现图查询功能

### 阶段4: 智能查询理解 (可选,3-5天)
1. ✅ 使用LLM进行查询意图识别
2. ✅ 实体识别和消歧
3. ✅ 高级图查询 (如"找出A和B的共同合作者")

---

## 快速验证

### 测试数据修复
```bash
# 检查authors字段
psql unsw_rag -c "
    SELECT doi, title,
           jsonb_array_length(authors) as author_count,
           authors
    FROM publications
    WHERE doi = '10.1145/3487553.3526094';
"
```

### 测试合作搜索
```python
# 简单测试脚本
from sqlalchemy import create_engine, text

engine = create_engine("postgresql://...")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT title, authors
        FROM publications
        WHERE authors::text ILIKE '%yang%'
          AND authors::text ILIKE '%zhang%'
        LIMIT 10
    """))

    for row in result:
        print(row.title)
        print(row.authors)
```

---

## 总结

**核心问题**:
1. Authors字段数据缺失
2. 缺少多对多关系和合作关系图
3. 搜索引擎无法理解"合作"这个语义

**最快解决方案**:
- 修复authors字段数据 (检查step2和step3的代码)
- 添加基于authors字段的JSON查询
- 在搜索中检测查询是否包含多个人名

**长期解决方案**:
- 建立完整的合作关系图
- 实现图查询引擎
- 使用LLM进行查询理解和实体识别
