"""Google Trends collector for the Cultural Signal Tracker.

Pulls relative search interest (0-100) for a list of Hispanic-culture
keywords in the US, then saves the result to a timestamped CSV.
"""

import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError

from categories import KEYWORDS, KEYWORD_TO_CATEGORY

# --- Configuration you can edit ------------------------------------------

GEO = "US"               # United States
TIMEFRAME = "today 3-m"  # last 3 months
BATCH_SIZE = 5           # Google Trends allows max 5 keywords per request
PAUSE_SECONDS = 2        # small pause between batches to avoid rate limits

OUTPUT_DIR = Path(__file__).parent / "data"

# -------------------------------------------------------------------------


def chunk(items, size):
    """Yield successive `size`-length chunks from a list."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

MAX_RETRIES = 4  # how many times to retry a batch on a 429 before giving up


def fetch_one_batch(pytrends, batch):
    """Fetch a single batch, retrying with growing pauses on a 429."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            pytrends.build_payload(batch, geo=GEO, timeframe=TIMEFRAME)
            return pytrends.interest_over_time()
        except TooManyRequestsError:
            wait = PAUSE_SECONDS * (2 ** attempt)  # 4, 8, 16, 32 seconds...
            print(f"    Rate-limited (429). Attempt {attempt}/{MAX_RETRIES}, "
                  f"waiting {wait}s before retry...")
            time.sleep(wait)
    print("    Gave up on this batch after repeated 429s.")
    return None


def fetch_interest(keywords):
    """Return a DataFrame of interest-over-time for up to 5 keywords."""
    # NOTE: we deliberately do NOT pass retries/backoff_factor here.
    # pytrends 4.9.2's built-in retry uses urllib3's removed `method_whitelist`
    # arg, which crashes under urllib3 2.x. We do our own retries in
    # fetch_one_batch instead. requests_args headers make us look like a browser.
    pytrends = TrendReq(
        hl="en-US",
        tz=360,
        timeout=(10, 25),
        requests_args={"headers": BROWSER_HEADERS},
    )
    frames = []

    for batch in chunk(keywords, BATCH_SIZE):
        print(f"  Fetching batch: {batch}")
        df = fetch_one_batch(pytrends, batch)

        if df is None or df.empty:
            print("    (no data returned for this batch)")
            continue

        # Drop the 'isPartial' helper column Google adds.
        if "isPartial" in df.columns:
            df = df.drop(columns=["isPartial"])

        frames.append(df)
        time.sleep(PAUSE_SECONDS)

    if not frames:
        return pd.DataFrame()

    # Join all batches side by side on the shared date index.
    return pd.concat(frames, axis=1)


def main():
    print(f"Collecting Google Trends data for {len(KEYWORDS)} keywords "
          f"({GEO}, {TIMEFRAME})...")

    data = fetch_interest(KEYWORDS)

    if data.empty:
        print("No data collected. Try again in a bit (possible rate limit).")
        return

    # Reshape from wide (one column per keyword) to long/tidy format:
    # date | category | keyword | interest. This keeps the category label
    # attached to every data point for easy grouping later.
    long_df = (
        data.reset_index()
        .melt(id_vars="date", var_name="keyword", value_name="interest")
    )
    long_df["category"] = long_df["keyword"].map(KEYWORD_TO_CATEGORY)
    long_df = long_df[["date", "category", "keyword", "interest"]]
    long_df = long_df.sort_values(["category", "keyword", "date"])

    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    out_path = OUTPUT_DIR / f"trends_{stamp}.csv"
    long_df.to_csv(out_path, index=False)

    n_dates = long_df["date"].nunique()
    n_keywords = long_df["keyword"].nunique()
    print(f"\nSaved {len(long_df)} rows ({n_keywords} keywords x {n_dates} dates) "
          f"-> {out_path}")
    print("\nLatest interest score per keyword (by category):")
    latest_date = long_df["date"].max()
    latest = long_df[long_df["date"] == latest_date]
    print(latest[["category", "keyword", "interest"]].to_string(index=False))


if __name__ == "__main__":
    main()
