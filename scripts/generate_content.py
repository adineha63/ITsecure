
import os
import json
import re
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from html.parser import HTMLParser

# ==================================================
# IT SECURE CONTENT AUTOMATION
# Reads website pages, researches topic ideas,
# generates a blog and social posts, checks links,
# and saves a Markdown draft for human review.
# ==================================================

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing. Check GitHub repository "
        "Settings > Secrets and variables > Actions."
    )


# ==================================================
# 1. READ EXISTING WEBSITE HTML FILES
# ==================================================

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_text = ""
        self.in_title = False
        self.in_ignored_tag = False
        self.in_heading = False
        self.headings = []
        self.text_parts = []
        self.links = []
        self.current_heading_text = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "title":
            self.in_title = True

        if tag in ("script", "style", "noscript"):
            self.in_ignored_tag = True

        if tag in ("h1", "h2", "h3"):
            self.in_heading = True
            self.current_heading_text = ""

        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

        if tag in ("script", "style", "noscript"):
            self.in_ignored_tag = False

        if tag in ("h1", "h2", "h3") and self.in_heading:
            heading = self.current_heading_text.strip()
            if heading:
                self.headings.append(heading)
            self.in_heading = False
            self.current_heading_text = ""

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text:
            return

        if self.in_title:
            self.title_text += " " + text

        if not self.in_ignored_tag:
            self.text_parts.append(text)

            if self.in_heading:
                self.current_heading_text += " " + text


def route_for_file(file_path):
    relative = file_path.relative_to(Path(".")).as_posix()

    if relative == "index.html":
        return "/"

    if relative.endswith("/index.html"):
        return "/" + relative[:-len("index.html")]

    return "/" + relative


pages = []
existing_routes = set()

ignored_directories = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
}

for html_file in Path(".").rglob("*.html"):
    if any(part in ignored_directories for part in html_file.parts):
        continue

    route = route_for_file(html_file)

    try:
        html = html_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"Skipping unreadable file {html_file}: {error}")
        continue

    parser = PageParser()

    try:
        parser.feed(html)
    except Exception as error:
        print(f"Could not fully parse {html_file}: {error}")

    existing_routes.add(route)

    pages.append({
        "file": html_file.as_posix(),
        "route": route,
        "title": parser.title_text.strip(),
        "headings": parser.headings[:25],
        "content": " ".join(parser.text_parts)[:1800],
        "links": parser.links[:50],
    })

if not pages:
    raise RuntimeError(
        "No HTML pages found. Check that the workflow is running "
        "in the root of your website repository."
    )

print(f"Website pages inspected: {len(pages)}")
for page in pages:
    print(f"  {page['route']} — {page['title'] or page['file']}")


# ==================================================
# 2. COLLECT GOOGLE AUTOCOMPLETE SUGGESTIONS
# ==================================================

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
        headers={"User-Agent": "Mozilla/5.0"},
    )

    for attempt in range(1, 3):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                result = json.loads(
                    response.read().decode("utf-8")
                )

            for suggestion in result[1]:
                suggestions.append({
                    "seed": seed,
                    "suggestion": suggestion,
                })

            break

        except Exception as error:
            print(
                f"Autocomplete attempt {attempt}/2 failed "
                f"for '{seed}': {error}"
            )

            if attempt == 1:
                time.sleep(2)

print(f"Autocomplete suggestions collected: {len(suggestions)}")


# ==================================================
# 3. BUILD THE CONTENT BRIEF
# ==================================================

website_summary = json.dumps(
    [
        {
            "route": page["route"],
            "title": page["title"],
            "headings": page["headings"],
            "content": page["content"],
        }
        for page in pages
    ],
    ensure_ascii=False,
    indent=2,
)

prompt = f"""
You are the content strategist and writer for IT Secure.

ABOUT THE BUSINESS
IT Secure is a practice website aimed at UK recruitment businesses.
The homepage promotes a free IT Health Check.

The homepage describes these service areas:
- Managed IT Support
- Cybersecurity
- Backup & Disaster Recovery
- Cloud Solutions

The target audience includes recruitment business owners and managers.
Their likely concerns include protecting candidate and client information,
keeping staff working, cybersecurity, backups and recovery.

EXISTING WEBSITE PAGES
The following information was extracted from actual HTML files
in the website repository. Use it as your source of truth.

{website_summary}

GOOGLE AUTOCOMPLETE SUGGESTIONS
These are possible topic ideas. They are NOT verified search-volume,
ranking or conversion data.

{json.dumps(suggestions, ensure_ascii=False, indent=2)}

YOUR TASK

Create one Markdown report with the following sections.

## 1. Content Opportunity Report
Recommend 12 relevant article topics.

For each topic include:
- Suggested article title
- Intended reader
- Question or problem it addresses
- Business relevance
- Qualitative priority: High, Medium or Low

Label all priorities as estimates. Do not invent search volumes
or claim that a topic will rank or convert.

Prioritise topics that could help recruitment businesses understand
IT risks and naturally discover the free IT Health Check.

Avoid generic news and topics unrelated to IT Secure.

## 2. Recommended Article
Choose the strongest topic and explain why it fits the audience
and the business.

## 3. SEO and AI Search Brief
Include:
- SEO title
- Meta description under 160 characters
- Main search question
- Related questions
- A concise, direct answer to the main question

Do not promise ranking or AI search inclusion.

## 4. Blog Article
Write approximately 600–800 words in clear British English.

Use helpful headings, specific practical advice and natural wording.
Avoid keyword stuffing, repetitive paragraphs and empty marketing claims.

Do not pretend to have conducted research that was not provided.

## 5. Internal Links
Suggest relevant internal links using ONLY these existing routes:

{json.dumps(sorted(existing_routes), ensure_ascii=False)}

Use the exact route shown. Never invent a page or URL.
If no relevant page exists, say "No suitable existing page".

## 6. Call to Action
Include a natural invitation to take the free IT Health Check.

Do not claim the assessment includes specific tests, delivers a report,
takes a specific amount of time, or guarantees results unless confirmed
by the supplied website content.

## 7. LinkedIn Post
Write one useful, professional post based on the article.

## 8. Instagram Caption
Write a shorter caption with a few relevant hashtags.

## 9. Claims to Verify Before Publishing
List statistics, legal or compliance statements, technical promises,
guarantees, service capabilities and business claims requiring review.

Do not present unsupported claims as facts.

## 10. Final Review Checklist
Check audience relevance, factual caution, clarity, CTA, internal links
and whether the content duplicates existing website information.

IMPORTANT RULES
- Do not invent customers, testimonials, certifications, awards,
  statistics, prices or service guarantees.
- Do not claim IT Secure provides a service unless supported by
  the supplied website content or the service list above.
- Do not treat autocomplete suggestions as proof of search volume.
- Do not give definitive legal advice.
- Do not invent internal routes.
- Clearly flag uncertainty.
- This is a draft for human review, NOT approved publication content.
- Return Markdown only.
"""


# ==================================================
# 4. CALL GEMINI WITH TIMEOUTS AND RETRIES
# ==================================================

payload = {
    "contents": [
        {
            "parts": [
                {"text": prompt}
            ]
        }
    ],
    "generationConfig": {
        "temperature": 0.3,
        "maxOutputTokens": 5000,
    },
}

api_url = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    + MODEL
    + ":generateContent"
)

result = None

for attempt in range(1, 4):
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
        print(
            f"Calling Gemini model {MODEL} "
            f"(attempt {attempt}/3)..."
        )

        with urllib.request.urlopen(
            api_request,
            timeout=240,
        ) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )

        break

    except urllib.error.HTTPError as error:
        details = error.read().decode(
            "utf-8", errors="replace"
        )

        if (
            error.code in (429, 500, 502, 503, 504)
            and attempt < 3
        ):
            print(
                f"Gemini returned HTTP {error.code}. "
                "Retrying in 15 seconds..."
            )
            time.sleep(15)
            continue

        raise RuntimeError(
            f"Gemini API returned HTTP {error.code}: {details}"
        ) from error

    except (TimeoutError, urllib.error.URLError) as error:
        if attempt == 3:
            raise RuntimeError(
                "Gemini did not respond after 3 attempts. "
                "Try running the workflow again later. "
                f"Last error: {error}"
            ) from error

        print(
            "Gemini timed out or had a connection problem. "
            "Retrying in 15 seconds..."
        )
        time.sleep(15)

if result is None:
    raise RuntimeError("Gemini did not return a response.")

if "candidates" not in result or not result["candidates"]:
    raise RuntimeError(
        "Gemini returned no content candidates. Response: "
        + json.dumps(result, ensure_ascii=False)[:2000]
    )

parts = result["candidates"][0].get(
    "content", {}
).get("parts", [])

draft = "\n".join(
    part["text"]
    for part in parts
    if "text" in part
).strip()

if not draft:
    raise RuntimeError(
        "Gemini returned an empty draft. Check the API response."
    )


# ==================================================
# 5. CHECK MARKDOWN INTERNAL LINKS
# ==================================================

markdown_links = re.findall(
    r"\]\((/[^)\s#?]*)(?:[?#][^)]*)?\)",
    draft,
)

invalid_routes = sorted({
    route
    for route in markdown_links
    if route not in existing_routes
})

validation_report = [
    "\n\n---",
    "\n## Automated Website Checks",
    "\n\n### HTML pages found in the repository",
]

for page in pages:
    validation_report.append(
        f"\n- `{page['route']}` — "
        f"{page['title'] or page['file']}"
    )

validation_report.append("\n\n### Internal link validation")

if invalid_routes:
    validation_report.append(
        "\nThese generated root-relative Markdown links did not match "
        "the HTML routes found in the repository:"
    )

    for route in invalid_routes:
        validation_report.append(f"\n- `{route}`")

    validation_report.append(
        "\n\nReview and correct these links before publishing."
    )
else:
    validation_report.append(
        "\nAll detected root-relative Markdown links matched "
        "an HTML route found in the repository."
    )

validation_report.append(
    "\n\n**Limitations:** These checks do not verify factual accuracy, "
    "legal claims, external links, search volume, rankings, or whether "
    "the live website serves every route correctly."
)


# ==================================================
# 6. SAVE THE REPORT
# ==================================================

output_dir = Path("output")
output_dir.mkdir(exist_ok=True)

today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
output_file = output_dir / f"content-draft-{today}.md"

output_file.write_text(
    "# IT Secure — Content Opportunity Report and Draft\n\n"
    f"Generated: {today} (UTC)\n\n"
    "**Status: DRAFT — review before publishing.**\n\n"
    + draft
    + "\n"
    + "\n".join(validation_report)
    + "\n",
    encoding="utf-8",
)

print(f"Draft created successfully: {output_file}")
print(f"HTML pages inspected: {len(pages)}")
print(f"Autocomplete suggestions collected: {len(suggestions)}")
print(f"Invalid internal routes flagged: {len(invalid_routes)}")
