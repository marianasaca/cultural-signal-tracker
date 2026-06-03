# Cultural Signal Tracker

A weekly cultural intelligence pipeline that monitors **US Hispanic consumer culture**. It pulls search-interest and news signals, has Google Gemini synthesize them into a strategist-ready brief, and publishes a browsable archive to GitHub Pages — automatically, every Monday.

**Live archive:** https://marianasaca.github.io/cultural-signal-tracker/

## How it works

```
Google Trends ─┐
               ├─► Gemini synthesis ─► weekly markdown brief ─► HTML archive (GitHub Pages)
NewsAPI (EN+ES)┘
```

1. **`collect_trends.py`** — relative US search interest (0–100) over the last 3 months for a set of Hispanic-culture keywords (via `pytrends`). Saved to `data/trends_<date>.csv`.
2. **`collect_news.py`** — last 7 days of articles in **English and Spanish** for each topic category (via NewsAPI). Saved to `data/news_<date>.json`.
3. **`synthesize.py`** — sends both sources to **Gemini (`gemini-2.5-flash`)** with a tuned cultural-analyst prompt and writes `outputs/brief_<date>.md`.
4. **`build_site.py`** — renders every brief in `outputs/` into a styled, browsable `site/` (newest first).
5. **`.github/workflows/weekly.yml`** — runs the whole pipeline on a schedule and deploys `site/` to GitHub Pages.

Topic categories and keywords are shared across both collectors in **`categories.py`** so the two data sources stay aligned.

## Setup

Requires Python 3.11+.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root (it is git-ignored — never commit it):

```
NEWSAPI_KEY=your_newsapi_key
GEMINI_API_KEY=your_gemini_key
```

- NewsAPI key (free Developer plan): https://newsapi.org
- Gemini key (free tier): https://aistudio.google.com/apikey

## Run it locally

```bash
python collect_trends.py    # writes data/trends_<date>.csv
python collect_news.py      # writes data/news_<date>.json
python synthesize.py        # writes outputs/brief_<date>.md
python build_site.py        # writes site/index.html + one page per brief
```

`synthesize.py` always needs a news file; the trends file is optional — if it's missing (e.g. Google rate-limited the run), it produces a news-only brief.

## Automated weekly runs

GitHub Actions runs the full pipeline **every Monday at 08:00 UTC** (and on-demand via the Actions tab), commits the new brief, and republishes the Pages archive.

To run it in your own fork:

1. Add repository secrets `NEWSAPI_KEY` and `GEMINI_API_KEY` (Settings → Secrets and variables → Actions).
2. Set **Settings → Pages → Source → "GitHub Actions"**.
3. Trigger a first run from the Actions tab.

## Cost

Everything runs on free tiers: Google Trends (no key), NewsAPI Developer plan, the Gemini free tier, and GitHub Actions/Pages (free for public repos). These are usage limits, not bills — going over rejects requests rather than charging you.

## Notes

- **`pytrends` is unreliable from CI runners** — Google rate-limits datacenter IPs, so some weeks the Trends step fails and the brief is news-only. This is expected and non-fatal.
- Raw pulls (`data/`) and the generated `site/` are git-ignored; only the markdown briefs in `outputs/` are committed.
