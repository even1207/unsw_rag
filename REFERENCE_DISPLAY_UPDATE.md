# 引用来源显示改进说明

## 问题描述

之前在回答中看到的数字（如 "1234"）是文档引用编号，但没有显示具体的引用来源信息。

### 示例问题：
```
回答文本中提到：
- "Document 3"
- "Document 10"
- "Document 2"

但答案末尾只显示：1234
```

## 问题原因

1. **后端已经生成了完整的 `sources` 数据**，包含：
   - 文献标题、作者、年份、DOI链接
   - 研究人员姓名、学院、个人主页链接

2. **前端没有显示这些 `sources`**：
   - API 返回了 `sources` 字段
   - 但前端代码中没有渲染这个字段
   - 只显示了检索过程中的文档列表，而非最终引用

## 解决方案

### 1. 修改前端代码以接收和显示 sources

**文件：** [client/src/App.jsx](client/src/App.jsx)

**改动：**
- 在处理 `done` 事件时保存 `sources` 数据
- 添加 "References" 区域显示引用来源
- 支持两种类型的来源：
  - **学术文献** (publication)：显示标题、作者、年份、出版地、DOI
  - **研究人员** (person)：显示姓名、学院、个人主页

### 2. 添加样式使引用易于阅读

**文件：** [client/src/App.css](client/src/App.css)

**新增样式：**
- `.sources-list`：引用列表容器
- `.source-item`：单个引用项
- `.source-number`：引用编号 [1], [2] 等
- `.source-title`：可点击的标题链接
- `.source-meta`：作者、年份等元数据

### 3. 显示格式

现在点击 "Show Details" 后，会看到三个部分：

#### **References** (新增！)
显示答案中实际引用的来源，格式如：

```
[1] Large-Scale Similarity-Based Time Series Mining
    Authors: Gustavo Batista, ...
    Year: 2018
    DOI: 10.1234/example
    🔗 点击标题可跳转到论文页面

[2] Dr. Hao Xue - Researcher Profile
    School: School of Computer Science and Engineering
    🔗 View Profile
```

#### **Knowledge Graph Sources**
从知识图谱获取的额外上下文

#### **Top Documents Retrieved**
搜索引擎检索到的原始文档列表

## 使用说明

### 启动系统

1. **启动后端 API**：
```bash
python3 api_server.py
```

2. **启动前端**：
```bash
cd client
npm run dev
```

3. **测试查询**：
```
问题：Who is doing research on time series at UNSW?
```

4. **查看引用**：
   - 等待回答生成完成
   - 点击 "Show Details"
   - 在 "References" 区域查看完整引用信息
   - 点击蓝色标题链接跳转到原文

## 技术细节

### 数据流

```
用户提问
  ↓
搜索引擎检索相关文档
  ↓
LLM 生成回答（引用 Document 1, 2, 3...）
  ↓
后端提取实际使用的文档，生成 sources 列表
  ↓
API 返回: { answer, sources, metadata }
  ↓
前端显示回答 + 可展开的 References
```

### Sources 数据结构

**学术文献：**
```javascript
{
  type: "publication",
  title: "论文标题",
  authors: ["作者1", "作者2", "作者3"],
  year: 2018,
  venue: "会议/期刊名称",
  doi: "10.1234/example",
  url: "https://doi.org/10.1234/example"
}
```

**研究人员：**
```javascript
{
  type: "person",
  name: "Dr. John Doe",
  school: "School of Computer Science",
  profile_url: "https://..."
}
```

## 优势

✅ **清晰的引用编号**：[1], [2], [3] 对应答案中的引用
✅ **可点击的链接**：直接跳转到论文或个人主页
✅ **完整的元数据**：作者、年份、出版地等信息
✅ **分类显示**：区分学术文献和研究人员资料
✅ **美观的界面**：使用卡片式布局，易于浏览

## 下一步改进建议

1. **在答案正文中添加上标引用**：如 "...time series analysis[1,3]..."
2. **支持引用悬浮预览**：鼠标悬停显示引用详情
3. **导出引用为 BibTeX**：方便学术写作
4. **引用去重**：同一来源在答案中多次引用时只显示一次
