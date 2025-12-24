"""Debug script to test API connection."""
import requests
import json

BASE_URL = "https://unsw-search.funnelback.squiz.cloud/s/search.html"
params = {
    "form": "json",
    "collection": "unsw~unsw-search",
    "profile": "profiles",
    "query": "!padrenull",
    "sort": "metastaffLastName",
    "f.Faculty|staffFaculty": "Engineering",
    "gscope1": "engineeringStaff",
    "meta_staffRole_not": "casual adjunct visiting honorary",
    "start_rank": 1,
    "num_ranks": 3
}

print("正在请求 API...")
try:
    resp = requests.get(
        BASE_URL,
        params=params,
        timeout=10,
        headers={"User-Agent": "UNSW-AI-RAG-Research-Bot/0.1"}
    )
    print(f"✓ 响应状态码: {resp.status_code}")

    data = resp.json()
    print(f"✓ JSON 解析成功")

    results = data.get("response", {}).get("resultPacket", {}).get("results", [])
    print(f"✓ 获取到 {len(results)} 条结果")

    if results:
        first = results[0]
        print(f"\n第一条记录:")
        print(f"  姓名: {first.get('title')}")
        print(f"  URL: {first.get('liveUrl')}")
        meta = first.get('metaData', {})
        print(f"  职位: {meta.get('staffRole')}")
        print(f"  学院: {meta.get('staffFaculty')}")
        print(f"  邮箱: {meta.get('emailAddress')}")

except Exception as e:
    print(f"✗ 错误: {e}")
    import traceback
    traceback.print_exc()
