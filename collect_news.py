"""NewsAPI collector for the Cultural Signal Tracker.

For each topic category, runs a broad boolean query in both English and
Spanish against NewsAPI's /v2/everything endpoint, pulling articles from
the last 7 days. Raw results are saved to a timestamped JSON file in data/,
grouped by category and language.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from categories import KEYWORDS_BY_CATEGORY

# --- Configuration you can edit ------------------------------------------

DAYS_BACK = 7              # how far back to pull articles
LANGUAGES = ["en", "es"]  # pull each category in English and Spanish
SORT_BY = "publishedAt"   # newest first; alternatives: "relevancy", "popularity"
PAGE_SIZE = 100           # max articles per request on the free plan
PAUSE_SECONDS = 1         # small pause between requests to be polite

# Broad boolean queries per category, in English and Spanish.
# NOTE on syntax: NewsAPI binds AND tighter than OR, so OR-groups are
# wrapped in parentheses to force (A OR B) AND (C OR D) grouping.
# Quotes are used only on genuine multi-word concept phrases.
NEWS_QUERIES = {
    "economic_resilience": {
        "en": '(Hispanic OR Latino) AND (inflation OR budget OR savings OR grocery OR "cost of living" OR "economic pressure")',
        "es": '(hispanos OR latinos) AND (inflación OR presupuesto OR ahorro OR supermercado OR "costo de vida" OR "presión económica")',
    },
    "bicultural_fusion": {
        "en": '(Hispanic OR Latino) AND ("Gen Z" OR beauty OR TikTok OR wellness OR bilingual OR "lifestyle trends")',
        "es": '(hispanos OR latinos) AND ("Generación Z" OR belleza OR TikTok OR bienestar OR bilingüe OR "tendencias de estilo de vida")',
    },
    "heritage_milestones": {
        "en": '(Hispanic OR Latino) AND (holiday OR celebration OR heritage OR tradition OR family OR quinceañera OR "Day of the Dead")',
        "es": '(hispanos OR latinos) AND (festividad OR celebración OR herencia OR tradición OR familia OR quinceañera OR "Día de los Muertos")',
    },
}

NEWS_ENDPOINT = "https://newsapi.org/v2/everything"
OUTPUT_DIR = Path(__file__).parent / "data"

# Keep the news categories aligned with the shared category list.
assert set(NEWS_QUERIES) == set(KEYWORDS_BY_CATEGORY), (
    "NEWS_QUERIES categories must match categories.py"
)

# -------------------------------------------------------------------------


def fetch(api_key, query, language, date_from, date_to):
    """Fetch one query/language. Returns the parsed JSON response."""
    params = {
        "q": query,
        "from": date_from,
        "to": date_to,
        "language": language,
        "sortBy": SORT_BY,
        "pageSize": PAGE_SIZE,
        "apiKey": api_key,
    }
    resp = requests.get(NEWS_ENDPOINT, params=params, timeout=30)
    return resp.json()


def main():
    load_dotenv()  # reads .env in this folder
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        print("ERROR: NEWSAPI_KEY not found. Is it set in your .env file?")
        return

    now = datetime.now(timezone.utc)
    date_to = now.strftime("%Y-%m-%d")
    date_from = (now - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")

    print(f"Collecting news {date_from} -> {date_to} for "
          f"{len(NEWS_QUERIES)} categories x {len(LANGUAGES)} languages...")

    results = {
        "collected_at": now.isoformat(),
        "window": {"from": date_from, "to": date_to},
        "languages": LANGUAGES,
        "categories": {},
    }

    for category, queries in NEWS_QUERIES.items():
        print(f"\n{category}:")
        results["categories"][category] = {}

        for language in LANGUAGES:
            query = queries[language]
            print(f"  [{language}] {query}")
            data = fetch(api_key, query, language, date_from, date_to)

            if data.get("status") != "ok":
                # Common codes: rateLimited, apiKeyInvalid, parameterInvalid.
                print(f"      NewsAPI error: {data.get('code')} - "
                      f"{data.get('message')}")
                results["categories"][category][language] = {
                    "query": query,
                    "error": data,
                }
                continue

            articles = data.get("articles", [])
            print(f"      {data.get('totalResults', 0)} total results, "
                  f"{len(articles)} fetched")
            results["categories"][category][language] = {
                "query": query,
                "totalResults": data.get("totalResults", 0),
                "fetched": len(articles),
                "articles": articles,
            }
            time.sleep(PAUSE_SECONDS)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"news_{date_to}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Tally totals overall and per language.
    total = 0
    per_lang = {lang: 0 for lang in LANGUAGES}
    for cat in results["categories"].values():
        for lang, block in cat.items():
            n = block.get("fetched", 0)
            total += n
            per_lang[lang] = per_lang.get(lang, 0) + n

    lang_summary = ", ".join(f"{lang}={per_lang[lang]}" for lang in LANGUAGES)
    print(f"\nSaved {total} articles ({lang_summary}) across "
          f"{len(results['categories'])} categories -> {out_path}")


if __name__ == "__main__":
    main()
