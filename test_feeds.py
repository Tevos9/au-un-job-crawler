import feedparser
import requests
from bs4 import BeautifulSoup

# Test UN RSS feed
print("=" * 60)
print("Testing UN RSS Feed")
print("=" * 60)
try:
    feed = feedparser.parse('https://careers.un.org/jobfeed?isPage=true&language=en')
    print(f"Feed bozo: {feed.bozo}")
    if feed.bozo:
        print(f"Bozo exception: {feed.bozo_exception}")
    print(f"Number of entries: {len(feed.entries)}")
    if feed.entries:
        print(f"First entry: {feed.entries[0].get('title', 'No title')}")
except Exception as e:
    print(f"Error: {e}")

# Try alternative UN RSS
print("\n" + "=" * 60)
print("Testing Alternative UN RSS URLs")
print("=" * 60)

alternatives = [
    "https://careers.un.org/jobfeed",
    "https://jobs.un.org/jobfeed",
]

for url in alternatives:
    try:
        print(f"\nTrying: {url}")
        feed = feedparser.parse(url)
        print(f"  Bozo: {feed.bozo}, Entries: {len(feed.entries)}")
    except Exception as e:
        print(f"  Error: {e}")

# Test AU Jobs website
print("\n" + "=" * 60)
print("Testing AU Jobs Website")
print("=" * 60)
try:
    response = requests.get('https://jobs.au.int/', timeout=10)
    print(f"Status code: {response.status_code}")
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Look for job links
    job_links = soup.find_all('a', href=lambda x: x and '/job/' in x)
    print(f"Found {len(job_links)} job links")
    if job_links:
        print(f"First link: {job_links[0].get('href')}")
        print(f"First link text: {job_links[0].get_text()}")
except Exception as e:
    print(f"Error: {e}")
