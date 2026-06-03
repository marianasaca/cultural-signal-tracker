"""Build a browsable HTML archive from the markdown briefs in outputs/.

Reads every outputs/brief_*.md, renders each to a styled HTML page in
site/, and writes site/index.html listing all briefs newest-first. The
site/ folder is what GitHub Pages publishes.
"""

import csv
import re
from pathlib import Path

import markdown

from categories import KEYWORDS

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "outputs"
DATA_DIR = BASE_DIR / "data"
SITE_DIR = BASE_DIR / "site"

# Sparkline colours by momentum direction.
RISING = "#2e7d32"     # green
DECLINING = "#c62828"  # red
STEADY = "#9e9e9e"     # gray

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
  .spark { display: inline-flex; align-items: center; gap: 4px;
           margin: 2px 6px 2px 0; font-size: .72rem; color: #666;
           vertical-align: middle; }
  .spark svg { vertical-align: middle; }
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


def load_trends_series(date):
    """Return {keyword: [interest, ...]} for the trends CSV of a given date.

    The series is ordered by date (oldest first). Returns {} if no matching
    trends CSV exists (e.g. Google rate-limited that week's run).
    """
    csv_path = DATA_DIR / f"trends_{date}.csv"
    if not csv_path.exists():
        return {}
    rows = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.setdefault(row["keyword"], []).append(
                (row["date"], float(row["interest"]))
            )
    return {kw: [v for _, v in sorted(pts)] for kw, pts in rows.items()}


def sparkline_svg(values, color, width=200, height=40, pad=3):
    """Render a list of interest values as a small inline SVG line chart."""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        x = pad if n == 1 else pad + i * (width - 2 * pad) / (n - 1)
        y = height / 2 if span == 0 else pad + (height - 2 * pad) * (1 - (v - lo) / span)
        pts.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="none" role="img" '
        f'aria-label="12-week search interest sparkline">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{" ".join(pts)}"/>'
        f"</svg>"
    )


def momentum_color(text_after_keyword):
    """Pick a sparkline colour from the momentum word nearest a keyword."""
    low = text_after_keyword.lower()
    nearest = {}
    for word, color in (
        ("rising", RISING),
        ("declining", DECLINING),
        ("steady", STEADY),
        ("early signal", STEADY),
    ):
        i = low.find(word)
        if i != -1:
            nearest[i] = color
    return nearest[min(nearest)] if nearest else STEADY


STRIP_TAGS = re.compile(r"<[^>]+>")
BLOCK_RE = re.compile(r"<(p|li)>(.*?)</\1>", re.DOTALL)


def add_sparklines(html, series):
    """Append a keyword sparkline to each momentum line in the HTML.

    A block (<p> or <li>) is treated as a momentum line if its text mentions
    'momentum'. For every trends keyword named in that block, a coloured
    sparkline of that keyword's 12-week interest is appended.
    """
    if not series:
        return html

    def augment(match):
        tag, inner = match.group(1), match.group(2)
        plain = STRIP_TAGS.sub("", inner)
        if "momentum" not in plain.lower():
            return match.group(0)

        found = sorted(
            (plain.find(kw), kw) for kw in series if plain.find(kw) != -1
        )
        spans = []
        for idx, kw in found:
            color = momentum_color(plain[idx + len(kw): idx + len(kw) + 80])
            svg = sparkline_svg(series[kw], color)
            spans.append(f'<span class="spark" title="{kw}">{kw}: {svg}</span>')
        if not spans:
            return match.group(0)
        return f"<{tag}>{inner}<br>{''.join(spans)}</{tag}>"

    return BLOCK_RE.sub(augment, html)


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
        # Inject SVG sparklines next to momentum scores, using the trends CSV
        # from the same run (skipped if that week's CSV isn't available).
        body = add_sparklines(body, load_trends_series(date))
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
