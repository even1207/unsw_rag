"""Test the full workflow with 2 staff members."""
import json
from ingestor.staff_fetcher import fetch_engineering_staff
from ingestor.staff_profile import parse_staff_profile

print("Step 1: 获取前2位员工的基本信息...")
staff_list = fetch_engineering_staff(page_size=2, delay_seconds=0)
print(f"✓ 获取了 {len(staff_list)} 位员工\n")

print("Step 2: 获取详细的 profile 信息...")
for i, staff in enumerate(staff_list, 1):
    url = staff.get('profile_url')
    name = staff.get('full_name')
    print(f"\n[{i}/{len(staff_list)}] 正在解析: {name}")
    print(f"  URL: {url}")

    try:
        profile_data = parse_staff_profile(url)
        staff.update(profile_data)

        bio = profile_data.get('biography') or ''
        research = profile_data.get('research_text') or ''
        print(f"  ✓ Biography: {len(bio)} 字符")
        print(f"  ✓ Research: {len(research)} 字符")

        if bio:
            print(f"  Bio preview: {bio[:100]}...")
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        import traceback
        traceback.print_exc()

print(f"\n" + "=" * 60)
print("Step 3: 完整数据示例（第1位员工）:")
print("=" * 60)
print(json.dumps(staff_list[0], ensure_ascii=False, indent=2))

print(f"\n✓ 测试完成！成功获取了 {len(staff_list)} 位员工的完整 profile 信息")
