"""Stage 3: Claude synthesis layer for the Cultural Signal Tracker.

Loads the two raw data sources collected earlier — the Google Trends CSV
and the NewsAPI JSON (English + Spanish) — formats them into a single
prompt, and asks Claude to write a weekly cultural insights brief. The
brief is saved as markdown in outputs/.
"""

import glob
import json
from datetime import datetime
from pathlib import Path

import os

import pandas as pd
from google import genai
from google.genai import types
from dotenv import load_dotenv

# --- Configuration you can edit ------------------------------------------

MODEL = "gemini-2.5-flash"
MAX_TOKENS = 8000
RECENT_WEEKS = 4  # how many trailing weeks count as "recent" for momentum

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

SYSTEM_PROMPT = (
    "You are the cultural intelligence director at a multicultural advertising "
    "agency. You work on the Walmart and GSK accounts and you present to CMOs. "
    "Write the way you'd explain this to a strategy director over coffee: "
    "sharp, specific, conversational, no filler. Short sentences. Every "
    "sentence earns its place — if it adds no new information, cut it.\n\n"
    "You receive two data sources: Google Trends (relative US search interest "
    "0-100, with a recent 4-week average and a prior average per keyword) and "
    "recent news articles about Hispanic/Latino culture, consumers, and "
    "marketing.\n\n"
    "HARD RULES:\n"
    "- Filter noise. Ignore articles that aren't genuinely about Hispanic/"
    "Latino consumer culture, identity, or marketing (gaming, general politics "
    "that only mentions Latino voters in passing, etc.).\n"
    "- BANNED PHRASES — never use any of these or a close variant: 'takes "
    "center stage,' 'ripe for disruption,' 'lead the charge,' 'curate "
    "experiences,' 'game-changer,' 'tap into,' 'leverage,' 'landscape,' "
    "'dynamic,' 'robust,' 'foster,' 'elevate,' 'deep dive,' 'actionable,' "
    "'it's time to,' 'the power of,' 'beyond just,' 'more than just,' and the "
    "'don't just X, do Y' construction. If a sentence reads like marketing "
    "copy, rewrite it in plain English.\n"
    "- Keep the whole brief to roughly 60-70% of a typical verbose brief. Cut "
    "ruthlessly.\n\n"
    "MOMENTUM SCORES:\n"
    "  - If the recent 4-week average is 5 or above, use the actual percentage "
    "change from the trends averages, formatted like 'Rising +150% (4wk avg "
    "11.0 vs prior 4.4).'\n"
    "  - If the recent 4-week average is below 5, do NOT show a percentage — "
    "it would be misleading off such low volume. Instead label it 'Early "
    "signal' and format like 'Early signal — low volume but newly appearing "
    "(4wk avg 0.8 vs prior 0.1).' Reserve the big percentage callouts for "
    "keywords with real volume behind them.\n\n"
    "RECOMMENDATIONS: every recommendation must name a specific example from "
    "the data — a named brand, campaign, article, or trend number — and tell a "
    "specific type of brand (a CPG brand, a retailer, an agency) exactly what "
    "to do and why. Never write 'brands should consider.' Say who does what.\n"
    "  - Keep GSK recommendations grounded in what GSK actually sells: OTC "
    "health, oral care, and vitamins (e.g. Advil, Sensodyne, Centrum). If a "
    "signal has no natural fit for those products, say so plainly — note it's "
    "more relevant to retail or CPG food brands — and skip GSK for that "
    "signal. Don't force a GSK angle where it doesn't belong.\n\n"
    "SOURCE LINKS: every time you cite a news article, render the source name "
    "as a markdown link to that article's URL, formatted exactly like "
    "'[PRNewswire](https://www.prnewswire.com/...)'. Use the exact URL given "
    "after 'URL:' for that article in the news data — never invent or guess a "
    "URL. Every cited article must have a clickable source link. If an article "
    "has no URL in the data, name the source in plain text without a link.\n\n"
    "Output a markdown brief in this exact order:\n"
    "1. An H1 markdown heading — the line must start with '# ': "
    "'# Weekly Cultural Signal Report: US Hispanic Consumer Culture'. Put the "
    "date range on the next line.\n"
    "2. '## So What This Week' — ONE punchy sentence, 25 words max. It must say "
    "what is DIFFERENT about THIS week specifically, anchored to the single "
    "biggest data point in this week's pull (the largest momentum move or the "
    "most notable news story). Not an evergreen truth about Hispanic consumers "
    "— write it like a headline a reporter would file about this week's data.\n"
    "3. The top 3-5 cultural signals. Each: a name, a momentum score, a tight "
    "explanation, evidence from both sources, and recommendations per the rule "
    "above.\n"
    "4. '## Category Gaps & Observations' — note quiet categories and why "
    "(e.g. seasonality); dormancy is itself a signal.\n"
    "5. '## Signal to Watch' — 3-4 sentences max. Name the signal, cite the "
    "evidence, say why it matters. Then stop."
)

# -------------------------------------------------------------------------


def latest_file(pattern):
    """Return the most recent file in data/ matching a glob pattern."""
    matches = sorted(DATA_DIR.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No files matching {pattern} in {DATA_DIR}")
    return matches[-1]


def momentum_label(recent_avg, earlier_avg):
    """Classify a keyword's trajectory from recent vs earlier average."""
    if earlier_avg == 0:
        return "rising" if recent_avg > 0 else "flat (no signal)"
    change = (recent_avg - earlier_avg) / earlier_avg
    if change > 0.15:
        return "rising"
    if change < -0.15:
        return "declining"
    return "steady"


def format_trends(csv_path):
    """Condense the long trends CSV into a per-keyword momentum summary.

    The raw CSV has one row per keyword per date (~weeks of history). For
    the brief we don't need every point — we need each keyword's current
    level and trajectory. So per keyword we compute latest interest, peak,
    the recent-N-weeks average vs the earlier average, and a momentum label.
    """
    df = pd.read_csv(csv_path, parse_dates=["date"])
    dates = sorted(df["date"].unique())
    recent_cutoff = dates[-RECENT_WEEKS] if len(dates) >= RECENT_WEEKS else dates[0]

    lines = []
    for category, cat_df in df.groupby("category"):
        lines.append(f"\n### {category}")
        for keyword, kw_df in cat_df.groupby("keyword"):
            kw_df = kw_df.sort_values("date")
            latest = kw_df.iloc[-1]["interest"]
            peak = kw_df["interest"].max()
            recent_avg = kw_df[kw_df["date"] >= recent_cutoff]["interest"].mean()
            earlier_avg = kw_df[kw_df["date"] < recent_cutoff]["interest"].mean()
            earlier_avg = 0 if pd.isna(earlier_avg) else earlier_avg
            label = momentum_label(recent_avg, earlier_avg)
            lines.append(
                f"- {keyword}: latest={latest:.0f}, peak={peak:.0f}, "
                f"recent {RECENT_WEEKS}wk avg={recent_avg:.1f}, "
                f"earlier avg={earlier_avg:.1f} -> {label}"
            )
    return "\n".join(lines)


def format_news(json_path):
    """Render the news JSON into readable per-category, per-language blocks."""
    with open(json_path, encoding="utf-8") as f:
        news = json.load(f)

    lines = [f"News window: {news['window']['from']} to {news['window']['to']}"]
    for category, langs in news["categories"].items():
        lines.append(f"\n### {category}")
        for lang, block in langs.items():
            if "error" in block:
                lines.append(f"  [{lang}] query errored: {block['error']}")
                continue
            lines.append(
                f"  [{lang}] query: {block['query']} "
                f"({block['totalResults']} total, {block['fetched']} fetched)"
            )
            for art in block["articles"]:
                title = (art.get("title") or "").strip()
                source = (art.get("source") or {}).get("name", "?")
                published = (art.get("publishedAt") or "")[:10]
                desc = (art.get("description") or "").strip()
                url = (art.get("url") or "").strip()
                lines.append(f"    - {title} ({source}, {published})")
                if url:
                    lines.append(f"      URL: {url}")
                if desc:
                    lines.append(f"      {desc}")
    return "\n".join(lines)


def main():
    load_dotenv()  # lets GEMINI_API_KEY live in .env if you prefer
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found. Set it in your .env file.")
        return

    # News is required; Trends is best-effort (it's often rate-limited when
    # the pipeline runs from a datacenter IP, e.g. GitHub Actions). If the
    # Trends pull produced no file this run, we still ship a news-only brief.
    news_path = latest_file("news_*.json")
    print(f"News source:   {news_path.name}")
    try:
        trends_path = latest_file("trends_*.csv")
        print(f"Trends source: {trends_path.name}")
        trends_block = format_trends(trends_path)
    except FileNotFoundError:
        print("Trends source: NONE — continuing with a news-only brief")
        trends_block = "(Google Trends data was unavailable for this run.)"

    news_block = format_news(news_path)

    # Derive the reporting date range from the news window.
    with open(news_path, encoding="utf-8") as f:
        window = json.load(f)["window"]
    date_range = f"{window['from']} to {window['to']}"

    user_content = (
        f"Reporting date range: {date_range}\n\n"
        "=== GOOGLE TRENDS (relative search interest 0-100, US) ===\n"
        "Momentum is recent vs earlier average for each keyword.\n"
        f"{trends_block}\n\n"
        "=== NEWS ARTICLES (last 7 days, English + Spanish) ===\n"
        f"{news_block}\n"
    )

    print(f"\nCalling {MODEL}...")
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=MAX_TOKENS,
        ),
    )

    brief = resp.text

    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    out_path = OUTPUT_DIR / f"brief_{stamp}.md"
    out_path.write_text(brief, encoding="utf-8")

    usage = resp.usage_metadata
    print(f"\nSaved brief -> {out_path}")
    print(f"  ({len(brief)} characters, "
          f"{usage.prompt_token_count} input / "
          f"{usage.candidates_token_count} output tokens)")


if __name__ == "__main__":
    main()
