import requests
from bs4 import BeautifulSoup

response = requests.get('https://jobs.au.int/', timeout=10)
soup = BeautifulSoup(response.content, 'html.parser')

# Look for common job listing patterns
print("Looking for job-related elements...")
print("\n1. Looking for <a> tags with various patterns:")
for pattern in ['job', 'position', 'career', 'posting']:
    links = soup.find_all('a', href=lambda x: x and pattern.lower() in str(x).lower())
    print(f"   Found {len(links)} links containing '{pattern}'")
    if links and len(links) > 0:
        print(f"   First link: {links[0].get('href')}")

print("\n2. Looking for common job listing classes/ids:")
for selector in ['job', 'position', 'vacancy', 'opening', 'listing']:
    elements = soup.find_all(class_=lambda x: x and selector in str(x).lower())
    print(f"   Found {len(elements)} elements with class containing '{selector}'")

print("\n3. Looking at main containers:")
main = soup.find('main')
if main:
    print(f"   Found <main> tag")
    print(f"   Main content length: {len(str(main))}")
    
content = soup.find('div', class_=lambda x: x and 'content' in str(x).lower())
if content:
    print(f"   Found content div")

# Try to find actual job listings
print("\n4. Looking for job title patterns in text:")
text = soup.get_text()
if 'job' in text.lower():
    print("   'job' keyword found in page")
if 'position' in text.lower():
    print("   'position' keyword found in page")

# Get all links and show first 10
print("\n5. First 10 links on the page:")
all_links = soup.find_all('a', limit=10)
for i, link in enumerate(all_links, 1):
    href = link.get('href', 'No href')
    text = link.get_text().strip()[:50]
    print(f"   {i}. {href[:60]} -> {text}")
