# PostgreSQL 数据库设置指南

本文档说明如何将爬取的员工数据导入到 PostgreSQL 数据库。

## 前置条件

### 1. 安装 PostgreSQL
如果还没有安装 PostgreSQL，请先安装：

**macOS (使用 Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### 2. 创建数据库
```bash
# 登录 PostgreSQL
psql postgres

# 创建数据库
CREATE DATABASE unsw_rag;

# 创建用户（可选）
CREATE USER unsw_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE unsw_rag TO unsw_user;

# 退出
\q
```

### 3. 安装 Python 依赖
```bash
pip3 install -r requirements.txt
```

## 配置数据库连接

编辑 [config/settings.py](config/settings.py) 或者使用环境变量设置数据库连接字符串：

```bash
# 使用环境变量
export POSTGRES_DSN="postgresql://username:password@localhost:5432/unsw_rag"

# 或者在 .env 文件中设置
echo 'POSTGRES_DSN=postgresql://username:password@localhost:5432/unsw_rag' > .env
```

**连接字符串格式：**
```
postgresql://[用户名]:[密码]@[主机]:[端口]/[数据库名]
```

**示例：**
- 本地默认: `postgresql://postgres:@localhost:5432/unsw_rag`
- 带密码: `postgresql://unsw_user:mypassword@localhost:5432/unsw_rag`
- 远程服务器: `postgresql://user:pass@192.168.1.100:5432/unsw_rag`

## 数据库表结构

系统会自动创建以下表结构：

### staff_profiles 表

| 字段名 | 类型 | 说明 |
|--------|------|------|
| email | VARCHAR(255) | 主键 - 员工邮箱 |
| first_name | VARCHAR(100) | 名字 |
| last_name | VARCHAR(100) | 姓氏 |
| full_name | VARCHAR(255) | 全名（带索引） |
| role | VARCHAR(255) | 职位 |
| faculty | VARCHAR(255) | 学院（带索引） |
| school | VARCHAR(255) | 学校/系（带索引） |
| phone | VARCHAR(50) | 电话 |
| profile_url | VARCHAR(512) | 个人主页 URL |
| photo_url | VARCHAR(512) | 照片 URL |
| summary | TEXT | 简介 |
| biography | TEXT | 详细传记 |
| research_text | TEXT | 研究领域文本 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

## 导入数据到数据库

### 方法1：使用导入脚本（推荐）

```bash
# 导入 engineering_staff_full.json（默认）
PYTHONPATH=/Users/z5241339/Documents/unsw_ai_rag python3 scripts/import_to_database.py

# 或指定自定义 JSON 文件
PYTHONPATH=/Users/z5241339/Documents/unsw_ai_rag python3 scripts/import_to_database.py path/to/your/data.json
```

### 方法2：使用 Python 代码

```python
import json
from database.db import init_database, upsert_staff

# 初始化数据库（创建表）
init_database()

# 加载 JSON 数据
with open('engineering_staff_full.json', 'r') as f:
    staff_data = json.load(f)

# 导入数据
result = upsert_staff(staff_data)
print(f"Imported {result['total']} records")
```

## 查询数据

### 使用 psql 命令行

```bash
# 连接数据库
psql -d unsw_rag

# 查看表结构
\d staff_profiles

# 查询总数
SELECT COUNT(*) FROM staff_profiles;

# 查询特定学院
SELECT full_name, role, school
FROM staff_profiles
WHERE faculty = 'Engineering'
LIMIT 10;

# 搜索名字
SELECT full_name, email, role
FROM staff_profiles
WHERE full_name ILIKE '%abdoli%';

# 按学校统计
SELECT school, COUNT(*) as count
FROM staff_profiles
GROUP BY school
ORDER BY count DESC;
```

### 使用 Python

```python
from database.db import get_connection
from database.schema import StaffProfile

# 获取数据库连接
session = get_connection()

# 查询所有员工
all_staff = session.query(StaffProfile).all()

# 按条件查询
professors = session.query(StaffProfile).filter(
    StaffProfile.role.like('%Professor%')
).all()

# 搜索特定学校
mech_eng = session.query(StaffProfile).filter(
    StaffProfile.school == 'Mechanical and Manufacturing Engineering'
).all()

# 关闭连接
session.close()
```

## 数据更新

导入脚本使用 UPSERT 操作（INSERT ... ON CONFLICT DO UPDATE），这意味着：
- 如果 email 已存在，会更新该记录
- 如果 email 不存在，会插入新记录

因此可以安全地重复运行导入脚本来更新数据。

## 故障排除

### 问题1：无法连接数据库
```
错误: could not connect to server
```

**解决方案：**
- 检查 PostgreSQL 是否正在运行：`brew services list` 或 `sudo systemctl status postgresql`
- 检查连接字符串是否正确
- 确保防火墙允许连接

### 问题2：权限错误
```
错误: permission denied for database
```

**解决方案：**
```sql
GRANT ALL PRIVILEGES ON DATABASE unsw_rag TO your_username;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_username;
```

### 问题3：依赖缺失
```
错误: No module named 'psycopg2'
```

**解决方案：**
```bash
pip3 install -r requirements.txt
```

## 性能优化

当前实现已包含以下索引：
- `full_name` - 用于按名字搜索
- `faculty` - 用于按学院筛选
- `school` - 用于按系筛选

如需添加更多索引，可以执行：
```sql
CREATE INDEX idx_role ON staff_profiles(role);
CREATE INDEX idx_email_gin ON staff_profiles USING gin(to_tsvector('english', email));
```

## 下一步

1. **全文搜索**: 可以使用 PostgreSQL 的全文搜索功能搜索 biography 和 research_text
2. **向量搜索**: 结合 pgvector 扩展存储文本嵌入向量，实现语义搜索
3. **API 集成**: 在 FastAPI 中添加数据库查询端点

查看 [PROJECT_STATUS.md](PROJECT_STATUS.md) 了解项目整体状态。
