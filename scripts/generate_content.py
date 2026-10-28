
import os
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from html import unescape

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = "gemini-3.8-flash"

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY secret is missing.")

# Fetch recent cybersecurity news headlines.
query = urllib.parse.quote("cybersecurity news when:7d")
feed_url = (
    "https://news.google.com/rss/search?q="
    + query
    + "&hl=en-GB&gl=GB&ceid=GB:en"
)

request = urllib.request.Request(
    feed_url,
    headers={"User-Agent": "ITSecureContentBot/1.0"}
)

with urllib.request.urlopen(request, timeout=30) as response:
    feed = ET.fromstring(response.read())

stories = []

for item in feed.findall(".//item")[:10]:
    title = item.findtext("title", "").strip()
    link = item.findtext("link", "").strip()
    published = item.findtext("pubDate", "").strip()
    source_element = item.find("source")
    source = (
        source_element.text.strip()
        if source_element is not None and source_element.text
        else "Source shown in article link"
    )

    if title and link:
        stories.append({
            "title": title,
            "source": source,
            "published": published,
            "url": link
        })

if not stories:
    raise RuntimeError("No news stories found in the RSS feed.")

prompt = f"""
You are the content writer for IT Secure, a practice website
aimed at recruitment businesses.

Choose one recent cybersecurity news story from this list that
is useful to UK recruitment agencies, staffing firms, or SMEs.

NEWS FEED:
{json.dumps(stories, ensure_ascii=False, indent=2)}

Create a REVIEW DRAFT in Markdown containing:

1. The selected story title, publisher, date and original URL.
2. An SEO-friendly blog title.
3. A meta description under 160 characters.
4. A useful blog article of approximately 600-800 words.
5. Practical security steps for recruitment businesses.
6. A natural, non-pushy call to action for an IT health check.
7. One LinkedIn post.
8. One shorter Instagram caption with relevant hashtags.
9. A short checklist of facts and claims a human must verify.

Important rules:
- Treat the news feed as leads, not verified full articles.
- Do not pretend you read the full linked article.
- Never invent quotes, statistics, incidents, dates or facts.
- Clearly distinguish confirmed headline information from general
  cybersecurity advice.
- Include the original source URL in the draft.
- Do not claim IT Secure has certifications, clients or services
  unless they are explicitly established here.
- Use clear British English and explain technical terms simply.
- This is a draft for review, NOT approved publication content.
- Return Markdown only.
"""

payload = {
    "contents": [{
        "parts": [{"text": prompt}]
    }],
    "generationConfig": {
        "maxOutputTokens": 3000,
        "thinkingConfig": {
            "thinkingLevel": "low"
        }
    }
}

api_url = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    + MODEL
    + ":generateContent"
)

api_request = urllib.request.Request(
    api_url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "x-goog-api-key": API_KEY
    },
    method="POST"
)

with urllib.request.urlopen(api_request, timeout=240) as response:
    result = json.loads(response.read().decode("utf-8"))

parts = result.get("candidates", [{}])[0].get(
    "content", {}
).get("parts", [])

draft = "\n".join(
    part["text"] for part in parts if "text" in part
).strip()

if not draft:
    raise RuntimeError(
        "Gemini returned no draft. Check the API response and model access."
    )

output_dir = Path("output")
output_dir.mkdir(exist_ok=True)

today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
output_file = output_dir / f"content-draft-{today}.md"

output_file.write_text(
    "# IT Secure — Content Draft\n\n"
    f"Generated: {today} (UTC)\n\n"
    "**Status: DRAFT — verify before publishing.**\n\n"
    + draft
    + "\n",
    encoding="utf-8"
)

print(f"Draft created: {output_file}")
print(f"News stories considered: {len(stories)}")
