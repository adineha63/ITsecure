
import os
import json
import re
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from html.parser import HTMLParser

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = "gemini-3.8-flash"

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing. Check your GitHub Actions secret."
    )


# --------------------------------------------------
# 1. Read the real website pages from the repository
# --------------------------------------------------

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_text = ""
        self.in_title = False
        self.headings = []
        self.links = []
        self.text_parts = []
        self.in_script_or_style = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "title":
            self.in_title = True

        if tag in ("script", "style"):
            self.in_script_or_style = True

        if tag in ("h1", "h2", "h3"):
            self.current_heading = tag

        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

        if tag in ("script", "style"):
            self.in_script_or_style = False

        if tag in ("h1", "h2", "h3"):
            self.current_heading = None

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text:
            return

        if self.in_title:
            self.title_text += " " + text

        if not self.in_script_or_style:
            self.text_parts.append(text)

            if getattr(self, "current_heading", None):
                self.headings.append(text)


def route_for_file(file_path):
    relative = file_path.relative_to(Path(".")).as_posix()

    if relative == "index.html":
        return "/"

    if relative.endswith("/index.html"):
        return "/" + relative[:-len("index.html")]

    return "/" + relative


pages = []
existing_routes = set()

for html_file in Path(".").rglob("*.html"):
    if any(
        part in {".git", "node_modules", "venv"}
        for part in html_file.parts
    ):
        continue

    route = route_for_file(html_file)
    existing_routes.add(route)

    parser = PageParser()
    parser.current_heading = None

    try:
        parser.feed(html_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        continue

    pages.append({
        "file": html_file.as_posix(),
        "route": route,
        "title": parser.title_text.strip(),
        "headings": parser.headings[:30],
        "content": " ".join(parser.text_parts)[:4500],
        "links": parser.links[:80],
    })

if not pages:
    raise RuntimeError("No HTML website pages were found.")


# --------------------------------------------------
# 2. Collect Google autocomplete suggestions
# --------------------------------------------------

seed_queries = [
    "IT health check for recruitment agencies",
    "IT support for recruitment agencies",
    "cybersecurity for recruitment businesses",
    "protect candidate data",
    "recruitment agency data security",
    "backup and disaster recovery for small business",
    "Microsoft 365 security for recruitment agencies",
    "UK GDPR candidate data",
    "business continuity for recruitment agencies",
    "IT risks for small businesses",
]

suggestions = []

for seed in seed_queries:
    url = (
        "https://suggestqueries.google.com/complete/search"
        "?client=firefox&q="
        + urllib.parse.quote(seed)
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            result = json.loads(response.read().decode("utf-8"))

        for suggestion in result[1]:
            suggestions.append({
                "seed": seed,
                "suggestion": suggestion
            })

    except Exception as error:
        print(f"Autocomplete unavailable for '{seed}': {error}")


# --------------------------------------------------
# 3. Ask Gemini to create relevant content
# --------------------------------------------------

website_summary = json.dumps(
    [
        {
            "route": page["route"],
            "title": page["title"],
            "headings": page["headings"],
            "content": page["content"],
            "links": page["links"],
        }
        for page in pages
    ],
    ensure_ascii=False,
    indent=2,
)

prompt = f"""
You are the content strategist and writer for IT Secure.

WEBSITE AND AUDIENCE
IT Secure is a practice website aimed at UK recruitment businesses.
Its homepage promotes a free IT Health Check.

The homepage describes these service areas:
- Managed IT Support
- Cybersecurity
- Backup & Disaster Recovery
- Cloud Solutions

The audience includes recruitment business owners and managers.
They care about protecting candidate and client information,
keeping staff working, cybersecurity, backups and recovery.

REAL WEBSITE INVENTORY
The following information was extracted from actual HTML files
in the website repository. Use it as the source of truth.

{website_summary}

GOOGLE AUTOCOMPLETE SUGGESTIONS
These are topic ideas, not verified search-volume or conversion data.

{json.dumps(suggestions, ensure_ascii=False, indent=2)}

YOUR TASK

Create a Markdown review draft with these sections:

1. CONTENT OPPORTUNITY REPORT
- Recommend 12 relevant article topics.
- Give each a qualitative priority: High, Medium or Low.
- Explain the intended reader and business relevance.
- Label the priority as an estimate, not measured search data.
- Prefer topics that may attract people with a real IT problem
  and lead naturally to the free IT Health Check.
- Avoid generic cybersecurity news and unrelated trending topics.

2. RECOMMENDED ARTICLE
Choose the strongest topic and explain briefly why it fits
the website and audience.

3. SEO AND AI SEARCH BRIEF
Include a suggested title, meta description under 160 characters,
main question, related questions, and a concise answer suitable
for a search result or AI-generated answer.

4. BLOG ARTICLE
Write approximately 600–800 words in clear British English.
Use helpful headings and practical, understandable advice.
Do not keyword-stuff or repeat the same point unnecessarily.
Do not pretend to have performed research that was not provided.

5. INTERNAL LINKS
Suggest relevant internal links using ONLY routes present in
the REAL WEBSITE INVENTORY above.
Use the exact route from the inventory.
Do not invent service pages, case studies, contact pages or URLs.
If there is no relevant page, say "No suitable existing page".

6. CALL TO ACTION
Include a natural invitation to take the free IT Health Check.
Do not claim that the check includes particular tests, delivers
a report, takes a specific amount of time or guarantees results
unless the website inventory explicitly confirms it.

7. LINKEDIN POST
Write one useful, professional post based on the article.

8. INSTAGRAM CAPTION
Write a shorter caption with a few relevant hashtags.

9. CLAIMS TO VERIFY BEFORE PUBLISHING
List claims requiring human verification, including statistics,
legal or compliance statements, technical promises, guarantees,
specific service capabilities and unsupported business claims.
Do not present an unverified claim as established fact.

10. FINAL REVIEW CHECKLIST
Check audience relevance, factual caution, clarity, CTA,
internal-link accuracy and whether the content duplicates
existing website information.

IMPORTANT RULES
- Do not invent customers, testimonials, certifications,
  awards, statistics, prices or service guarantees.
- Do not say IT Secure provides a service unless supported
  by the website inventory or the explicit service list above.
- Do not treat autocomplete suggestions as proof of search volume.
- Do not claim a topic will rank or convert.
- Explain uncertainty instead of making unsupported promises.
- Do not make legal advice sound definitive.
- This is a draft for human review, NOT approved publication content.
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

api_request = urllib.request.Request(
    api_url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "x-goog-api-key": API_KEY,
    },
    method="POST",
)

try:
    with urllib.request.urlopen(api_request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))

except urllib.error.HTTPError as error:
    details = error.read().decode("utf-8", errors="replace")
    raise RuntimeError(
        f"Gemini API returned HTTP {error.code}: {details}"
    ) from error


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


# --------------------------------------------------
# 4. Check generated internal links against real pages
# --------------------------------------------------

markdown_links = re.findall(
    r"\]\((/[^)\s#?]*)(?:[?#][^)]*)?\)",
    draft
)

invalid_routes = sorted({
    route for route in markdown_links
    if route not in existing_routes
})

validation_report = [
    "\n\n---",
    "\n## Automated Website Checks",
    "\n\n### HTML pages found in the repository",
]

for page in pages:
    validation_report.append(
        f"\n- `{page['route']}` — {page['title'] or page['file']}"
    )

validation_report.append("\n\n### Internal link validation")

if invalid_routes:
    validation_report.append(
        "\nThe following generated internal routes did not match "
        "the repository's HTML page routes:"
    )
    for route in invalid_routes:
        validation_report.append(f"\n- `{route}`")
    validation_report.append(
        "\n\nReview these links and remove or correct them before publishing."
    )
else:
    validation_report.append(
        "\nAll detected root-relative Markdown links matched an HTML "
        "route in the repository. This does not verify external links "
        "or every possible link format."
    )

validation_report.append(
    "\n\n**Important:** These checks verify local HTML routes and "
    "content consistency only. They do not independently verify "
    "facts, legal claims, live website availability, search volume "
    "or ranking potential."
)

output_dir = Path("output")
output_dir.mkdir(exist_ok=True)

today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
output_file = output_dir / f"content-draft-{today}.md"

output_file.write_text(
    "# IT Secure — Content Opportunity Report and Draft\n\n"
    f"Generated: {today} (UTC)\n\n"
    "**Status: DRAFT — verify before publishing.**\n\n"
    + draft
    + "\n"
    + "\n".join(validation_report)
    + "\n",
    encoding="utf-8",
)

print(f"Draft created: {output_file}")
print(f"HTML pages inspected: {len(pages)}")
print(f"Autocomplete suggestions collected: {len(suggestions)}")
print(f"Invalid internal routes flagged: {len(invalid_routes)}")
