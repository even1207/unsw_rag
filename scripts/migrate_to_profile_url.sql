-- 数据库迁移: 从 staff.email 主键改为 staff.profile_url 主键
-- 这个迁移会保留现有数据

BEGIN;

-- 1. 删除依赖 staff.email 的外键约束
ALTER TABLE chunks DROP CONSTRAINT IF EXISTS chunks_staff_email_fkey;
ALTER TABLE publications DROP CONSTRAINT IF EXISTS publications_staff_email_fkey;

-- 2. 修改 staff 表
-- 2.1 删除旧的主键
ALTER TABLE staff DROP CONSTRAINT IF EXISTS staff_pkey;

-- 2.2 将 profile_url 设置为 NOT NULL（如果有 NULL 值需要先处理）
UPDATE staff SET profile_url = 'https://research.unsw.edu.au/people/' || email
WHERE profile_url IS NULL;

ALTER TABLE staff ALTER COLUMN profile_url SET NOT NULL;

-- 2.3 创建新的主键
ALTER TABLE staff ADD PRIMARY KEY (profile_url);

-- 2.4 为 email 创建唯一索引（如果需要的话）
CREATE INDEX IF NOT EXISTS ix_staff_email ON staff(email);

-- 3. 修改 chunks 表
-- 3.1 添加新列 staff_profile_url
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS staff_profile_url VARCHAR(512);

-- 3.2 填充新列数据（从 staff_email 映射到 profile_url）
UPDATE chunks
SET staff_profile_url = staff.profile_url
FROM staff
WHERE chunks.staff_email = staff.email;

-- 3.3 删除旧列
ALTER TABLE chunks DROP COLUMN IF EXISTS staff_email;

-- 3.4 创建新的外键约束
ALTER TABLE chunks ADD CONSTRAINT chunks_staff_profile_url_fkey
    FOREIGN KEY (staff_profile_url) REFERENCES staff(profile_url);

-- 3.5 创建索引
CREATE INDEX IF NOT EXISTS ix_chunks_staff_profile_url ON chunks(staff_profile_url);

-- 4. 修改 publications 表
-- 4.1 添加新列 staff_profile_url
ALTER TABLE publications ADD COLUMN IF NOT EXISTS staff_profile_url VARCHAR(512);

-- 4.2 填充新列数据
UPDATE publications
SET staff_profile_url = staff.profile_url
FROM staff
WHERE publications.staff_email = staff.email;

-- 4.3 删除旧列
ALTER TABLE publications DROP COLUMN IF EXISTS staff_email;

-- 4.4 创建新的外键约束
ALTER TABLE publications ADD CONSTRAINT publications_staff_profile_url_fkey
    FOREIGN KEY (staff_profile_url) REFERENCES staff(profile_url);

-- 4.5 创建索引
CREATE INDEX IF NOT EXISTS ix_publications_staff_profile_url ON publications(staff_profile_url);

COMMIT;

-- 验证迁移结果
\d staff
\d chunks
\d publications
