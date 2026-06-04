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
RECENT_DAYS = 28  # trailing window that counts as "recent" (4 weeks of daily data)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

SYSTEM_PROMPT = (
    "You are a cultural intelligence director who tracks US Hispanic consumer "
    "culture. You present to brand and agency strategists. "
    "Write the way you'd explain this to a strategy director over coffee: "
    "sharp, specific, conversational, no filler. Short sentences. Every "
    "sentence earns its place — if it adds no new information, cut it.\n\n"
    "You receive two data sources: Google Trends (relative US search interest "
    "0-100, with a recent 4-week average and a prior average per keyword) and "
    "recent news articles about Hispanic/Latino culture, consumers, and "
    "marketing.\n\n"
    "STRATEGIC PILLARS: the keywords are organized into three pillars that "
    "frame how to read the US Hispanic consumer. Anchor your "
    "signals and recommendations to these:\n"
    "  1. Economic Resilience — how households stretch budgets, optimize "
    "income, and contain non-discretionary costs (bulk buying, private "
    "label, fee-free remittances, gig income, downsizing).\n"
    "  2. Bicultural Fusion — how younger, bicultural consumers blend "
    "American trends with heritage across food, beauty, wellness, tech, "
    "and lifestyle.\n"
    "  3. Heritage & Milestones — celebrations, religious milestones, and "
    "seasonal family moments that drive predictable retail demand.\n\n"
    "HARD RULES:\n"
    "- Filter noise. Ignore articles that aren't genuinely about Hispanic/"
    "Latino consumer culture, identity, or marketing (gaming, general politics "
    "that only mentions Latino voters in passing, etc.).\n"
    "- Exclude news articles about individual celebrities' personal lives — "
    "divorces, family drama, red carpet appearances, social media posts. A "
    "gossip article that happens to mention a Latino person is NOT a cultural "
    "signal. Only include celebrity news if the article specifically discusses "
    "a consumer trend, marketing campaign, or cultural shift.\n"
    "- BANNED PHRASES — never use any of these or a close variant: 'takes "
    "center stage,' 'ripe for disruption,' 'lead the charge,' 'curate "
    "experiences,' 'game-changer,' 'tap into,' 'leverage,' 'landscape,' "
    "'dynamic,' 'robust,' 'foster,' 'elevate,' 'deep dive,' 'actionable,' "
    "'it's time to,' 'the power of,' 'beyond just,' 'more than just,' and the "
    "'don't just X, do Y' construction. If a sentence reads like marketing "
    "copy, rewrite it in plain English.\n"
    "- If a heritage or milestone keyword spikes outside its expected season "
    "by more than 3 months (for example Rosca de Reyes trending in June, or "
    "Day of the Dead makeup trending in March), flag it as an anomaly worth "
    "investigating rather than presenting it as a confirmed seasonal trend. "
    "Say something like 'This is unusual for this time of year and may reflect "
    "a data artifact or an emerging off-season interest — worth watching.'\n"
    "- Keep the whole brief to roughly 60-70% of a typical verbose brief. Cut "
    "ruthlessly.\n\n"
    "MOMENTUM SCORES:\n"
    "  - If the prior/earlier average is 0.0 and the recent average is above "
    "zero, do NOT show a percentage (it would be infinite/division-by-zero). "
    "Instead label it 'New signal — not previously tracked' and format like "
    "'New signal — not previously tracked (4wk avg 3.6).' This takes priority "
    "over the rules below.\n"
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
    "specific SECTOR (retailers, CPG food brands, beauty brands, financial "
    "services, QSR, consumer electronics, etc.) exactly what to do and why. "
    "Stay opinionated and concrete, but address sectors, never individual "
    "companies — don't name a particular retailer or brand as the one that "
    "should act. Never write 'brands should consider.' Say which sector does "
    "what. If a signal has no natural fit for a given sector, don't force one "
    "— name the sector it actually serves and move on.\n"
    "  - FORMAT: write the recommendations as a markdown bullet list — one "
    "bullet per sector, each bullet starting with the sector name in bold "
    "followed by a colon, like '- **Retailers:** ...'. Put each sector on "
    "its own bullet. Never run multiple recommendations together as a single "
    "paragraph.\n\n"
    "SOURCE LINKS: every time you cite a news article, render the source name "
    "as a markdown link to that article's URL, formatted exactly like "
    "'[PRNewswire](https://www.prnewswire.com/...)'. Use the exact URL given "
    "after 'URL:' for that article in the news data — never invent or guess a "
    "URL. Every cited article must have a clickable source link. If an article "
    "has no URL in the data, name the source in plain text without a link.\n\n"
    "SIGNAL CODEBOOK: use this to interpret what a rise or fall in each "
    "keyword means. A spike signals growing intent in that direction; a "
    "decline signals the opposite. Don't just report numbers — explain what "
    "the movement means for the consumer, using these readings.\n\n"
    "Economic Resilience:\n"
    "  - articulos de limpieza por galon: Shift to extreme bulk purchasing "
    "for household cleaning\n"
    "  - cupones de walmart digitales: Budget consciousness and active "
    "search for savings\n"
    "  - marca equate opiniones: Value-tier brand migration; swapping "
    "national brands for private labels\n"
    "  - envio de dinero sin comision: Income optimization; prioritizing "
    "low fees over brand loyalty\n"
    "  - walmart cash back policy: Liquidity signal; using retail checkouts "
    "as ATM alternatives\n"
    "  - comida congelada barata: Time-poverty or budget strain; shifting "
    "from fresh cooking to convenience\n"
    "  - llantas usadas cerca de mi: Extreme cost-containment in automotive "
    "maintenance\n"
    "  - financiamiento de muebles sin credito: High-intent asset "
    "acquisition bypassing traditional credit\n"
    "  - precio del huevo por caja: Basic food staple inflation sentiment\n"
    "  - walmart delivery free trial: Testing digital ecosystem entry "
    "points to save on transit costs\n"
    "  - apartamentos de un solo cuarto: Downsizing or co-living shifts due "
    "to housing pressure\n"
    "  - aplicaciones para ganar dinero facil: Gig-economy interest during "
    "wage stagnation\n"
    "  - seguro de auto mas barato: Non-discretionary cost optimization\n"
    "  - herramientas hyper tough: Tracking Walmart's lowest-priced opening "
    "price point tool brand\n"
    "  - articulos de bebe usados: Secondary market reliance for "
    "high-velocity infant goods\n"
    "  - gasolinera mas barata cerca de mi: Immediate response to "
    "fluctuating energy costs\n"
    "  - reparar pantalla de telefono precio: Extending tech lifecycle over "
    "purchasing new\n"
    "  - tarjeta de debito para niños: Financial literacy push within "
    "unbanked or newly banked households\n"
    "  - renta con todo incluido: Predictive budgeting; avoiding variable "
    "utility cost spikes\n"
    "  - presupuesto mensual excel gratis: Proactive financial planning "
    "intent\n\n"
    "Bicultural Fusion:\n"
    "  - air fryer platanos maduros: Adapting modern kitchen tech to "
    "heritage comfort foods\n"
    "  - makeup routines for latina skin: High-intent beauty search "
    "filtering for specific undertones\n"
    "  - dupe de perfumes en walmart: Social-media-driven smart shopping; "
    "beauty trend awareness\n"
    "  - tacos de birria slow cooker: Modern convenience meets traditional "
    "cuisine\n"
    "  - best Hispanic creators on tiktok: Media consumption tracking; "
    "identifying retail influencers\n"
    "  - sneaker drops walmart: Gen Z streetwear culture overlapping with "
    "mass retail\n"
    "  - organic baby food brands: Premiumization shifts among millennial "
    "parents\n"
    "  - recetas de cocteles con mezcal: Crossover beverage trends; upscale "
    "spirits going mainstream\n"
    "  - smart home devices cheap: Tech adoption baseline; upgrading "
    "high-density households\n"
    "  - protein powder para mujeres: Wellness and fitness prioritization\n"
    "  - iced coffee en casa facil: Shifting from premium café spend to DIY "
    "beverages\n"
    "  - curled hair tutorials latinas: Hyper-specific haircare driving "
    "textured hair product demand\n"
    "  - gaming setup ideas: High gaming subculture index among young "
    "Latinos\n"
    "  - sustainable clothing brands online: Eco-conscious sentiment among "
    "younger shoppers\n"
    "  - keto diet alternatives spanish: Merging American health trends "
    "with Latin diet context\n"
    "  - best budget soundbar for tv: Home entertainment upgrades tied to "
    "communal viewing\n"
    "  - skincare minimalista pasos: Shift toward streamlined premium "
    "personal care\n"
    "  - vlog de estilo de vida: Peer-to-peer inspiration for lifestyle "
    "choices\n"
    "  - smartwatch fitness tracking cheap: Digital health tech adoption at "
    "value pricing\n"
    "  - diy dorm room decor ideas: First-generation college demographic "
    "styling new spaces\n\n"
    "Heritage & Milestones:\n"
    "  - dulces para piñata por mayoreo: Family party planning; seasonal "
    "confectionary demand\n"
    "  - decoracion de mesa para boda civil: Intimate celebration planning; "
    "budget-chic decor demand\n"
    "  - traje de bautizo para niño walmart: Milestone religious retail; "
    "formal apparel search\n"
    "  - regalos de graduacion universitaria: Generational milestone "
    "celebration; high emotional spend\n"
    "  - receta de tamales de puerco: Early Q4 indicator for holiday food "
    "supply chains\n"
    "  - adornos para el dia de la madre: Q2 holiday preparation; floral "
    "and gifting runway\n"
    "  - rosca de reyes walmart: Seasonal activation for early January "
    "bakery items\n"
    "  - vestidos de fiesta largos baratos: Social calendar intensity; "
    "affordable formalwear demand\n"
    "  - velas de la virgen de guadalupe: Spiritual baseline; year-round "
    "volume peaking early December\n"
    "  - comida para baby shower moderna: Family expansion; contemporary "
    "catering and hosting\n"
    "  - trajes tipicos de mexico: Cultural festival and Heritage Month "
    "demand\n"
    "  - regalos para el dia del padre: Family celebration tracking; "
    "elastic seasonal spend\n"
    "  - musica para año nuevo bailable: Multi-generational family hosting "
    "and entertainment\n"
    "  - comida tipica de nochebuena: Christmas Eve feast prep; out-indexes "
    "Dec 25 terms\n"
    "  - arreglos de globos sencillos: DIY celebration culture; anchors "
    "celebratory retail\n"
    "  - manteles de mesa elegantes: Communal hosting prep for extended "
    "family gatherings\n"
    "  - receta de flan casero cremoso: Heritage dessert baking; grocery "
    "dairy aisle signal\n"
    "  - recuerdos para primera comunion: Party favors and crafting demand "
    "for religious milestones\n"
    "  - maletas de mano para viajar: International family reunification "
    "travel intent\n"
    "  - disfraces de halloween familiares: Group/family seasonal purchases "
    "over individual costumes\n\n"
    "Output a markdown brief in this exact order:\n"
    "1. An H1 markdown heading — the line must start with '# ': "
    "'# Weekly Cultural Signal Report: US Hispanic Consumer Culture'. Put the "
    "date range on the next line.\n"
    "2. '## So What This Week' — ONE punchy sentence, 25 words max. The So What "
    "must be ONE specific insight — not two or three things joined with 'while' "
    "or 'and.' Pick the single most important signal from this week's data and "
    "write it as a sharp, specific sentence that a CMO would stop scrolling to "
    "read. Reference a specific number. Bad example: 'Consumers face economic "
    "pressure while engaging with celebrations and tech.' Good example: 'Egg "
    "price searches up 80% as a new report shows 13M Hispanics face food "
    "insecurity — belt-tightening is accelerating.' Not an evergreen truth "
    "about Hispanic consumers — write it like a headline a reporter would file "
    "about this week's data.\n"
    "3. The top 3-5 cultural signals. Render EACH signal's name as its own H3 "
    "markdown heading — a line that starts with '### '. Under each heading "
    "put: a momentum score, a tight explanation, evidence from both sources, "
    "and recommendations per the rule above. Do not group multiple signals "
    "under one heading or use bold text in place of an H3 heading.\n"
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
        # No prior baseline — a percentage would be infinite/division-by-zero,
        # so call it a brand-new signal rather than fabricating a number.
        return "new signal (not previously tracked)" if recent_avg > 0 else "flat (no signal)"
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
    recent_cutoff = dates[-RECENT_DAYS] if len(dates) >= RECENT_DAYS else dates[0]

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
                f"recent 4wk avg={recent_avg:.1f}, "
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
            # gemini-2.5-flash "thinks" by default, and those thinking tokens
            # count against max_output_tokens. With this large prompt that can
            # eat the whole budget and truncate the brief, so we disable it —
            # this is a deterministic writing task that doesn't need it.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
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
