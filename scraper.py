"""
Data acquisition layer — runs BEFORE any LLM agent.
Provides grounded, real-world data so agents extract/analyse rather than recall.

Sources (in priority order):
  1. Official website scrape (httpx + BeautifulSoup)
  2. Wikipedia REST API (free, no rate limit, excellent for known companies)
  3. DuckDuckGo Instant Answer API (free, structured summary)
  4. DDGS web/news search
  5. yfinance for public-company financials
"""

import re
import os
import time
import json
from typing import Optional, Dict, Any, List
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

try:
    from ddgs import DDGS
    DDG_OK = True
except ImportError:
    try:
        from duckduckgo_search import DDGS  # legacy fallback
        DDG_OK = True
    except ImportError:
        DDG_OK = False
        print("WARNING: ddgs not installed — pip install ddgs")

try:
    import yfinance as yf
    YF_OK = True
except ImportError:
    YF_OK = False
    print("WARNING: yfinance not installed — pip install yfinance")

# ── Constants ─────────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

EXCLUDED_DOMAINS = {
    "linkedin.com", "wikipedia.org", "crunchbase.com", "glassdoor.com",
    "bloomberg.com", "reuters.com", "twitter.com", "facebook.com",
    "instagram.com", "youtube.com", "reddit.com", "owler.com",
    "zoominfo.com", "dnb.com", "fortune.com", "forbes.com",
}

SCRAPE_TIMEOUT = 15
MAX_CHARS_PAGE = 2000   # stored raw; trimmed to budget at format time
MAX_PAGES      = 3
DDG_DELAY      = 2.0   # seconds between DDG requests


# ── HTML utilities ─────────────────────────────────────────────────────────────
def _clean_html(html: str, max_chars: int = MAX_CHARS_PAGE) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "aside",
                     "noscript", "iframe", "svg", "form", "header"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _base_url(url: str) -> str:
    m = re.match(r"(https?://[^/]+)", url)
    return m.group(1) if m else url


def _is_excluded(url: str) -> bool:
    domain = re.sub(r"^https?://", "", url).split("/")[0].lower()
    return any(ex in domain for ex in EXCLUDED_DOMAINS)


# ── DDG safe wrapper ──────────────────────────────────────────────────────────
def _ddg_text(query: str, max_results: int = 6) -> List[Dict]:
    """Single DDG text search with retry on rate-limit."""
    if not DDG_OK:
        return []
    for attempt in range(2):
        try:
            with DDGS() as ddg:
                results = ddg.text(query, max_results=max_results)
                return list(results) if results else []
        except Exception as e:
            msg = str(e).lower()
            if "ratelimit" in msg or "429" in msg or "403" in msg:
                wait = 5 + attempt * 5
                print(f"[scraper] DDG rate-limit on text search, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"[scraper] DDG text search failed: {e}")
                return []
    return []


def _ddg_news(query: str, max_results: int = 6) -> List[Dict]:
    """Single DDG news search — best-effort, not retried."""
    if not DDG_OK:
        return []
    try:
        with DDGS() as ddg:
            results = ddg.news(query, max_results=max_results)
            return list(results) if results else []
    except Exception as e:
        print(f"[scraper] DDG news search failed (non-critical): {e}")
        return []


# ── Wikipedia REST API (free, reliable) ───────────────────────────────────────
def get_wikipedia_summary(company_name: str) -> Dict[str, str]:
    """
    Fetch Wikipedia page summary via the free REST API.
    Returns dict with keys: title, description, extract, url.
    """
    name_variants = [
        company_name,
        company_name.replace(" ", "_"),
        company_name.split()[0] if " " in company_name else company_name,
    ]
    for variant in name_variants:
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote_plus(variant)}"
            with httpx.Client(timeout=8, follow_redirects=True) as c:
                r = c.get(url, headers={"Accept": "application/json"})
                if r.status_code == 200:
                    d = r.json()
                    if d.get("type") in ("standard", "disambiguation"):
                        return {
                            "title":       d.get("title", ""),
                            "description": d.get("description", ""),
                            "extract":     d.get("extract", "")[:1200],
                            "url":         d.get("content_urls", {}).get("desktop", {}).get("page", ""),
                        }
        except Exception:
            pass
    return {}


# ── DuckDuckGo Instant Answer (free, structured) ──────────────────────────────
def get_ddg_instant(company_name: str) -> Dict[str, str]:
    """
    Fetch DuckDuckGo Instant Answer for structured info (no scraping needed).
    """
    try:
        url = f"https://api.duckduckgo.com/?q={quote_plus(company_name)}&format=json&no_redirect=1&no_html=1"
        with httpx.Client(timeout=8, follow_redirects=True) as c:
            r = c.get(url, headers={"Accept": "application/json"})
            if r.status_code == 200:
                d = r.json()
                result = {}
                if d.get("AbstractText"):
                    result["abstract"] = d["AbstractText"][:800]
                    result["abstract_source"] = d.get("AbstractSource", "")
                if d.get("Answer"):
                    result["answer"] = d["Answer"][:400]
                if d.get("Infobox", {}).get("content"):
                    kvs = []
                    for item in d["Infobox"]["content"][:15]:
                        kvs.append(f"{item.get('label','')}: {item.get('value','')}")
                    result["infobox"] = "; ".join(kvs)
                return result
    except Exception:
        pass
    return {}


# ── Page scraper ──────────────────────────────────────────────────────────────
def scrape_page(url: str) -> Optional[str]:
    for _ in range(2):
        try:
            with httpx.Client(headers=HEADERS, timeout=SCRAPE_TIMEOUT, follow_redirects=True) as c:
                r = c.get(url)
                if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
                    text = _clean_html(r.text)
                    if len(text) > 200:
                        return text
                elif r.status_code in (429, 503):
                    time.sleep(3)
        except Exception:
            pass
    return None


# ── Find official website URL ─────────────────────────────────────────────────
def find_official_url(company_name: str) -> Optional[str]:
    results = _ddg_text(
        f'"{company_name}" official website -linkedin -wikipedia -crunchbase -glassdoor',
        max_results=8,
    )
    time.sleep(DDG_DELAY)
    for r in results:
        href = r.get("href", "")
        if href and not _is_excluded(href):
            return _base_url(href)
    return None


# ── Website scraper ───────────────────────────────────────────────────────────
def scrape_website(company_name: str, base_url: Optional[str] = None) -> Dict[str, str]:
    if not base_url:
        base_url = find_official_url(company_name)
    if not base_url:
        return {}

    paths = [
        ("home",         ""),
        ("about",        "/about"),
        ("about-us",     "/about-us"),
        ("services",     "/services"),
        ("solutions",    "/solutions"),
        ("products",     "/products"),
        ("clients",      "/clients"),
        ("case-studies", "/case-studies"),
        ("news",         "/news"),
        ("press",        "/press"),
        ("leadership",   "/leadership"),
        ("team",         "/team"),
    ]

    pages: Dict[str, str] = {}
    for name, path in paths:
        if len(pages) >= MAX_PAGES:
            break
        text = scrape_page(base_url + path)
        if text and len(text) > 300:
            pages[name] = text
        time.sleep(0.3)

    return pages


# ── DuckDuckGo search facts ───────────────────────────────────────────────────
def search_facts(company_name: str) -> Dict[str, List[Dict]]:
    queries = {
        "general":    f"{company_name} company founded headquarters employees revenue sector industry",
        "funding":    f"{company_name} funding round acquisition investment valuation",
        "leadership": f"{company_name} CEO CFO CTO chief executive president leadership team",
        "clients":    f"{company_name} clients customers case study partnerships",
        "glassdoor":  f"{company_name} Glassdoor rating employee reviews",
    }

    facts: Dict[str, List[Dict]] = {}
    for key, query in queries.items():
        results = _ddg_text(query, max_results=4)
        if results:
            facts[key] = [
                {"title": r["title"], "body": r["body"][:300], "url": r.get("href", "")}
                for r in results
            ]
        time.sleep(DDG_DELAY)

    # News — best-effort
    news = _ddg_news(company_name, max_results=6)
    if news:
        facts["news"] = [
            {
                "date":   r.get("date", ""),
                "title":  r["title"],
                "body":   r.get("body", r.get("excerpt", ""))[:250],
                "source": r.get("source", ""),
            }
            for r in news
        ]
    time.sleep(DDG_DELAY)

    return facts


# ── yfinance public financials ────────────────────────────────────────────────
def get_public_financials(company_name: str) -> Dict[str, Any]:
    if not YF_OK:
        return {}

    candidates: List[str] = []

    # Try yfinance search directly first
    try:
        hits = yf.Search(company_name, max_results=5).quotes
        candidates = [h["symbol"] for h in hits if h.get("symbol")]
    except Exception:
        pass

    # Fallback: DDG text search for ticker
    if not candidates:
        results = _ddg_text(f"{company_name} stock ticker NYSE NASDAQ", max_results=4)
        full_text = " ".join(r["title"] + " " + r["body"] for r in results)
        bracketed = re.findall(r"\(([A-Z]{1,5})\)", full_text)
        if bracketed:
            candidates = bracketed
        time.sleep(DDG_DELAY)

    name_tokens = set(company_name.lower().split())
    for ticker in candidates[:8]:
        try:
            t    = yf.Ticker(ticker)
            info = t.info
            long_name  = (info.get("longName")  or "").lower()
            short_name = (info.get("shortName") or "").lower()
            combined   = long_name + " " + short_name
            if name_tokens & set(combined.split()):
                return {
                    "ticker":               ticker,
                    "exchange":             info.get("exchange", ""),
                    "revenue_usd":          info.get("totalRevenue"),
                    "revenue_growth_yoy":   info.get("revenueGrowth"),
                    "gross_margin":         info.get("grossMargins"),
                    "ebitda_usd":           info.get("ebitda"),
                    "market_cap_usd":       info.get("marketCap"),
                    "enterprise_value_usd": info.get("enterpriseValue"),
                    "ev_to_revenue":        info.get("enterpriseToRevenue"),
                    "ev_to_ebitda":         info.get("enterpriseToEbitda"),
                    "pe_ratio":             info.get("trailingPE"),
                    "employees":            info.get("fullTimeEmployees"),
                    "country":              info.get("country"),
                    "sector":               info.get("sector"),
                    "industry":             info.get("industry"),
                    "description":          (info.get("longBusinessSummary") or "")[:800],
                    "fiscal_year_end":      info.get("fiscalYearEnd"),
                }
        except Exception:
            continue

    return {}


# ── Master gather function ────────────────────────────────────────────────────
def gather_company_intelligence(
    company_name: str,
    url: Optional[str] = None,
    openai_key: Optional[str] = None,
    gemini_key: Optional[str] = None,
) -> Dict[str, Any]:
    # Keys fall back to config.py if not passed explicitly
    try:
        import config as _cfg
        openai_key = openai_key or _cfg.OPENAI_API_KEY
        gemini_key = gemini_key or _cfg.GOOGLE_API_KEY
    except ImportError:
        pass
    """
    Gather all available grounded data for a company.
    Returns dict with keys: company, url, website, wiki, ddg_instant,
                            search, financials, llm_research.
    """
    print(f"[scraper] -- Gathering intelligence: {company_name}")

    data: Dict[str, Any] = {
        "company":      company_name,
        "url":          url,
        "website":      {},
        "wiki":         {},
        "ddg_instant":  {},
        "search":       {},
        "financials":   {},
        "llm_research": {},
    }

    print("[scraper]   1/6 Wikipedia summary...")
    data["wiki"] = get_wikipedia_summary(company_name)

    print("[scraper]   2/6 DuckDuckGo instant answer...")
    data["ddg_instant"] = get_ddg_instant(company_name)

    print("[scraper]   3/6 Scraping website...")
    data["website"] = scrape_website(company_name, url)
    if data["website"] and not url:
        data["url"] = find_official_url(company_name)

    print("[scraper]   4/6 Searching web for facts...")
    data["search"] = search_facts(company_name)

    print("[scraper]   5/6 Fetching public financials...")
    data["financials"] = get_public_financials(company_name)

    # LLM research (OpenAI + Gemini) — runs if API keys are available
    oai = openai_key or os.environ.get("OPENAI_API_KEY", "")
    gem = gemini_key or os.environ.get("GOOGLE_API_KEY", "")
    if oai or gem:
        print("[scraper]   6/6 LLM research (OpenAI + Gemini)...")
        from llm_research import research_company
        data["llm_research"] = research_company(company_name, openai_key=oai, gemini_key=gem)
    else:
        print("[scraper]   6/6 LLM research skipped (no API keys set)")

    page_count    = len(data["website"])
    search_count  = sum(len(v) for v in data["search"].values())
    wiki_ok       = bool(data["wiki"].get("extract"))
    fin_ok        = bool(data["financials"])
    llm_sources   = data["llm_research"].get("sources_used", [])
    print(f"[scraper]   Done: {page_count} pages, {search_count} DDG, wiki={'yes' if wiki_ok else 'no'}, fin={'yes' if fin_ok else 'no'}, llm={llm_sources or 'none'}")

    return data


# ── M&A target discovery ──────────────────────────────────────────────────────
def discover_acquisition_targets(thesis: Dict[str, str]) -> List[Dict[str, str]]:
    """
    Search web for potential acquisition target names based on investment thesis.
    Returns raw search snippets for the LLM to extract company names from.
    Returns empty list if no useful results — caller must handle this gracefully.
    """
    sector = thesis.get("sector", "IT consulting services")
    geo    = thesis.get("geography", "")
    cap    = thesis.get("capability_gap", "")
    rev    = thesis.get("revenue_range", "$50M–$500M")

    queries = [
        f"top {sector} companies {geo} {cap} private mid-market acquisition target 2023 2024",
        f"{sector} {geo} firm {cap} employees revenue mid-market private equity",
        f"best {sector} firms {geo} {cap} {rev} revenue independent",
    ]

    raw: List[Dict] = []
    for q in queries:
        results = _ddg_text(q, max_results=8)
        if results:
            raw.extend(results)
        time.sleep(DDG_DELAY)

    return [
        {"title": r["title"], "body": r["body"][:300], "url": r.get("href", "")}
        for r in raw
    ]


# ── Formatting helpers for LLM prompts ───────────────────────────────────────
# ── Context budget constants ──────────────────────────────────────────────────
# Target ~4000 chars total so each agent prompt fits in 4096 tokens.
# The agent prompt text itself takes ~500 chars, schema ~200 chars.
# Remaining ~3300 chars for data context.
WIKI_BUDGET     = 800
INSTANT_BUDGET  = 400
WEBSITE_BUDGET  = 1200  # 2 pages × 600 each
SEARCH_BUDGET   = 1200  # 2 keys × 600 each (2 snippets × 300)
FIN_BUDGET      = 500


def format_wiki_context(wiki: Dict[str, str]) -> str:
    if not wiki or not wiki.get("extract"):
        return ""
    desc = wiki.get("description", "")
    extract = wiki["extract"][:WIKI_BUDGET]
    return f"[WIKIPEDIA] {wiki.get('title','')} — {desc}\n{extract}"


def format_ddg_instant_context(instant: Dict[str, str]) -> str:
    if not instant:
        return ""
    parts = []
    if instant.get("abstract"):
        parts.append(instant["abstract"][:300])
    if instant.get("infobox"):
        parts.append(f"Info: {instant['infobox'][:200]}")
    if not parts:
        return ""
    return "[DDG INSTANT] " + " | ".join(parts)


def format_website_context(website: Dict[str, str], max_pages: int = 2) -> str:
    if not website:
        return ""
    per_page = WEBSITE_BUDGET // max(max_pages, 1)
    parts = []
    for i, (page, text) in enumerate(website.items()):
        if i >= max_pages:
            break
        parts.append(f"[SITE:{page.upper()}] {text[:per_page]}")
    return "\n".join(parts)


def format_search_context(search: Dict[str, List[Dict]], keys: Optional[List[str]] = None) -> str:
    if not search:
        return ""
    keys = keys or ["general", "funding", "leadership", "clients"]
    # Use only keys that have data, then divide budget
    active_keys = [k for k in keys if search.get(k)]
    if not active_keys:
        return ""
    per_key = SEARCH_BUDGET // max(len(active_keys), 1)
    parts = []
    for key in active_keys:
        items = search.get(key, [])
        snippets = "\n".join(
            f"  {r.get('title','')}: {(r.get('body') or r.get('description',''))[:200]}"
            for r in items[:2]
        )
        parts.append(f"[{key.upper()} SEARCH]\n{snippets}"[:per_key])
    return "\n\n".join(parts)


def format_financials_context(fin: Dict[str, Any]) -> str:
    if not fin:
        return ""
    lines = []
    field_map = {
        "ticker": "Ticker", "revenue_usd": "Revenue",
        "revenue_growth_yoy": "Rev Growth", "gross_margin": "Gross Margin",
        "ebitda_usd": "EBITDA", "enterprise_value_usd": "EV",
        "ev_to_revenue": "EV/Rev", "employees": "Employees",
        "country": "Country", "sector": "Sector", "industry": "Industry",
    }
    for k, label in field_map.items():
        v = fin.get(k)
        if v is not None:
            lines.append(f"{label}: {v}")
    if fin.get("description"):
        lines.append(f"Desc: {fin['description'][:200]}")
    return "[YFINANCE] " + " | ".join(lines)


def build_full_context(scraped: Dict[str, Any], search_keys: Optional[List[str]] = None) -> str:
    """
    Build a concise, budget-capped context string from all sources.
    LLM research (OpenAI + Gemini) is placed FIRST as the highest-quality source.
    """
    parts = []

    # 1. LLM pre-research — highest quality, goes first
    llm_research = scraped.get("llm_research", {})
    llm_ctx = llm_research.get("context_str", "")
    if llm_ctx:
        parts.append(llm_ctx[:1200])

    # 2. Wikipedia — reliable structured summary
    wiki_ctx = format_wiki_context(scraped.get("wiki", {}))
    if wiki_ctx:
        parts.append(wiki_ctx)

    # 3. DuckDuckGo Instant Answer
    instant_ctx = format_ddg_instant_context(scraped.get("ddg_instant", {}))
    if instant_ctx:
        parts.append(instant_ctx)

    # 4. Website pages
    website_ctx = format_website_context(scraped.get("website", {}))
    if website_ctx:
        parts.append(website_ctx)

    # 5. DDG search snippets (agent-specific keys)
    search_ctx = format_search_context(scraped.get("search", {}), keys=search_keys)
    if search_ctx:
        parts.append(search_ctx)

    # 6. yfinance public financials
    fin_ctx = format_financials_context(scraped.get("financials", {}))
    if fin_ctx:
        parts.append(fin_ctx)

    if not parts:
        return "No data available from any source."

    return "\n\n---\n\n".join(parts)
