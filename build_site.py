"""Build a browsable HTML archive from the markdown briefs in outputs/.

Renders each outputs/brief_*.md into a styled, newsletter-style HTML page in
site/ (with a masthead, at-a-glance metrics, a table of contents, and inline
trend sparklines), and writes site/index.html as a card-based archive. The
site/ folder is what GitHub Pages publishes.
"""

import csv
import html
import json
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

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">'
)

CSS = """
:root{--ink:#16181d;--muted:#5f6368;--accent:#b3261e;--link:#1a56db;
  --line:#e7e7ea;--soft:#f6f6f7;--bg:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:16px;line-height:1.65;-webkit-font-smoothing:antialiased}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline}
.masthead{border-bottom:1px solid var(--line);background:var(--soft)}
.masthead-inner{max-width:1040px;margin:0 auto;padding:1.4rem 1.25rem}
.brand{font-weight:700;letter-spacing:.14em;text-transform:uppercase;
  font-size:.8rem;color:var(--accent)}
.tagline{font-size:.95rem;color:var(--muted);margin-top:.15rem}
.daterange{font-size:.85rem;color:var(--muted);margin-top:.35rem;
  font-variant-numeric:tabular-nums}
.wrap{max-width:1040px;margin:0 auto;padding:1.5rem 1.25rem 3rem}
.back{display:inline-block;font-size:.85rem;margin-bottom:1.25rem}
.metrics{display:flex;flex-wrap:wrap;gap:.75rem;margin-bottom:2rem}
.metric{flex:1 1 150px;border:1px solid var(--line);border-radius:12px;
  padding:.9rem 1rem;background:#fff}
.metric-num{font-size:1.5rem;font-weight:700;line-height:1.1;
  font-variant-numeric:tabular-nums}
.metric-label{font-size:.78rem;color:var(--muted);margin-top:.25rem}
.layout{display:grid;grid-template-columns:1fr;gap:2rem}
.toc-title{font-weight:600;font-size:.72rem;letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted);margin-bottom:.5rem}
.toc ol{margin:0;padding-left:1.1rem;font-size:.9rem}
.toc li{margin:.3rem 0}
.brief h1{font-size:1.9rem;line-height:1.2;margin:.2rem 0 1.2rem;
  letter-spacing:-.01em}
.brief h2{font-size:.82rem;margin:2.2rem 0 .5rem;text-transform:uppercase;
  letter-spacing:.08em;color:var(--accent);font-weight:600}
.brief h3{font-size:1.2rem;margin:2rem 0 .5rem;padding-top:1.6rem;
  border-top:1px solid var(--line)}
.brief h3:first-of-type{border-top:none;padding-top:0}
.brief p{margin:.6rem 0}
.brief ul{padding-left:1.15rem}
.spark{display:inline-flex;align-items:center;gap:5px;margin:2px 8px 2px 0;
  font-size:.72rem;color:var(--muted);vertical-align:middle}
.spark svg{vertical-align:middle}
.cards{display:grid;grid-template-columns:1fr;gap:1rem;margin-top:1.5rem}
.card{border:1px solid var(--line);border-radius:14px;padding:1.1rem 1.2rem;
  display:block;color:inherit;transition:border-color .15s,box-shadow .15s}
.card:hover{border-color:#cfcfd4;box-shadow:0 2px 10px rgba(0,0,0,.05);
  text-decoration:none}
.card-date{font-size:.74rem;letter-spacing:.08em;text-transform:uppercase;
  color:var(--accent);font-weight:600}
.card-sowhat{font-size:1.05rem;font-weight:600;margin-top:.4rem;line-height:1.4;
  color:var(--ink)}
.card-cta{font-size:.82rem;color:var(--link);margin-top:.6rem}
.site-footer{border-top:1px solid var(--line);color:var(--muted);
  font-size:.82rem;text-align:center;padding:1.5rem 1rem}
@media(min-width:700px){.cards{grid-template-columns:1fr 1fr}}
@media(min-width:900px){
  .layout{grid-template-columns:200px 1fr}
  .toc{position:sticky;top:1.25rem;align-self:start}
}
"""

PAGE_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>{fonts}<style>{css}</style></head>
<body>
<header class="masthead"><div class="masthead-inner">
<div class="brand">Cultural Signal Tracker</div>
<div class="tagline">Weekly Cultural Signal Report &middot; US Hispanic Consumer Culture</div>
<div class="daterange">{daterange}</div>
</div></header>
<main class="wrap">
<a class="back" href="index.html">&larr; All briefs</a>
<section class="metrics">{metrics}</section>
<div class="layout">
<nav class="toc">{toc}</nav>
<article class="brief">{body}</article>
</div>
</main>
<footer class="site-footer">Cultural Signal Tracker &middot; Built by Mariana Saca</footer>
</body></html>
"""

INDEX_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cultural Signal Tracker &mdash; Archive</title>{fonts}<style>{css}</style></head>
<body>
<header class="masthead"><div class="masthead-inner">
<div class="brand">Cultural Signal Tracker</div>
<div class="tagline">Weekly cultural signal reports &middot; US Hispanic Consumer Culture</div>
<div class="daterange">{count} brief(s) archived</div>
</div></header>
<main class="wrap"><div class="cards">{cards}</div></main>
<footer class="site-footer">Cultural Signal Tracker &middot; Built by Mariana Saca</footer>
</body></html>
"""


def brief_date(path):
    """Extract the YYYY-MM-DD date from a brief_<date>.md filename."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    return match.group(1) if match else path.stem


def extract_date_range(md_text, fallback):
    """Pull the 'YYYY-MM-DD to YYYY-MM-DD' range from the brief text."""
    match = re.search(r"\d{4}-\d{2}-\d{2}\s+to\s+\d{4}-\d{2}-\d{2}", md_text)
    return match.group(0) if match else fallback


def extract_so_what(md_text):
    """Return the 'So What This Week' headline sentence, plain text."""
    match = re.search(r"##\s*So What This Week\s*\n+(.+)", md_text)
    if not match:
        return ""
    line = match.group(1).strip()
    return line.replace("**", "").strip("* ").strip()


def news_article_count(date):
    """Total articles fetched in the news JSON for a date, or None."""
    path = DATA_DIR / f"news_{date}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    total = 0
    for langs in data.get("categories", {}).values():
        for block in langs.values():
            total += block.get("fetched", 0)
    return total


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


def top_mover(series, recent_days=28, floor=5.0):
    """Find the keyword with the largest % change (recent vs earlier avg).

    Only considers keywords whose recent average clears `floor`, so tiny
    near-zero swings don't dominate. Returns (keyword, pct) or None.
    """
    best = None
    best_abs = -1.0
    for kw, vals in series.items():
        if len(vals) <= recent_days:
            continue
        recent, earlier = vals[-recent_days:], vals[:-recent_days]
        if not earlier:
            continue
        r = sum(recent) / len(recent)
        e = sum(earlier) / len(earlier)
        if r < floor or e <= 0:
            continue
        pct = (r - e) / e * 100
        if abs(pct) > best_abs:
            best, best_abs = (kw, pct), abs(pct)
    return best


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


def add_sparklines(html_body, series):
    """Append a keyword sparkline to each momentum line in the HTML.

    A block (<p> or <li>) is treated as a momentum line if its text mentions
    'momentum'. For every trends keyword named in that block, a coloured
    sparkline of that keyword's 12-week interest is appended.
    """
    if not series:
        return html_body

    def augment(match):
        tag, inner = match.group(1), match.group(2)
        plain = STRIP_TAGS.sub("", inner)
        # Trends lines in the brief are flagged with a "**Trend:**" /
        # "**Trends:**" lead-in; that's our reliable hook for where a
        # sparkline belongs.
        if "trend:" not in plain.lower() and "trends:" not in plain.lower():
            return match.group(0)

        found = sorted(
            (plain.find(kw), kw) for kw in series if plain.find(kw) != -1
        )
        spans = []
        for idx, kw in found:
            color = momentum_color(plain[idx + len(kw): idx + len(kw) + 80])
            svg = sparkline_svg(series[kw], color)
            spans.append(
                f'<span class="spark" title="{html.escape(kw)}">'
                f"{html.escape(kw)}: {svg}</span>"
            )
        if not spans:
            return match.group(0)
        return f"<{tag}>{inner}<br>{''.join(spans)}</{tag}>"

    return BLOCK_RE.sub(augment, html_body)


def collect_h3(tokens):
    """Flatten markdown toc_tokens into an ordered list of (id, name) H3s."""
    out = []
    for tok in tokens:
        if tok.get("level") == 3:
            out.append((tok["id"], tok["name"]))
        out.extend(collect_h3(tok.get("children", [])))
    return out


def metric_card(num, label):
    return (
        f'<div class="metric"><div class="metric-num">{html.escape(str(num))}</div>'
        f'<div class="metric-label">{html.escape(label)}</div></div>'
    )


def render_brief(md_path):
    """Render one brief to HTML; return (html_name, date, so_what)."""
    date = brief_date(md_path)
    text = md_path.read_text(encoding="utf-8")

    md = markdown.Markdown(extensions=["extra", "sane_lists", "toc"])
    body = md.convert(text)
    h3s = collect_h3(md.toc_tokens)

    # Drop the standalone date paragraph (shown in the masthead instead).
    body = re.sub(
        r"<p>\s*\d{4}-\d{2}-\d{2}\s+to\s+\d{4}-\d{2}-\d{2}\s*</p>",
        "", body, count=1,
    )
    # Source links open in a new tab; sparklines go next to momentum scores.
    body = re.sub(
        r'<a href="(https?://)',
        r'<a target="_blank" rel="noopener noreferrer" href="\1',
        body,
    )
    series = load_trends_series(date)
    body = add_sparklines(body, series)

    # At-a-glance metrics.
    articles = news_article_count(date)
    mover = top_mover(series)
    metrics = (
        metric_card(articles if articles is not None else "—", "Articles analyzed")
        + metric_card(len(h3s), "Signals detected")
        + metric_card(
            f"{mover[1]:+.0f}%" if mover else "—",
            f"Top mover · {mover[0]}" if mover else "Top mover",
        )
    )

    # Table of contents (signals only).
    if h3s:
        items = "".join(
            # `name` comes from md.toc_tokens already HTML-escaped — don't double-escape.
            f'<li><a href="#{hid}">{name}</a></li>' for hid, name in h3s
        )
        toc = f'<div class="toc-title">In this brief</div><ol>{items}</ol>'
    else:
        toc = ""

    html_name = f"{md_path.stem}.html"
    (SITE_DIR / html_name).write_text(
        PAGE_TEMPLATE.format(
            title=f"Cultural Signal Report — {date}",
            fonts=FONTS,
            css=CSS,
            daterange=html.escape(extract_date_range(text, date)),
            metrics=metrics,
            toc=toc,
            body=body,
        ),
        encoding="utf-8",
    )
    return html_name, date, extract_so_what(text)


def main():
    SITE_DIR.mkdir(exist_ok=True)
    briefs = sorted(OUTPUT_DIR.glob("brief_*.md"), reverse=True)

    if not briefs:
        print("No briefs found in outputs/. Nothing to build.")
        return

    cards = []
    for md_path in briefs:
        html_name, date, so_what = render_brief(md_path)
        headline = html.escape(so_what) if so_what else "View the full brief"
        cards.append(
            f'<a class="card" href="{html_name}">'
            f'<div class="card-date">{date}</div>'
            f'<div class="card-sowhat">{headline}</div>'
            f'<div class="card-cta">Read brief &rarr;</div></a>'
        )

    (SITE_DIR / "index.html").write_text(
        INDEX_TEMPLATE.format(
            fonts=FONTS, css=CSS, count=len(briefs), cards="\n".join(cards)
        ),
        encoding="utf-8",
    )
    print(f"Built site/ with {len(briefs)} brief(s) -> {SITE_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
