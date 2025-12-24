"""
生成缺失的 staff chunks

处理那些没有 publications 的 staff，为他们生成 person_basic 和 person_biography chunks
"""
import json
import sys
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def create_staff_chunks(staff):
    """为单个 staff 创建 chunks（不包括 publications）"""
    chunks = []

    profile_url = staff['profile_url']
    staff_id = profile_url.split('/')[-1] if profile_url else hashlib.md5(staff['full_name'].encode()).hexdigest()[:8]

    # Person basic chunk
    person_basic = {
        "chunk_id": f"person_basic_{staff_id}",
        "chunk_type": "person_basic",
        "content": f"{staff['full_name']}\n"
                   f"Position: {staff.get('role', 'N/A')}\n"
                   f"School: {staff.get('school', 'N/A')}\n"
                   f"Faculty: {staff.get('faculty', 'N/A')}",
        "metadata": {
            "person_name": staff['full_name'],
            "person_email": staff.get('email'),
            "person_profile_url": profile_url,
            "role": staff.get('role'),
            "school": staff.get('school'),
            "faculty": staff.get('faculty'),
            "profile_url": profile_url,
        }
    }
    chunks.append(person_basic)

    # Person biography chunk
    biography = staff.get('biography') or staff.get('profile_details', {}).get('biography')
    research = staff.get('research_text') or staff.get('profile_details', {}).get('research_interests', '')

    if biography:
        person_bio = {
            "chunk_id": f"person_bio_{staff_id}",
            "chunk_type": "person_biography",
            "content": f"{staff['full_name']} - Research Profile\n\n"
                       f"{biography}\n\n"
                       f"Research Areas: {research}",
            "metadata": {
                "person_name": staff['full_name'],
                "person_email": staff.get('email'),
                "person_profile_url": profile_url,
                "school": staff.get('school'),
                "profile_url": profile_url,
            }
        }
        chunks.append(person_bio)

    return chunks


def main():
    print("生成缺失的 staff chunks")
    print("=" * 80)

    # 读取现有 chunks
    chunks_file = PROJECT_ROOT / "data/processed/rag_chunks.json"
    with open(chunks_file, 'r') as f:
        existing_chunks = json.load(f)

    print(f"现有 chunks 数量: {len(existing_chunks)}")

    # 获取已处理的 profile_urls
    existing_urls = set()
    for chunk in existing_chunks:
        metadata = chunk.get('metadata', {})
        profile_url = metadata.get('person_profile_url') or metadata.get('profile_url')
        if profile_url:
            existing_urls.add(profile_url)

    print(f"已有 chunks 的 staff: {len(existing_urls)}")

    # 读取所有 staff
    staff_file = PROJECT_ROOT / "data/processed/staff_with_profiles.json"
    with open(staff_file, 'r') as f:
        all_staff = json.load(f)

    print(f"总 staff 数量: {len(all_staff)}")

    # 找出没有 chunks 的 staff
    missing_staff = [s for s in all_staff if s.get('profile_url') not in existing_urls]

    print(f"缺少 chunks 的 staff: {len(missing_staff)}")

    if not missing_staff:
        print("\n✓ 所有 staff 都已有 chunks!")
        return

    print(f"\n处理缺失的 staff:")
    new_chunks = []

    for i, staff in enumerate(missing_staff, 1):
        print(f"  [{i}/{len(missing_staff)}] {staff.get('full_name')}")

        chunks = create_staff_chunks(staff)
        new_chunks.extend(chunks)

        print(f"    生成了 {len(chunks)} 个 chunks")

    # 合并新旧 chunks
    all_chunks = existing_chunks + new_chunks

    print(f"\n总 chunks 数量: {len(all_chunks)}")
    print(f"新增 chunks 数量: {len(new_chunks)}")

    # 保存
    with open(chunks_file, 'w') as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print(f"\n✓ 已保存到: {chunks_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
