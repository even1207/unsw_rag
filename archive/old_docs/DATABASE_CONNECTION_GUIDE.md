# 数据库连接指南

## 方法1：使用 psql 命令行工具

### 基本连接命令

```bash
# 最简单的方式 - 连接到 unsw_rag 数据库
psql -d unsw_rag

# 或者指定完整参数
psql -U z5241339 -d unsw_rag -h localhost -p 5432
```

### 常用 psql 命令

连接成功后，你会看到提示符 `unsw_rag=#`，可以使用以下命令：

```sql
-- 查看所有表
\dt

-- 查看表结构
\d staff_profiles

-- 查看所有数据库
\l

-- 查看当前连接信息
\conninfo

-- 退出
\q

-- 执行 SQL 查询
SELECT COUNT(*) FROM staff_profiles;

-- 查看前10条记录
SELECT full_name, role, school FROM staff_profiles LIMIT 10;

-- 搜索特定内容
SELECT full_name, email, school
FROM staff_profiles
WHERE full_name ILIKE '%zhang%'
OR biography ILIKE '%machine learning%';
```

### 直接执行 SQL 命令（不进入交互模式）

```bash
# 查询总数
psql -d unsw_rag -c "SELECT COUNT(*) FROM staff_profiles;"

# 导出数据为 CSV
psql -d unsw_rag -c "COPY staff_profiles TO '/tmp/staff_export.csv' CSV HEADER;"

# 查看表结构
psql -d unsw_rag -c "\d staff_profiles"
```

## 方法2：使用 DBeaver 连接

DBeaver 是一个功能强大的数据库管理工具，支持可视化操作。

### 步骤1：下载安装 DBeaver

如果还没有安装，下载 DBeaver Community Edition（免费）：
```bash
# macOS 使用 Homebrew 安装
brew install --cask dbeaver-community

# 或者从官网下载
# https://dbeaver.io/download/
```

### 步骤2：在 DBeaver 中创建连接

1. **打开 DBeaver**

2. **创建新连接**
   - 点击左上角 "新建数据库连接" 按钮（或 File → New → Database Connection）
   - 选择 **PostgreSQL**
   - 点击 "下一步"

3. **填写连接信息**

   **主要设置（Main）标签页：**
   ```
   Host: localhost
   Port: 5432
   Database: unsw_rag
   Username: z5241339
   Password: （留空 - 不需要密码）
   ```

   完整示例：
   ```
   ┌─────────────────────────────────────┐
   │ Connection Settings                  │
   ├─────────────────────────────────────┤
   │ Host:       localhost               │
   │ Port:       5432                    │
   │ Database:   unsw_rag                │
   │ Username:   z5241339                │
   │ Password:   [留空]                  │
   │                                     │
   │ ☑ Show all databases                │
   │ ☐ Read only connection              │
   └─────────────────────────────────────┘
   ```

4. **测试连接**
   - 点击 "Test Connection" 按钮
   - 如果是第一次连接，DBeaver 会提示下载 PostgreSQL 驱动
   - 点击 "下载" 等待驱动下载完成
   - 测试成功会显示 "Connected"

5. **完成连接**
   - 点击 "完成" 或 "Finish"
   - 连接会出现在左侧导航栏中

### 步骤3：浏览数据

连接成功后，在 DBeaver 左侧导航栏：

```
unsw_rag
  └─ Databases
      └─ unsw_rag
          └─ Schemas
              └─ public
                  └─ Tables
                      └─ staff_profiles  ← 右键点击查看数据
```

**常用操作：**
- **查看数据**：右键 staff_profiles → "查看数据" (View Data)
- **查看结构**：右键 staff_profiles → "属性" (Properties) → "列" (Columns)
- **执行 SQL**：点击上方 "SQL 编辑器" 按钮
- **导出数据**：右键表 → "导出数据" (Export Data)
- **查询数据**：双击表名自动打开数据查看器

### DBeaver 实用 SQL 查询示例

在 SQL 编辑器中可以运行：

```sql
-- 1. 查看所有 Professor
SELECT full_name, school, email
FROM staff_profiles
WHERE role LIKE '%Professor%'
ORDER BY full_name;

-- 2. 按学院统计人数
SELECT school, COUNT(*) as staff_count
FROM staff_profiles
GROUP BY school
ORDER BY staff_count DESC;

-- 3. 搜索研究领域包含 AI 的员工
SELECT full_name, role, research_text
FROM staff_profiles
WHERE research_text ILIKE '%artificial intelligence%'
   OR research_text ILIKE '%machine learning%'
   OR biography ILIKE '%AI%';

-- 4. 查找特定学院的高级讲师
SELECT full_name, email, profile_url
FROM staff_profiles
WHERE school = 'Computer Science and Engineering'
  AND role LIKE '%Lecturer%';

-- 5. 全文搜索（在所有文本字段中搜索）
SELECT full_name, role, school, email
FROM staff_profiles
WHERE full_name ILIKE '%chen%'
   OR biography ILIKE '%robotics%'
   OR research_text ILIKE '%robotics%';
```

## 方法3：使用 Python 连接

在你的 Python 代码中：

```python
from database.db import get_connection
from database.schema import StaffProfile

# 获取数据库会话
session = get_connection()

# 查询示例
# 1. 查询所有记录
all_staff = session.query(StaffProfile).all()
print(f"Total staff: {len(all_staff)}")

# 2. 条件查询
professors = session.query(StaffProfile).filter(
    StaffProfile.role.like('%Professor%')
).all()

# 3. 搜索特定学院
cse_staff = session.query(StaffProfile).filter(
    StaffProfile.school == 'Computer Science and Engineering'
).all()

# 4. 复杂查询
from sqlalchemy import or_

ai_researchers = session.query(StaffProfile).filter(
    or_(
        StaffProfile.research_text.ilike('%artificial intelligence%'),
        StaffProfile.research_text.ilike('%machine learning%'),
        StaffProfile.biography.ilike('%AI%')
    )
).all()

# 5. 按名字搜索
staff = session.query(StaffProfile).filter(
    StaffProfile.full_name.ilike('%zhang%')
).first()

if staff:
    print(f"Found: {staff.full_name}")
    print(f"Email: {staff.email}")
    print(f"School: {staff.school}")

# 关闭连接
session.close()
```

## 方法4：其他数据库工具

除了 DBeaver，还可以使用：

### pgAdmin 4（PostgreSQL 官方工具）
```bash
# 安装
brew install --cask pgadmin4

# 连接信息同 DBeaver
Host: localhost
Port: 5432
Database: unsw_rag
Username: z5241339
Password: (空)
```

### TablePlus（简洁好用）
```bash
# 安装
brew install --cask tableplus

# 创建连接
# 选择 PostgreSQL
# 填写相同的连接信息
```

### Postico（Mac 专用，界面友好）
```bash
# 安装
brew install --cask postico

# 连接配置同上
```

## 快速参考卡片

### 连接信息摘要
```
╔═══════════════════════════════════════╗
║   PostgreSQL 连接信息                  ║
╠═══════════════════════════════════════╣
║ 类型:    PostgreSQL                   ║
║ 主机:    localhost                    ║
║ 端口:    5432                         ║
║ 数据库:  unsw_rag                     ║
║ 用户名:  z5241339                     ║
║ 密码:    (无需密码)                    ║
║                                       ║
║ 连接字符串:                            ║
║ postgresql://z5241339@localhost:5432/unsw_rag
╚═══════════════════════════════════════╝
```

### 快速命令参考
```bash
# 连接数据库
psql -d unsw_rag

# 查看记录总数
psql -d unsw_rag -c "SELECT COUNT(*) FROM staff_profiles;"

# 查看表结构
psql -d unsw_rag -c "\d staff_profiles"

# 搜索特定员工
psql -d unsw_rag -c "SELECT * FROM staff_profiles WHERE full_name ILIKE '%zhang%';"
```

## 故障排除

### 问题1：psql: command not found
```bash
# 将 PostgreSQL 添加到 PATH
echo 'export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### 问题2：DBeaver 连接失败
- 确保 PostgreSQL 正在运行：`brew services list`
- 启动 PostgreSQL：`brew services start postgresql@15`
- 检查端口是否被占用：`lsof -i :5432`

### 问题3：权限被拒绝
```bash
# 检查当前用户
whoami

# 确保使用正确的用户名
psql -U z5241339 -d unsw_rag
```

### 问题4：数据库不存在
```bash
# 创建数据库
createdb unsw_rag

# 或使用 psql
psql -d postgres -c "CREATE DATABASE unsw_rag;"
```
