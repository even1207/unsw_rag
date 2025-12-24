# UNSW 研究人员智能搜索引擎 - 工作进展周报

**汇报日期**: 2025年12月22日
**项目状态**: MVP已完成，核心功能验证成功
**汇报对象**: Director

---

## 一、项目概述

本项目旨在构建一个智能搜索引擎，帮助快速查询和了解UNSW工程学院研究人员的研究方向、学术成果和专业领域，为学院管理决策提供数据支持。

---

## 二、已完成的工作

### 1. 数据采集

#### 研究人员信息
- **采集范围**: UNSW工程学院全部研究人员
- **数据量**: 成功爬取 **649名** 教职工的个人资料
- **覆盖率**:
  - 有学术发表记录: 586人 (90.3%)
  - 有个人简介信息: 632人 (97.4%)

#### 学术发表信息
- **数据来源**: OpenAlex开源学术数据库API
- **论文总数**: 62,726篇学术论文
- **人均论文**: 平均每位研究人员约107篇
- **数据完整性**:
  - 包含摘要(Abstract): 21,516篇 (34.3%)
  - 包含DOI: 61,357篇 (97.8%)
  - 包含主题标签(Topics/Keywords): 34,528篇

#### 学院分布
排名前5的学院:
1. 计算机科学与工程学院: 105人
2. 土木与环境工程学院: 82人
3. 机械与制造工程学院: 82人
4. 电气工程与通信学院: 81人
5. 光伏与可再生能源工程学院: 79人

#### 时间覆盖
近5年(2020-2025)学术产出:
- 2025年: 2,744篇
- 2024年: 3,325篇
- 2023年: 3,336篇
- 2022年: 3,336篇
- 2021年: 3,425篇

### 2. 技术实现

#### 智能检索系统
采用**混合检索技术**(Hybrid Search)，结合两种检索方式:
- **关键词匹配** (BM25算法): 精确查找专业术语
- **语义理解** (向量检索): 理解查询意图，找到相关内容
- **智能重排序** (Reranker): 对结果进行二次排序，提升准确度

技术指标:
- 文本块(Chunks)总数: 120,489个
- 检索响应时间: <2秒
- 支持中英文自然语言查询

### 3. 功能验证

系统已能成功回答以下类型的查询:

#### ✅ 专业术语查询

**问题**: "What is digital twin technology?"

**系统回答**:
> Digital twin technology (DT) is a transformative concept that bridges the cyber and physical realms, significantly contributing to advancements in smart manufacturing and Industry 4.0. Digital twins are virtual models that accurately reflect physical objects or systems, enabling enhanced analysis and optimization of processes.
>
> The role of data is pivotal in the functionality of digital twins. Data is essential for constructing virtual models and establishing cyber-physical connections. Digital twins offer innovative solutions for complexity management in intelligent manufacturing, thereby facilitating a more autonomous and analytical approach.

**引用来源**: 8篇相关论文，包括:
- "Digital Twin in Industry: State-of-the-Art" (IEEE Transactions, 2019)
- "Digital twin data: methods and key technologies" (Digital Twin, 2021)
- "Digital twin-driven product design framework" (IJPR, 2018)

---

#### ✅ 研究人员查询

**问题**: "Tell me about Professor Arcot Sowmya"

**系统回答**:
> Professor Arcot Sowmya is a prominent academic in the field of Computer Science and Engineering at UNSW, where he serves as the Head of School. He holds a PhD in Computer Science from IIT Bombay, and has significant focus on research areas including **Machine Learning and Computer Vision**. His work encompasses learning object models, feature extraction, segmentation, and recognition, utilizing various methodologies from machine learning and deep learning. Notably, his research has applications in **medical image analysis**, which indicates a strong interdisciplinary approach bridging technology and healthcare.

**数据来源**: 教授的个人主页和研究简介

---

## 三、数据质量分析

### 整体数据质量
| 指标 | 数值 | 说明 |
|------|------|------|
| 研究人员覆盖率 | 100% (649/649) | 所有工程学院staff已录入 |
| 学术发表覆盖率 | 90.3% (586/649) | 有学术发表记录的研究人员 |
| 论文摘要覆盖率 | 34.3% (21,516/62,726) | 包含详细摘要的论文 |
| DOI覆盖率 | 97.8% | 便于文献追踪和引用 |

### 数据结构分布
| 内容类型 | 数量 | 占比 |
|---------|------|------|
| 论文标题 | 63,164 | 52.4% |
| 研究主题/关键词 | 34,528 | 28.7% |
| 论文摘要 | 21,516 | 17.9% |
| 人员基本信息 | 649 | 0.5% |
| 人员传记/简介 | 632 | 0.5% |
| **总计** | **120,489** | **100%** |

### 合作网络数据
- 唯一作者总数: 10,642人
- UNSW研究人员: 649人 (我们采集的目标)
- 外部合作者: ~10,000人 (从论文作者中识别)

---

## 四、当前限制与挑战

### 1. 数据完整性问题 ⚠️ 【优先级: 高】

**问题描述**:
- 目前使用的是**免费的OpenAlex公开数据库**
- 缺少UNSW图书馆订阅的专业数据库访问权限(如Scopus, Web of Science)
- 论文摘要覆盖率仅34.3%，意味着约65%的论文缺少详细摘要

**实际影响**:
- 部分查询可能遗漏重要学术成果
- 对于没有摘要的论文，只能基于标题和关键词检索
- 最新发表的论文(OpenAlex收录滞后)可能缺失

**数据对比**:
- 当前可获取摘要: 21,516篇 / 62,726篇 (34.3%)
- 如有UNSW图书馆权限，预计可提升至: 50,000+篇 / 62,726篇 (80%+)

**建议方案**:
需要申请以下数据库的API访问权限:
- Scopus (Elsevier)
- Web of Science (Clarivate)
- IEEE Xplore (工程领域专业数据库)

**预期收益**:
- 摘要覆盖率提升至80%以上
- 数据更新更及时
- 引用关系更完整

---

### 2. 权限管理功能缺失 ⚠️ 【优先级: 待确认】

**问题描述**:
目前系统没有实现多层级的访问控制和数据分类，缺少以下维度:
- **学院级别**(Faculty level): 如工程学院、理学院
- **学系级别**(School level): 如计算机学院、电气学院
- **研究组级别**(Research group level): 如机器学习组、网络安全组

**实际影响**:
- 所有用户看到的是全部工程学院的数据
- 无法实现针对特定院系或研究组的定制化查询
- 暂未采集组织架构的元数据(研究组归属、项目团队等)

**需要明确**:
1. 这个功能对您的业务需求有多重要?
2. 是否需要在下一阶段开发?
3. 预期的使用场景是什么?(如: 院长只看本学院数据？研究组长查看组内成果?)

---

### 3. 数据维度有限 ⚠️ 【优先级: 中】

**当前系统能回答的问题**:
- ✅ 某个研究领域有哪些研究人员?
- ✅ 某位教授的研究方向是什么?
- ✅ 什么是某个专业术语?
- ✅ 某个主题有哪些相关论文?

**当前系统无法回答的问题**:
- ❌ 某位教授获得了哪些科研经费?金额多少?
- ❌ 哪些研究人员有跨机构合作?合作伙伴是谁?
- ❌ 某个实验室有哪些设备和资源?
- ❌ 某位教授指导了多少研究生?学生毕业去向?
- ❌ 哪些研究成果转化成了专利或产品?

**缺失的数据源**:
| 数据类型 | 潜在价值 | 获取难度 | 数据隐私性 |
|---------|---------|---------|-----------|
| 科研经费(Grants/Funding) | ⭐⭐⭐⭐⭐ | 中-高 | 中 |
| 合作网络(Collaborations) | ⭐⭐⭐⭐ | 低-中 | 低 |
| 实验室设施(Lab Resources) | ⭐⭐⭐ | 中 | 中 |
| 学生培养(PhD Supervision) | ⭐⭐⭐⭐ | 中 | 中 |
| 专利与转化(Patents/Commercialization) | ⭐⭐⭐⭐⭐ | 中 | 低-中 |
| 行业咨询项目(Industry Projects) | ⭐⭐⭐⭐ | 高 | 高 |

**不确定因素**:
1. 哪些数据维度对您的决策最有价值?(建议按优先级排序)
2. 这些数据能否合法合规获取?(需确认数据隐私政策)
3. 某些敏感数据(如经费)是否适合展示?

---

### 4. 合作论文重复数据处理 ✅ 【已自动解决】

**情况说明**:
- 原始JSON文件: 158,223个chunks
- 数据库入库: 120,489个unique chunks
- 自动去重: 37,734个重复chunks (23.8%)

**原因分析**:
当一篇论文有多个UNSW作者时,数据生成阶段会为每个作者都生成该论文的chunks,造成重复。

**举例说明**:
- 论文: "Digital Twin in Manufacturing" (DOI: 10.xxx)
- UNSW合作者: Professor A 和 Dr B (2人)
- 生成结果: 该论文的title/abstract/keywords chunks各生成了2份
- 导入处理: 通过chunk_id自动去重,只保留1份

**数据正确性验证**:
- ✅ Publications: 62,726篇 (正确,每篇论文只记录一次)
- ✅ Chunks: 120,489个 unique chunks (正确,自动去重)
- ✅ 去重机制: 导入脚本通过chunk_id确保唯一性

**结论**: 这是**合作论文的正常现象**,系统已正确处理。当前数据库状态是准确的,无需修复。

---

## 五、下一步计划

### 短期目标 (建议2-3周内完成)

#### 1. 业务需求确认会议
希望与您进行一次深入讨论，明确以下问题:
- ✓ 最关心的数据维度是什么?(经费 > 合作 > 专利?)
- ✓ 是否需要权限分级功能?
- ✓ 系统的主要使用场景和用户群体?
- ✓ 可接受的预算和时间线?

#### 2. 数据库访问权限申请
- 申请UNSW图书馆学术数据库API权限
- 联系IT部门了解申请流程
- 预估所需时间: 2-4周

#### 3. 修复数据导入问题
- 排查为何有23.9%的数据丢失
- 重新导入完整数据
- 预估所需时间: 1周

---

### 中期目标 (建议1-2个月内完成)

#### 1. 扩展数据源
根据您确认的优先级,依次接入:
- **第一优先**: Scopus/Web of Science (提升论文数据质量)
- **第二优先**: 科研经费数据(如果可获取)
- **第三优先**: 合作网络数据(从现有论文作者中分析)

#### 2. 功能增强
- 添加数据可视化(如: 研究趋势图、合作网络图)
- 实现权限管理(如需要)
- 优化搜索结果展示

#### 3. 系统优化
- 提升查询性能(目标<1秒响应)
- 增加缓存机制
- 完善错误处理

---

## 六、需要您的支持

### 1. 数据访问权限申请 【关键】
- **需求**: 协助申请UNSW图书馆学术数据库API访问权限
- **原因**: 这将使摘要覆盖率从34%提升至80%+
- **行动**: 可能需要通过IT部门或图书馆正式流程

### 2. 业务需求澄清 【重要】
- **需求**: 安排一次会议(30-60分钟)深入讨论系统定位
- **目的**: 确保开发方向符合实际业务需求
- **准备**: 我会准备系统演示和功能优先级选项

### 3. 数据使用合规确认 【必要】
- **需求**: 确认各类数据的使用是否符合隐私政策
- **关注点**: 特别是涉及经费、学生信息等敏感数据
- **行动**: 可能需要咨询法务或合规部门

---

## 七、总结

### ✅ 关键成果
- **649名**工程学院研究人员数据已完整录入
- **62,726篇**学术论文可供检索
- **智能搜索功能**已验证可用,能够准确理解自然语言查询
- **MVP系统**已成功运行,核心功能满足预期

### ⚠️ 关键待办
- **数据质量提升**: 需要学术数据库权限(摘要覆盖率34% → 80%)
- **业务需求明确**: 需确认数据维度优先级和权限管理需求
- **技术优化**: 修复数据导入问题(23.9%数据丢失)

### 📊 数据亮点
- 90.3%的研究人员有学术发表记录
- 平均每位研究人员107篇论文
- 近5年产出保持稳定(每年3,000+篇)
- 系统响应速度快(<2秒)

### 💡 建议
本系统目前是一个**功能验证成功的MVP**,已证明技术可行性。下一步的关键是:
1. 获取更好的数据源权限(质的提升)
2. 明确业务需求和优先级(方向确认)
3. 逐步扩展功能(量的增长)

建议采用**迭代开发**的方式,先解决最核心的数据质量问题,再根据实际使用反馈逐步添加新功能。

---

**如需查看系统演示或进一步讨论,请随时联系。**

---

## 附录: 技术细节

### 系统架构
- 数据库: PostgreSQL + pgvector (向量检索)
- 检索算法: BM25 + Vector Search + Reranker
- 语言模型: GPT-4o-mini (答案生成)
- 向量模型: OpenAI text-embedding-3-small

### 查询示例API
```bash
# 查询示例
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is digital twin?", "max_context": 10}'
```

### 性能指标
- 向量维度: 1536维
- 索引类型: HNSW (高性能向量检索)
- 平均查询时间: 1.5-2.0秒
- 并发支持: 可扩展
