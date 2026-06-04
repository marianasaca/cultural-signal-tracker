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

from categories import KEYWORDS, KEYWORDS_BY_CATEGORY

# Human-readable names for the config category keys.
CATEGORY_LABELS = {
    "economic_resilience": "Economic Resilience",
    "bicultural_fusion": "Bicultural Fusion",
    "heritage_milestones": "Heritage & Milestones",
}

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
.metric-num.sm{font-size:1rem;font-weight:600}
.metric-label{font-size:.78rem;color:var(--muted);margin-top:.25rem}
.databox{margin:1.4rem 0 .5rem}
.databox .metrics{margin-bottom:0}
.databox-title,.catchart-title{font-weight:600;font-size:.72rem;
  letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
  margin:0 0 .6rem}
.catchart{margin:1.6rem 0 2rem;padding:1.1rem 1.2rem;border:1px solid var(--line);
  border-radius:12px;background:#fff}
.catchart svg{display:block}
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


def news_article_breakdown(date):
    """Article counts from the news JSON: (total, en, es).

    Returns (None, 0, 0) when no news file exists for the date.
    """
    path = DATA_DIR / f"news_{date}.json"
    if not path.exists():
        return None, 0, 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None, 0, 0
    total = en = es = 0
    for langs in data.get("categories", {}).values():
        for lang, block in langs.items():
            n = block.get("fetched", 0)
            total += n
            if lang == "en":
                en += n
            elif lang == "es":
                es += n
    return total, en, es


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
    """Identify the week's headline keyword. Returns (keyword, pct|None).

    Prefers the biggest *riser* among keywords with real recent volume
    (recent avg >= floor), mirroring the brief's "Early signal" guardrail
    so we don't headline a noisy low-volume spike. If nothing clears the
    floor, falls back to the single highest-interest keyword so the card is
    never blank. `pct` is None only when an earlier average is zero.
    """
    scored = []  # (keyword, recent_avg, earlier_avg)
    for kw, vals in series.items():
        if len(vals) <= recent_days:
            continue
        recent, earlier = vals[-recent_days:], vals[:-recent_days]
        if not earlier:
            continue
        scored.append((kw, sum(recent) / len(recent), sum(earlier) / len(earlier)))
    if not scored:
        return None

    rising = [
        (kw, (r - e) / e * 100)
        for kw, r, e in scored
        if r >= floor and e > 0 and r > e
    ]
    if rising:
        return max(rising, key=lambda x: x[1])

    # Fallback: the most-searched keyword right now.
    kw, r, e = max(scored, key=lambda x: x[1])
    return kw, ((r - e) / e * 100 if e > 0 else None)


def category_strength(series, recent_days=28):
    """Average recent search-interest level per category, across *active*
    keywords only.

    These long-tail keywords are mostly zero on any given day, so averaging
    every keyword collapses each pillar toward ~0. Instead we average only
    keywords with non-zero recent interest — the pillar's live signals — for
    a more legible measure. Returns {category: (recent_avg, earlier_avg)};
    earlier_avg uses the same active keywords and only colours the bar by
    direction. Categories with no active keywords are omitted.
    """
    out = {}
    for cat, kws in KEYWORDS_BY_CATEGORY.items():
        recents, earliers = [], []
        for k in kws:
            vals = series.get(k)
            if not vals:
                continue
            recent_avg = sum(vals[-recent_days:]) / len(vals[-recent_days:])
            if recent_avg <= 0:
                continue  # dormant this window — skip
            recents.append(recent_avg)
            earlier = vals[:-recent_days]
            if earlier:
                earliers.append(sum(earlier) / len(earlier))
        if recents:
            r = sum(recents) / len(recents)
            e = sum(earliers) / len(earliers) if earliers else r
            out[cat] = (r, e)
    return out


def category_bar_svg(cat_strength, width=620, row_h=34, label_w=170, pad=10):
    """Horizontal bar chart of average recent search interest per category.

    Bar length is proportional to the recent interest level (0-100 scale);
    colour encodes direction vs the earlier window (green up, red down,
    gray flat). The numeric label is the interest index, not a percentage.
    """
    if not cat_strength:
        return ""
    rows = sorted(cat_strength.items(), key=lambda kv: kv[1][0], reverse=True)
    maxval = max(r for _, (r, _) in rows) or 1.0
    val_w = 44
    bar_max = width - label_w - val_w - pad * 2
    height = pad * 2 + row_h * len(rows)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="Average recent search interest by category" '
        f'font-family="Inter, sans-serif">'
    ]
    for i, (cat, (recent, earlier)) in enumerate(rows):
        y = pad + i * row_h
        mid = y + row_h / 2
        bar_w = recent / maxval * bar_max
        diff = recent - earlier
        color = RISING if diff > 1 else DECLINING if diff < -1 else STEADY
        label = CATEGORY_LABELS.get(cat, cat)
        bx = label_w + pad
        parts.append(
            f'<text x="{label_w}" y="{mid:.0f}" text-anchor="end" '
            f'dominant-baseline="central" font-size="12" fill="#16181d">'
            f"{html.escape(label)}</text>"
        )
        parts.append(
            f'<rect x="{bx}" y="{y + 6:.0f}" width="{bar_w:.1f}" '
            f'height="{row_h - 12}" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{bx + bar_w + 6:.1f}" y="{mid:.0f}" '
            f'dominant-baseline="central" font-size="11" fill="#5f6368">'
            f"{recent:.0f}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


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
        ("new signal", RISING),
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
        # A block earns sparklines if it reads like a momentum line — i.e. it
        # mentions a direction word. This is robust to formatting drift in the
        # brief (bold vs. "Trend:" vs. "Momentum:" lead-ins).
        low = plain.lower()
        if not any(w in low for w in ("rising", "declining", "steady", "early signal", "new signal")):
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


def metric_card(num, label, small=False):
    cls = "metric-num sm" if small else "metric-num"
    return (
        f'<div class="metric"><div class="{cls}">{html.escape(str(num))}</div>'
        f'<div class="metric-label">{html.escape(label)}</div></div>'
    )


def data_box(daterange, total, en, es, n_signals, mover):
    """The 'This Week's Data' card row shown after the So What line."""
    if total is None:
        articles_num, articles_label = "—", "Articles analyzed"
    else:
        articles_num = total
        articles_label = f"Articles · {en} EN / {es} ES"
    if mover:
        kw, pct = mover
        # pct is None when the keyword is newly appearing (no prior volume).
        mover_num = f"{pct:+.0f}%" if pct is not None else "New"
        mover_label = f"Top mover · {kw}"
    else:
        mover_num, mover_label = "—", "Top mover"
    cards = (
        metric_card(daterange, "Date range", small=True)
        + metric_card(len(KEYWORDS), "Keywords tracked")
        + metric_card(articles_num, articles_label)
        + metric_card(n_signals, "Signals identified")
        + metric_card(mover_num, mover_label)
    )
    return (
        '<section class="databox">'
        "<div class=\"databox-title\">This Week’s Data</div>"
        f'<div class="metrics">{cards}</div></section>'
    )


SO_WHAT_RE = re.compile(
    r"(<h2[^>]*>\s*So What This Week\s*</h2>\s*<p>.*?</p>)", re.DOTALL
)


def insert_after_so_what(body, snippet):
    """Insert HTML right after the So What paragraph.

    Falls back to placing it before the first signal heading, then to the
    top of the body, so the box always appears even if the brief's wording
    drifts.
    """
    if not snippet:
        return body
    if SO_WHAT_RE.search(body):
        return SO_WHAT_RE.sub(lambda m: m.group(1) + snippet, body, count=1)
    parts = re.split(r"(<h3)", body, maxsplit=1)
    if len(parts) == 3:
        return parts[0] + snippet + parts[1] + parts[2]
    return snippet + body


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

    # "This Week's Data" box + category momentum chart, slotted in after the
    # So What line and before the first signal.
    total, en, es = news_article_breakdown(date)
    mover = top_mover(series)
    box = data_box(extract_date_range(text, date), total, en, es, len(h3s), mover)

    cat_strength = category_strength(series)
    chart = ""
    if cat_strength:
        chart = (
            '<section class="catchart">'
            '<div class="catchart-title">Category Signal Strength '
            "&middot; avg recent search interest</div>"
            f"{category_bar_svg(cat_strength)}</section>"
        )
    body = insert_after_so_what(body, box + chart)

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
