"""Quick test script to verify staff fetcher."""
import json
from ingestor.staff_fetcher import fetch_engineering_staff

print("开始获取员工数据...")
staff = fetch_engineering_staff(page_size=5)
print(f"\n✓ 成功获取 {len(staff)} 位员工")

if staff:
    print("\n第一位员工完整信息:")
    print(json.dumps(staff[0], ensure_ascii=False, indent=2))
    print("\n所有员工姓名列表:")
    for s in staff:
        print(f"  - {s.get('full_name')} ({s.get('role')})")
else:
    print("⚠ 未获取到任何员工数据")
