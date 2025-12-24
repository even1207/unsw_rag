import json

# 读取结果文件
with open('engineering_staff_with_profiles.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 70)
print("爬取结果统计分析")
print("=" * 70)

# 基本统计
total_count = len(data)
print(f"\n总教职员工数: {total_count}")

# 成功/失败统计
success_count = sum(1 for r in data if 'scrape_error' not in r and r.get('profile_details'))
error_count = sum(1 for r in data if 'scrape_error' in r)
no_url_count = sum(1 for r in data if not r.get('profile_url'))

print(f"成功爬取: {success_count}")
print(f"爬取失败: {error_count}")
print(f"无URL: {no_url_count}")

# 出版物统计
has_publications = 0
pub_categories = {}

for staff in data:
    profile_details = staff.get('profile_details', {})
    publications = profile_details.get('publications', {})

    if publications:
        has_publications += 1
        for category in publications.keys():
            pub_categories[category] = pub_categories.get(category, 0) + 1

print(f"\n有出版物信息的教职员工: {has_publications} ({has_publications/total_count*100:.1f}%)")

print(f"\n出版物类别统计:")
for category, count in sorted(pub_categories.items(), key=lambda x: x[1], reverse=True):
    print(f"  {category}: {count}人")

# 详细信息字段统计
field_counts = {}
for staff in data:
    profile_details = staff.get('profile_details', {})
    for field in profile_details.keys():
        if field != 'publications':
            field_counts[field] = field_counts.get(field, 0) + 1

print(f"\n详细信息字段覆盖率:")
for field, count in sorted(field_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  {field}: {count}人 ({count/total_count*100:.1f}%)")

# 检查几个示例
print(f"\n" + "=" * 70)
print("示例数据预览 (前3位教职员工):")
print("=" * 70)

for i in range(min(3, len(data))):
    staff = data[i]
    print(f"\n{i+1}. {staff.get('full_name', 'Unknown')}")
    print(f"   URL: {staff.get('profile_url', 'N/A')}")

    profile_details = staff.get('profile_details', {})
    print(f"   职位: {profile_details.get('position', 'N/A')}")
    print(f"   学院: {profile_details.get('faculty', 'N/A')}")
    print(f"   邮箱: {profile_details.get('email', 'N/A')}")

    biography = profile_details.get('biography', '')
    if biography:
        print(f"   传记: {biography[:100]}..." if len(biography) > 100 else f"   传记: {biography}")

    publications = profile_details.get('publications', {})
    if publications:
        print(f"   出版物类别: {', '.join(publications.keys())}")
        # 统计总出版物数量
        total_pubs = sum(len(str(v).split('|')) for v in publications.values() if v)
        print(f"   出版物数量: ~{total_pubs}")

print("\n" + "=" * 70)
