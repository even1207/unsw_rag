"""Fast test without delays."""
import json
from ingestor.staff_fetcher import fetch_engineering_staff

print("开始获取...")
# 设置 delay 为 0 来加快测试
staff = fetch_engineering_staff(page_size=3, delay_seconds=0)
print(f"✓ 成功获取 {len(staff)} 位员工\n")

if staff:
    for i, s in enumerate(staff, 1):
        print(f"{i}. {s.get('full_name')} - {s.get('role')}")
        print(f"   邮箱: {s.get('email')}")
        print(f"   学院: {s.get('faculty')}, 学校: {s.get('school')}")
        print(f"   URL: {s.get('profile_url')}\n")
