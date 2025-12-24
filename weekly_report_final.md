# UNSW 研究人员智能搜索引擎 - 工作进展报告

**汇报日期**: 2025年12月22日
**项目状态**: MVP已完成，核心功能验证成功
**汇报对象**: Director

---

## 一、项目目标

构建一个智能搜索引擎，让您能够快速了解:
- 工程学院有哪些研究人员在做某个领域的研究
- 某位教授的研究方向和学术成果
- 某个专业术语或技术的定义和应用场景
- 特定研究主题的最新进展

为学院管理决策、科研合作、人才引进等提供数据支持。

---

## 二、已完成的核心工作

### 1. 数据采集与整理

#### 研究人员数据
- **覆盖范围**: UNSW工程学院全体研究人员 **649人**
- **信息完整性**: 90.3% 的研究人员有学术发表记录

#### 学术论文数据
- **论文总数**: **62,726篇** 学术论文
- **数据来源**: OpenAlex开源学术数据库 (免费API)
- **平均产出**: 每位研究人员约107篇论文
- **时间跨度**: 1932年至今 (近5年产出约16,500篇，占26%)

#### 数据质量指标
| 数据类型 | 数量 | 覆盖率 |
|---------|------|--------|
| 研究人员基本信息 | 649 | 100% |
| 有学术发表的研究人员 | 586 | 90.3% |
| 论文摘要(详细) | 21,516 | 34.3% |
| 论文DOI(引用追踪) | 61,357 | 97.8% |
| 研究主题标签 | 34,528 | 55.0% |

### 2. 智能检索系统

采用**混合检索技术**(Hybrid Search):
- **关键词匹配**: 精确查找专业术语
- **语义理解**: 理解查询意图,找到相关内容
- **智能重排序**: 二次排序提升准确度

**性能指标**:
- 响应时间: <2秒
- 支持中英文查询
- 可处理复杂自然语言问题

---

## 三、功能演示

### 示例 1: 专业术语查询

**问题**: "What is digital twin technology?"

**系统回答**:
> Digital twin technology (DT) is a transformative concept that bridges the cyber and physical realms, significantly contributing to advancements in smart manufacturing and Industry 4.0. Digital twins are virtual models that accurately reflect physical objects or systems, enabling enhanced analysis and optimization of processes.
>
> The role of data is pivotal in the functionality of digital twins. Data is essential for constructing virtual models and establishing cyber-physical connections. Digital twins offer innovative solutions for complexity management in intelligent manufacturing, thereby facilitating a more autonomous and analytical approach.

**引用来源**: 8篇相关论文
- "Digital Twin in Industry: State-of-the-Art" (IEEE Transactions, 2019)
- "Digital twin data: methods and key technologies" (Digital Twin, 2021)
- "Digital twin-driven product design framework" (IJPR, 2018)
- ... 等

**检索过程**:
- BM25关键词检索: 35篇相关文献
- 向量语义检索: 42篇相关文献
- 智能重排序: 精选8篇最相关
- GPT生成回答: 整合信息并附引用

---

### 示例 2: 研究人员查询

**问题**: "Tell me about Professor Arcot Sowmya"

**系统回答**:
> Professor Arcot Sowmya is a prominent academic in the field of Computer Science and Engineering at UNSW, where he serves as the Head of School. He holds a PhD in Computer Science from IIT Bombay, and has significant focus on research areas including **Machine Learning and Computer Vision**.
>
> His work encompasses learning object models, feature extraction, segmentation, and recognition, utilizing various methodologies from machine learning and deep learning. Notably, his research has applications in **medical image analysis**, which indicates a strong interdisciplinary approach bridging technology and healthcare.

**数据来源**: 教授个人主页 + 研究发表记录

---

## 四、当前限制

### 1. 数据源质量 【优先级: 高】

**当前状况**:
- 使用免费的OpenAlex公开数据库
- 论文摘要覆盖率仅**34.3%** (21,516 / 62,726)

**实际影响**:
- 约65%的论文缺少详细摘要,只能基于标题和关键词检索
- 检索精度和答案质量受限
- 最新论文可能收录滞后

**改进方案**:
如果能获得UNSW图书馆订阅数据库的API访问权限:
- Scopus (Elsevier)
- Web of Science (Clarivate)
- IEEE Xplore

**预期提升**:
- 摘要覆盖率: 34% → **80%+**
- 数据更新更及时
- 引用关系更完整

---

### 2. 数据维度有限 【优先级: 待确认】

**当前系统能回答**:
- ✅ 某个研究领域有哪些研究人员?
- ✅ 某位教授的研究方向和代表性论文?
- ✅ 某个专业术语的定义和应用?
- ✅ 某个主题有哪些最新研究?

**当前系统无法回答**:
- ❌ 某位教授获得了哪些科研经费?金额多少?
- ❌ 哪些研究人员有重要的跨机构合作?
- ❌ 哪些研究成果转化成了专利或商业产品?
- ❌ 某个研究组的人员构成和实验室设施?

**缺失的数据源**:

| 数据类型 | 决策价值 | 获取难度 |
|---------|---------|---------|
| 科研经费 (Grants) | ⭐⭐⭐⭐⭐ | 中-高 |
| 专利与转化 (Patents) | ⭐⭐⭐⭐⭐ | 中 |
| 合作网络 (Collaborations) | ⭐⭐⭐⭐ | 低-中 |
| 学生培养 (PhD Supervision) | ⭐⭐⭐⭐ | 中 |
| 行业项目 (Industry Projects) | ⭐⭐⭐⭐ | 高 |

**需要明确**:
1. 哪些数据维度对您的决策最有价值?(请按优先级排序)
2. 这些数据能否合规获取?(数据隐私、访问权限)
3. 系统的主要使用场景和用户群体?

---

### 3. 权限管理 【优先级: 待确认】

**当前状况**:
- 所有用户看到全部工程学院的数据
- 无法按学院/学系/研究组分级查询

**可能需求**:
- 院长查看本学院数据
- 研究组长查看本组成果
- 按faculty/school/group分类

**需要确认**:
- 是否需要这个功能?
- 优先级有多高?
- 预期的使用场景?

---

## 五、建议的下一步

### 短期 (2-3周)

#### 1. 业务需求确认会议
与您进行深入讨论 (30-60分钟):
- 确认系统的主要使用场景
- 明确数据维度的优先级
- 确定权限管理的必要性
- 评估预算和时间线

#### 2. 数据库权限申请
- 申请UNSW图书馆学术数据库API访问权限
- 联系IT部门/图书馆了解流程
- 预估时间: 2-4周

### 中期 (1-2个月)

#### 1. 数据源扩展
根据确认的优先级,依次接入:
- Scopus/Web of Science (提升论文质量)
- 科研经费数据 (如可获取)
- 专利数据库

#### 2. 功能增强
- 数据可视化 (研究趋势、合作网络)
- 权限管理 (如需要)
- 性能优化 (响应时间<1秒)

---

## 六、总结

### ✅ 已完成
- **649名** 研究人员数据完整录入
- **62,726篇** 论文可检索
- **智能搜索** 功能验证成功
- **MVP系统** 运行稳定

### 📊 核心数据
- 90%+ 研究人员有学术记录
- 每人平均107篇论文
- 时间跨度: 1932年至今
- 查询响应<2秒
- 近年产出稳定 (2015年后每年2,500-3,500篇)

### 🎯 关键挑战
- **数据质量**: 需学术数据库权限 (摘要覆盖率34% → 80%+)
- **功能定位**: 需明确业务需求和数据优先级
- **扩展性**: 需确认是否需要经费、专利等额外数据

### 💡 建议
这是一个**技术上已验证的MVP**。下一步的关键是:
1. **获取更好的数据源** (质的提升) - 需要您协助申请权限
2. **明确业务需求** (方向确认) - 需要安排讨论会议
3. **迭代开发功能** (量的增长) - 根据反馈逐步添加

建议先解决数据质量问题,再根据实际使用场景逐步扩展功能。

---

## 七、需要您的支持

### 1. 数据访问权限 【关键】
协助申请UNSW图书馆学术数据库API权限,这将使系统质量提升一个档次。

### 2. 业务需求讨论 【重要】
安排一次会议深入讨论系统定位和功能优先级。

### 3. 数据合规确认 【必要】
确认各类数据(特别是经费、学生信息)的使用是否符合隐私政策。

---

**如需系统演示或进一步讨论,请随时联系。**

---

## 附录: 技术信息

### 系统架构
- **数据库**: PostgreSQL + pgvector (向量检索)
- **检索**: BM25 + Vector Search + Reranker
- **AI模型**: GPT-4o-mini (回答生成)
- **向量模型**: OpenAI text-embedding-3-small

### 性能指标
- 响应时间: 1.5-2.0秒
- 向量维度: 1536维
- 索引: HNSW高性能向量检索
- 支持并发查询

### API访问
```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is digital twin?", "max_context": 10}'
```
