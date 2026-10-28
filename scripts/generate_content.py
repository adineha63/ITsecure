
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
You are the senior cybersecurity content writer and editorial
research assistant for IT Secure, a UK-focused cybersecurity
practice targeting recruitment businesses, staffing firms, and SMEs.

Your goal is to create accurate, useful, original content that
builds trust, supports relevant services, and is suitable for
human editorial review before publication.

NEWS FEED:
{json.dumps(stories, ensure_ascii=False, indent=2)}

STEP 1 — SELECT A RELEVANT STORY

Review the available headlines and choose one story that is:
- Recent and relevant to UK businesses.
- Relevant to recruitment agencies, staffing firms, or SMEs.
- Connected to cybersecurity, data protection, identity security,
  ransomware, business continuity, or third-party risk.
- From a recognisable, credible news publisher where possible.

Do not select a story merely because its headline sounds dramatic.
If none is sufficiently relevant, create an evergreen educational
article instead and clearly label it as such.

STEP 2 — HANDLE SOURCES AND FACTS RESPONSIBLY

Important: The feed provides headlines, publishers, dates and links.
It does not provide the full article text.

- Do not claim to have read or independently verified an article.
- Do not invent incident details, affected organisations, victims,
  data types, financial losses, quotations, statistics or outcomes.
- Treat the headline as a lead, not proof of every detail.
- Do not infer that personal data was exposed simply because
  a supplier or organisation experienced a cyber incident.
- Separate information explicitly present in the feed from general
  cybersecurity advice.
- Never present assumptions as confirmed facts.
- Include the original feed URL and identify it as a source link.
- Flag facts that require checking against the original publisher.
- If a story cannot support a reliable article without further
  research, choose another story or produce evergreen content.

STEP 3 — CREATE THE CONTENT PACKAGE

Return the following sections in Markdown.

1. EDITORIAL SUMMARY
- Selected topic and publisher.
- Publication date and original URL.
- Why the topic is relevant to the target audience.
- What is known from the feed and what remains unverified.
- Label the source verification status clearly.

2. SEO TITLE AND META DESCRIPTION
- Write a clear, accurate, search-friendly title.
- Keep the meta description under 160 characters.
- Use relevant keywords naturally.
- Do not make exaggerated promises or misleading claims.

3. BLOG ARTICLE
- Aim for approximately 600–800 words.
- Use a clear H1 title and descriptive H2/H3 headings.
- Write in natural British English.
- Explain technical terms in simple language.
- Start with the business problem and explain why it matters.
- If discussing a news incident, include only facts supported
  by verified information supplied to you.
- Do not fabricate details to make the story more interesting.
- Include practical advice relevant to UK recruitment agencies,
  staffing firms or SMEs.
- Avoid repetitive paragraphs, generic introductions and keyword
  stuffing.
- Do not copy or closely imitate the source article.
- Do not claim that IT Secure investigated or handled an incident.

4. PRACTICAL ACTION CHECKLIST
Provide 3–5 specific, realistic actions a business can take.
Explain the purpose of each action briefly.
Distinguish general recommendations from legal requirements.
Do not invent compliance obligations or deadlines.

5. CALL TO ACTION
Write a natural, non-pushy call to action for an IT health check.
Do not invent service features, certifications, guarantees,
client results or landing-page URLs.
If the exact service or URL is not confirmed, flag it for review
rather than inventing a destination.

6. LINKEDIN POST
- Write a concise, engaging post for business decision-makers.
- Open with a useful insight or question.
- Explain the business relevance and give practical advice.
- Avoid sensationalism and unsupported claims.
- Include a CTA only where appropriate.
- Do not use a fake article link or claim the blog is published.

7. INSTAGRAM CAPTION
- Write a shorter, accessible version of the key advice.
- Use a few relevant hashtags.
- Do not imply that an unverified incident is confirmed.
- Do not refer to a link in the bio unless one is actually available.

8. HUMAN REVIEW CHECKLIST
Include checks for:
- Original source and incident details.
- Dates, names, statistics and quotations.
- UK legal or regulatory statements.
- Relevance to the intended audience.
- Accuracy of IT Secure service descriptions.
- Internal links and CTA destination.
- Duplicate content and editorial quality.

EDITORIAL RULES
- This output is an UNAPPROVED DRAFT.
- Never claim a human has verified the content.
- Do not invent company information or capabilities.
- Do not fabricate internal links, references or URLs.
- Avoid unsupported legal advice and absolute security claims.
- Use accurate, helpful, original content rather than filler.
- Flag missing information explicitly.
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
