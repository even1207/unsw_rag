import requests
from bs4 import BeautifulSoup

url = "https://www.unsw.edu.au/staff/mr-ademir-abdala-prata-junior"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

response = requests.get(url, headers=headers, timeout=30)
soup = BeautifulSoup(response.content, 'html.parser')

# 保存HTML到文件以便分析
with open('page_source.html', 'w', encoding='utf-8') as f:
    f.write(soup.prettify())

print("HTML已保存到 page_source.html")

# 查找所有有class属性的div
print("\n所有带class的div:")
print("="*60)
divs_with_class = soup.find_all('div', class_=True)
unique_classes = set()
for div in divs_with_class:
    classes = div.get('class', [])
    for cls in classes:
        unique_classes.add(cls)

for cls in sorted(unique_classes)[:50]:  # 只显示前50个
    print(f"  - {cls}")

# 查找所有section
print("\n所有section标签:")
print("="*60)
sections = soup.find_all('section')
for section in sections[:10]:
    section_id = section.get('id', 'no-id')
    section_class = section.get('class', ['no-class'])
    print(f"  ID: {section_id}, Class: {section_class}")
    # 显示section的前100个字符
    text = section.get_text(strip=True)[:100]
    print(f"    Text: {text}...\n")

# 查找所有h2, h3 标题
print("\n所有标题 (h2, h3):")
print("="*60)
for heading in soup.find_all(['h2', 'h3'])[:20]:
    print(f"  {heading.name}: {heading.get_text(strip=True)}")
