import json
import os

def check_progress():
    """检查爬取进度"""

    # 检查输出文件
    output_file = 'engineering_staff_with_profiles.json'
    input_file = 'engineering_staff_full.json'

    # 读取目标数量
    with open(input_file, 'r', encoding='utf-8') as f:
        total_staff = len(json.load(f))

    # 检查当前进度
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            current_data = json.load(f)
            current_count = len(current_data)

            # 统计成功和失败数量
            success_count = sum(1 for r in current_data if 'scrape_error' not in r and r.get('profile_details'))
            error_count = sum(1 for r in current_data if 'scrape_error' in r)

            progress_percent = (current_count / total_staff) * 100

            print(f"=" * 60)
            print(f"爬取进度报告")
            print(f"=" * 60)
            print(f"总数: {total_staff}")
            print(f"已完成: {current_count} ({progress_percent:.1f}%)")
            print(f"成功: {success_count}")
            print(f"失败: {error_count}")
            print(f"剩余: {total_staff - current_count}")
            print(f"=" * 60)

            # 估算剩余时间 (每个profile约2秒)
            remaining = total_staff - current_count
            estimated_seconds = remaining * 2
            estimated_minutes = estimated_seconds / 60
            print(f"预计剩余时间: {estimated_minutes:.1f} 分钟")
            print(f"=" * 60)

            # 显示最近几个爬取的结果
            if current_count > 0:
                print(f"\n最近爬取的教职员工:")
                for i in range(max(0, current_count - 5), current_count):
                    staff = current_data[i]
                    status = "✓" if 'scrape_error' not in staff else "✗"
                    name = staff.get('full_name', 'Unknown')
                    print(f"  {status} {name}")
    else:
        print("输出文件尚未创建,爬虫可能刚开始运行...")

    # 显示日志尾部
    print(f"\n最新日志:")
    print("-" * 60)
    os.system("tail -5 scraper.log")

if __name__ == '__main__':
    check_progress()
