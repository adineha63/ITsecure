
import os
import json
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = "gemini-3.8-flash"

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY secret is missing.")

# These topics reflect IT Secure's current practice audience.
seed_queries = [
    "cybersecurity for recruitment agencies",
    "IT support for recruitment agencies",
    "cybersecurity checklist for small businesses",
    "Microsoft 365 security for small businesses",
    "how to prevent phishing attacks at work",
    "ransomware protection for small businesses",
    "IT health check for businesses",
    "data protection for recruitment agencies",
    "business email security",
    "backup and disaster recovery for small businesses",
]

def get_suggestions(query):
    url = (
        "https://suggestqueries.google.com/complete/search?"
        + urllib.parse.urlencode({
            "client": "firefox",
            "q": query
        })
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        return data[1] if len(data) > 1 else []

    except Exception as exc:
        print(f"Suggestion lookup skipped for '{query}': {exc}")
        return []

suggestions = {}

for query in seed_queries:
    results = get_suggestions(query)
    suggestions[query] = results[:8]

print("Search suggestion collection completed.")

research_data = {
    "seed_queries": seed_queries,
    "google_suggestions": suggestions,
    "audience": "UK recruitment agencies and small businesses",
    "website": "IT Secure",
    "primary_conversion": "Enquiry for an IT health check",
}

prompt = f"""
You are a B2B content strategist specialising in cybersecurity,
search intent, Google SEO and AI search visibility.

Develop a topic opportunity report for IT Secure, a practice
website aimed at UK recruitment agencies and small businesses.

RESEARCH INPUT:
{json.dumps(research_data, ensure_ascii=False, indent=2)}

OBJECTIVE:
Find useful topics that could attract relevant business visitors,
answer their questions and encourage suitable enquiries.

PART 1 — TOPIC OPPORTUNITY REPORT
Suggest 12 distinct content topics.

For each topic provide:
- Proposed title
- Main search query
- Search intent: informational, commercial or transactional
- Audience problem being solved
- Relevance to recruitment businesses (1-5)
- Likely enquiry potential (1-5)
- Differentiation opportunity (1-5)
- Recommended content format
- A brief explanation of why it deserves attention

Use the research inputs as clues, not proof of search volume.
Do not claim these are the most trending topics.
Do not invent keyword volumes, ranking difficulty or competitor data.
Make clear that scores are strategic estimates, not measured metrics.

PART 2 — PRIORITISATION
Select the three strongest topics for IT Secure.
Explain their trade-offs and identify the best first article.
Prioritise business relevance and enquiry potential over broad traffic.

PART 3 — FIRST ARTICLE DRAFT
Write a useful article of approximately 600-800 words on the
selected topic.

Include:
- SEO title
- Meta description under 160 characters
- Clear introduction answering the reader's main question
- Descriptive headings and practical steps
- A concise answer section suitable for readers and AI search
- FAQs based on genuine reader needs
- A natural call to action for an IT health check
- Suggested internal links to relevant IT Secure pages
- Claims or details that need human verification

PART 4 — SOCIAL CONTENT
Create one LinkedIn post and one Instagram caption based on
the article.

RULES:
- Use clear British English.
- Avoid keyword stuffing and generic filler.
- Do not fabricate statistics, customer stories, certifications,
  services or claims about IT Secure.
- Do not claim guaranteed Google rankings or AI citations.
- Do not imply the search suggestions provide search-volume data.
- Clearly label the output as a draft requiring review.
- Return Markdown only.
"""

payload = {
    "contents": [{
        "parts": [{"text": prompt}]
    }],
    "generationConfig": {
        "temperature": 0.3,
        "maxOutputTokens": 7000
    }
}

api_url = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    + MODEL
    + ":generateContent"
)

request = urllib.request.Request(
    api_url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "x-goog-api-key": API_KEY
    },
    method="POST"
)

try:
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))

except urllib.error.HTTPError as exc:
    details = exc.read().decode("utf-8", errors="replace")
    raise RuntimeError(
        f"Gemini API returned HTTP {exc.code}: {details}"
    ) from exc

parts = result.get("candidates", [{}])[0].get(
    "content", {}
).get("parts", [])

draft = "\n".join(
    part["text"] for part in parts if "text" in part
).strip()

if not draft:
    raise RuntimeError(
        "Gemini returned no text. Check the API response, "
        "model availability and usage limits."
    )

output_dir = Path("output")
output_dir.mkdir(exist_ok=True)

today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
output_file = output_dir / f"topic-research-{today}.md"

output_file.write_text(
    "# IT Secure — Topic Research and Content Draft\n\n"
    f"Generated: {today} (UTC)\n\n"
    "**Status: DRAFT — verify before publishing.**\n\n"
    "Note: Google suggestions are not search-volume or trend data. "
    "Topic scores are AI-generated estimates.\n\n"
    + draft
    + "\n",
    encoding="utf-8"
)

print(f"Research report and article draft saved to {output_file}")
print("Review the report before publishing any content.")
