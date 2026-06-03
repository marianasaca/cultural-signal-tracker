"""Shared topic categories for the Cultural Signal Tracker.

Both the Google Trends collector and the NewsAPI collector import these,
so the two data sources stay aligned on the same categories/keywords.
"""

KEYWORDS_BY_CATEGORY = {
    "consumer_behavior": [
        "Hispanic shoppers",
        "Latino consumers",
        "Hispanic grocery",
        "Latino beauty",
        "Hispanic food brands",
        "remittances USA",
    ],
    "cultural_identity": [
        "Latino identity",
        "Hispanic culture USA",
        "Spanglish",
        "bicultural",
    ],
    "marketing_media": [
        "multicultural marketing",
        "Hispanic advertising",
        "bilingual ads",
        "Latino influencer",
    ],
    "tentpole_moments": [
        "World Cup 2026 marketing",
        "World Cup 2026 Hispanic",
        "World Cup 2026 Latino fans",
        "Hispanic Heritage Month",
        "Dia de los Muertos",
        "quinceañera",
    ],
    "retail_relevant": [
        "Hispanic household products",
        "Latino shopping habits",
        "bodega culture",
    ],
}

# Lookup from keyword -> category, and a flat list of every keyword.
KEYWORD_TO_CATEGORY = {
    kw: category
    for category, kws in KEYWORDS_BY_CATEGORY.items()
    for kw in kws
}
KEYWORDS = list(KEYWORD_TO_CATEGORY.keys())
