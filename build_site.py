"""Build a browsable HTML archive from the markdown briefs in outputs/.

Reads every outputs/brief_*.md, renders each to a styled HTML page in
site/, and writes site/index.html listing all briefs newest-first. The
site/ folder is what GitHub Pages publishes.
"""

import re
from pathlib import Path

import markdown

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "outputs"
SITE_DIR = BASE_DIR / "site"

PAGE_CSS = """
  body { max-width: 760px; margin: 2rem auto; padding: 0 1rem;
         font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         color: #1a1a1a; }
  h1 { font-size: 1.7rem; border-bottom: 2px solid #eee; padding-bottom: .4rem; }
  h2 { font-size: 1.25rem; margin-top: 2rem; color: #b3261e; }
  h3 { font-size: 1.05rem; margin-top: 1.4rem; }
  a { color: #1a73e8; text-decoration: none; }
  a:hover { text-decoration: underline; }
  ul { padding-left: 1.2rem; }
  .back { display: inline-block; margin-bottom: 1.5rem; font-size: .9rem; }
  .meta { color: #666; font-size: .9rem; }
"""

PAGE_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{css}</style></head>
<body><a class="back" href="index.html">&larr; All briefs</a>
{body}
</body></html>
"""

INDEX_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cultural Signal Tracker — Archive</title><style>{css}</style></head>
<body>
<h1>Weekly Cultural Signal Reports</h1>
<p class="meta">US Hispanic Consumer Culture &middot; {count} brief(s)</p>
<ul>
{items}
</ul>
</body></html>
"""


def brief_date(path):
    """Extract the YYYY-MM-DD date from a brief_<date>.md filename."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    return match.group(1) if match else path.stem


def main():
    SITE_DIR.mkdir(exist_ok=True)
    briefs = sorted(OUTPUT_DIR.glob("brief_*.md"), reverse=True)

    if not briefs:
        print("No briefs found in outputs/. Nothing to build.")
        return

    items = []
    for md_path in briefs:
        date = brief_date(md_path)
        html_name = f"{md_path.stem}.html"
        body = markdown.markdown(
            md_path.read_text(encoding="utf-8"),
            extensions=["extra", "sane_lists"],
        )
        # Source citations are markdown links; make external ones open in a
        # new tab so readers don't navigate away from the brief.
        body = re.sub(
            r'<a href="(https?://)',
            r'<a target="_blank" rel="noopener noreferrer" href="\1',
            body,
        )
        (SITE_DIR / html_name).write_text(
            PAGE_TEMPLATE.format(title=f"Brief {date}", css=PAGE_CSS, body=body),
            encoding="utf-8",
        )
        items.append(f'  <li><a href="{html_name}">{date}</a></li>')

    (SITE_DIR / "index.html").write_text(
        INDEX_TEMPLATE.format(css=PAGE_CSS, count=len(briefs), items="\n".join(items)),
        encoding="utf-8",
    )
    print(f"Built site/ with {len(briefs)} brief(s) -> {SITE_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
