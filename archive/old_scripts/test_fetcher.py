"""Test the staff fetcher function."""
import json
import sys

# 添加更详细的日志
print("导入模块...", file=sys.stderr)
from ingestor.staff_fetcher import fetch_engineering_staff

print("开始获取员工数据（仅5条用于测试）...", file=sys.stderr)
try:
    staff = fetch_engineering_staff(page_size=5)
    print(f"✓ 成功获取 {len(staff)} 位员工", file=sys.stderr)

    if staff:
        print(f"\n第一位员工完整信息:")
        print(json.dumps(staff[0], ensure_ascii=False, indent=2))

        print(f"\n所有 {len(staff)} 位员工:")
        for i, s in enumerate(staff, 1):
            print(f"{i}. {s.get('full_name')} - {s.get('role')} - {s.get('email')}")
    else:
        print("⚠ 未获取到任何员工数据", file=sys.stderr)
except Exception as e:
    print(f"✗ 错误: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
