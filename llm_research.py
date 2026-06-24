"""
LLM Research layer — queries OpenAI, Google Gemini, xAI Grok, and DeepSeek for company intelligence.
Keys are read from config.py. Any one provider is sufficient.
When multiple providers are available, company research runs in parallel and results are merged.
"""

import json
import re
import threading
from typing import Dict, Any, Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from openai import OpenAI
    _OPENAI_OK = True
except ImportError:
    _OPENAI_OK = False

try:
    from google import genai as _google_genai
    _GEMINI_OK = True
except ImportError:
    _GEMINI_OK = False

_GROK_BASE_URL   = "https://api.x.ai/v1"
_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
_DEEPSEEK_MODEL  = "deepseek-ai/deepseek-v4-pro"


def _try_parse_json(text: str) -> Optional[Dict]:
    """
    Parse JSON with graceful recovery for truncated responses.
    Tries direct parse first, then strips markdown fences, then attempts
    recovery by truncating at the last valid closing brace.
    """
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Recovery: find the last top-level closing brace and try to parse up to it
    last_brace = cleaned.rfind("}")
    if last_brace > 0:
        try:
            return json.loads(cleaned[: last_brace + 1])
        except json.JSONDecodeError:
            pass
    return None

# ── In-memory cache (keyed by company + prompt type) ─────────────────────────
_RESEARCH_CACHE: Dict[str, Dict] = {}
_CACHE_LOCK = threading.Lock()


def _cache_key(company: str, kind: str) -> str:
    return f"{company.lower().strip()}::{kind}"


# ── Prompts ───────────────────────────────────────────────────────────────────
_COMPANY_PROMPT = """\
Return JSON only. Company: "{company}"
Keys (null if unknown):
hq, founded, employees, revenue, ebitda_margin,
sector, company_type(Public/Private/PE-backed/VC-backed/Subsidiary/Joint Venture),
business_model(one sentence),
ownership(PE firm with fund vintage if known, or exchange+ticker if public, else null),
services(list<=8), clients(list<=8),
geographies(list<=6 key regions),
executives(list<=5 of {{name,title}}),
partnerships(list<=8 key tech or business partners),
recent_acquisitions(list<=5 of {{name,year,value,rationale}}),
skills_tech(list<=8 primary technologies or certifications),
competitors(list<=5 direct competitors by name),
growth_signals(list<=3 notable growth indicators e.g. revenue CAGR new markets headcount growth),
key_client_verticals(list<=4 industry verticals most served),
glassdoor_rating(X.X or null), glassdoor_reviews(integer or null),
valuation_or_ev(string with source or null),
pe_details({{firm,fund_vintage,acquisition_year,exit_timeline_hint}} or null),
certifications(list<=5 key certifications or awards),
news(list<=6 recent news headlines with year)"""

_DEAL_INTEL_PROMPT = """\
Return JSON only. M&A deal intelligence for "{company}".
Keys (null if unknown):
strategic_rationale(2 sentences on why this company is an attractive M&A target),
ownership_pressure(evidence of PE exit pressure or founder succession, or null),
comparable_transactions(list<=4 of {{name,year,ev_revenue_multiple,buyer}} similar closed deals in same sector),
key_deal_risks(list<=4 integration or deal execution risks),
integration_complexity(Low/Medium/High),
integration_complexity_basis(one sentence explanation),
estimated_ev_revenue_multiple(string e.g. "1.5x-2.5x"),
deal_structure_recommendation(Full acquisition/Minority stake/Joint venture/Partnership),
strategic_fit_score(integer 1-10 for Accenture as acquirer),
strategic_fit_rationale(one sentence)"""

_DISCOVERY_PROMPT = """\
Return JSON only. Find acquisition targets for "{acquirer}".
Thesis: sector={sector}, geography={geography}, capability={capability_gap}, revenue={revenue_range}
Keys: targets(list<=8 of {{
  name, hq, revenue, employees,
  company_type(Private/PE-backed/Public),
  ownership(PE firm or ticker, else null),
  tech_focus(list<=3 primary technologies),
  geography_focus(list<=2 key markets),
  founded(year or null),
  glassdoor_rating(X.X or null),
  rationale(one sentence)
}})
Only real companies you are confident exist."""


# ── Provider callers ──────────────────────────────────────────────────────────
def _call_openai(prompt: str, api_key: str, model: str = "gpt-4o-mini",
                 max_tokens: int = 2000) -> Optional[Dict]:
    if not _OPENAI_OK or not api_key:
        return None
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        result = _try_parse_json(resp.choices[0].message.content or "")
        if result is None:
            print("[llm_research] OpenAI: could not parse JSON response")
        return result
    except Exception as e:
        print(f"[llm_research] OpenAI error: {e}")
        return None


def _call_gemini(prompt: str, api_key: str, model: str = "gemini-2.0-flash",
                 max_tokens: int = 2000) -> Optional[Dict]:
    if not _GEMINI_OK or not api_key:
        return None
    try:
        client = _google_genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=_google_genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=max_tokens,
                temperature=0,
            ),
        )
        result = _try_parse_json(resp.text or "")
        if result is None:
            print("[llm_research] Gemini: could not parse JSON response")
        return result
    except Exception as e:
        print(f"[llm_research] Gemini error: {e}")
        return None


def _call_grok(prompt: str, api_key: str, model: str = "grok-3-mini",
               max_tokens: int = 2000) -> Optional[Dict]:
    if not _OPENAI_OK or not api_key:
        return None
    try:
        client = OpenAI(api_key=api_key, base_url=_GROK_BASE_URL)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        result = _try_parse_json(resp.choices[0].message.content or "")
        if result is None:
            print("[llm_research] Grok: could not parse JSON response")
        return result
    except Exception as e:
        print(f"[llm_research] Grok error: {e}")
        return None


def _call_deepseek(prompt: str, api_key: str, max_tokens: int = 2000) -> Optional[Dict]:
    """DeepSeek-V4-Pro via NVIDIA NIM — OpenAI-compatible, thinking disabled."""
    if not _OPENAI_OK or not api_key:
        return None
    try:
        client = OpenAI(api_key=api_key, base_url=_NVIDIA_BASE_URL)
        resp = client.chat.completions.create(
            model=_DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            top_p=0.95,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            extra_body={"chat_template_kwargs": {"thinking": False}},
        )
        result = _try_parse_json(resp.choices[0].message.content or "")
        if result is None:
            print("[llm_research] DeepSeek: could not parse JSON response")
        return result
    except Exception as e:
        print(f"[llm_research] DeepSeek error: {e}")
        return None


def _call_any(prompt: str, openai_key: str, gemini_key: str,
              grok_key: str = "", nvidia_key: str = "",
              max_tokens: int = 2000) -> Tuple[Optional[Dict], Optional[str]]:
    """Sequential fallback: OpenAI → Grok → DeepSeek → Gemini."""
    for key, name, fn in [
        (openai_key, "OpenAI",   lambda k=openai_key: _call_openai(prompt, k, max_tokens=max_tokens)),
        (grok_key,   "Grok",     lambda k=grok_key:   _call_grok(prompt, k, max_tokens=max_tokens)),
        (nvidia_key, "DeepSeek", lambda k=nvidia_key: _call_deepseek(prompt, k, max_tokens=max_tokens)),
        (gemini_key, "Gemini",   lambda k=gemini_key: _call_gemini(prompt, k, max_tokens=max_tokens)),
    ]:
        if key:
            result = fn()
            if result:
                return result, name
    return None, None


def _call_all_parallel(
    prompt: str,
    openai_key: str, gemini_key: str,
    grok_key: str = "", nvidia_key: str = "",
    max_tokens: int = 2000,
) -> List[Tuple[Dict, str]]:
    """Query all available providers concurrently. Returns [(result, source), ...]."""
    tasks = [
        (name, fn)
        for name, key, fn in [
            ("OpenAI",   openai_key,  lambda k=openai_key:  _call_openai(prompt, k, max_tokens=max_tokens)),
            ("Grok",     grok_key,    lambda k=grok_key:    _call_grok(prompt, k, max_tokens=max_tokens)),
            ("DeepSeek", nvidia_key,  lambda k=nvidia_key:  _call_deepseek(prompt, k, max_tokens=max_tokens)),
            ("Gemini",   gemini_key,  lambda k=gemini_key:  _call_gemini(prompt, k, max_tokens=max_tokens)),
        ]
        if key
    ]
    if not tasks:
        return []

    results: List[Tuple[Dict, str]] = []
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        future_map = {pool.submit(fn): name for name, fn in tasks}
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                res = future.result()
                if res:
                    results.append((res, name))
            except Exception as e:
                print(f"[llm_research] {name} parallel call failed: {e}")
    return results


def _deep_merge(primary: Dict, secondaries: List[Dict]) -> Dict:
    """
    Fill null/empty scalar fields from secondaries.
    Extend short lists with unique items from richer secondary results.
    """
    result = dict(primary)
    for sec in secondaries:
        for k, v in sec.items():
            curr = result.get(k)
            if curr is None or curr == "":
                if v is not None and v != "":
                    result[k] = v
            elif isinstance(curr, list) and isinstance(v, list) and v:
                seen = set()
                for item in curr:
                    seen.add(
                        item.get("name", "").lower() if isinstance(item, dict)
                        else str(item).lower()
                    )
                for item in v:
                    item_key = (
                        item.get("name", "").lower() if isinstance(item, dict)
                        else str(item).lower()
                    )
                    if item_key and item_key not in seen and len(curr) < 10:
                        curr.append(item)
                        seen.add(item_key)
                result[k] = curr
    return result


# ── Shared utilities ──────────────────────────────────────────────────────────
def _safe_list(v: Any, limit: int = 8) -> List:
    if isinstance(v, list):
        return [str(x) for x in v[:limit] if x]
    return []


# ── Public API ────────────────────────────────────────────────────────────────
def research_company(
    company_name: str,
    openai_key: str = "",
    gemini_key: str = "",
    grok_key: str = "",
    nvidia_key: str = "",
) -> Dict[str, Any]:
    """
    Query available LLMs (parallel when multiple) for company facts.
    Results from all providers are merged to maximise data coverage.
    """
    if not openai_key and not gemini_key and not grok_key and not nvidia_key:
        return {}

    cache_k = _cache_key(company_name, "company")
    with _CACHE_LOCK:
        if cache_k in _RESEARCH_CACHE:
            print(f"[llm_research] Cache hit: {company_name} (company)")
            return _RESEARCH_CACHE[cache_k]

    prompt = _COMPANY_PROMPT.format(company=company_name)
    provider_count = sum(1 for k in [openai_key, grok_key, nvidia_key, gemini_key] if k)

    sources_used: List[str] = []
    if provider_count > 1:
        all_results = _call_all_parallel(prompt, openai_key, gemini_key, grok_key, nvidia_key)
        if not all_results:
            return {}
        # Prefer OpenAI as primary when available
        order = {"OpenAI": 0, "Grok": 1, "DeepSeek": 2, "Gemini": 3}
        all_results.sort(key=lambda x: order.get(x[1], 99))
        raw = all_results[0][0]
        sources_used = [s for _, s in all_results]
        if len(all_results) > 1:
            raw = _deep_merge(raw, [r for r, _ in all_results[1:]])
    else:
        raw, primary_src = _call_any(prompt, openai_key, gemini_key, grok_key, nvidia_key)
        if not raw:
            return {}
        sources_used = [primary_src]

    def _acq_list(v: Any) -> List[Dict]:
        if not isinstance(v, list):
            return []
        return [
            {
                "name":      i.get("name", ""),
                "year":      i.get("year", ""),
                "value":     i.get("value", ""),
                "rationale": i.get("rationale", ""),
            }
            for i in v[:5] if isinstance(i, dict) and i.get("name")
        ]

    def _exec_list(v: Any) -> List[Dict]:
        if not isinstance(v, list):
            return []
        return [
            {"name": e.get("name", ""), "title": e.get("title", "")}
            for e in v[:5] if isinstance(e, dict)
        ]

    def _pe_details(v: Any) -> Optional[Dict]:
        if not isinstance(v, dict):
            return None
        return {k: v.get(k, "") for k in ("firm", "fund_vintage", "acquisition_year", "exit_timeline_hint")}

    collated = {
        "hq":                   raw.get("hq"),
        "founded":              raw.get("founded"),
        "employees":            raw.get("employees"),
        "revenue":              raw.get("revenue"),
        "ebitda_margin":        raw.get("ebitda_margin"),
        "sector":               raw.get("sector"),
        "company_type":         raw.get("company_type"),
        "business_model":       raw.get("business_model"),
        "ownership":            raw.get("ownership"),
        "services":             _safe_list(raw.get("services"), 8),
        "clients":              _safe_list(raw.get("clients"), 8),
        "geographies":          _safe_list(raw.get("geographies"), 6),
        "executives":           _exec_list(raw.get("executives")),
        "partnerships":         _safe_list(raw.get("partnerships"), 8),
        "recent_acquisitions":  _acq_list(raw.get("recent_acquisitions")),
        "skills_tech":          _safe_list(raw.get("skills_tech"), 8),
        "competitors":          _safe_list(raw.get("competitors"), 5),
        "growth_signals":       _safe_list(raw.get("growth_signals"), 3),
        "key_client_verticals": _safe_list(raw.get("key_client_verticals"), 4),
        "glassdoor_rating":     raw.get("glassdoor_rating"),
        "glassdoor_reviews":    raw.get("glassdoor_reviews"),
        "valuation_or_ev":      raw.get("valuation_or_ev"),
        "pe_details":           _pe_details(raw.get("pe_details")),
        "certifications":       _safe_list(raw.get("certifications"), 5),
        "news":                 _safe_list(raw.get("news"), 6),
    }

    lines = [f"[{'/'.join(s.upper() for s in sources_used)} RESEARCH]"]

    for k, label in [
        ("hq", "HQ"), ("founded", "Founded"), ("employees", "Employees"),
        ("revenue", "Revenue"), ("ebitda_margin", "EBITDA Margin"),
        ("sector", "Sector"), ("company_type", "Type"),
        ("business_model", "Business Model"), ("ownership", "Ownership"),
        ("glassdoor_rating", "Glassdoor"), ("glassdoor_reviews", "Reviews"),
        ("valuation_or_ev", "Valuation/EV"),
    ]:
        if collated.get(k):
            lines.append(f"  {label}: {collated[k]}")

    for k, label in [
        ("services", "Services"), ("clients", "Clients"), ("geographies", "Geographies"),
        ("partnerships", "Partners"), ("skills_tech", "Tech/Skills"),
        ("competitors", "Competitors"), ("key_client_verticals", "Client Verticals"),
        ("certifications", "Certifications"),
    ]:
        if collated[k]:
            lines.append(f"  {label}: {', '.join(collated[k])}")

    if collated["growth_signals"]:
        lines.append(f"  Growth: {' | '.join(collated['growth_signals'])}")
    if collated["recent_acquisitions"]:
        acq_str = "; ".join(f"{a['name']} ({a['year']})" for a in collated["recent_acquisitions"])
        lines.append(f"  Acquisitions: {acq_str}")
    if collated["executives"]:
        execs = ", ".join(f"{e['name']} ({e['title']})" for e in collated["executives"])
        lines.append(f"  Executives: {execs}")
    if collated["pe_details"] and collated["pe_details"].get("firm"):
        pe = collated["pe_details"]
        lines.append(
            f"  PE Sponsor: {pe['firm']} | Vintage: {pe['fund_vintage']}"
            f" | Acq Year: {pe['acquisition_year']} | Exit: {pe['exit_timeline_hint']}"
        )
    if collated["news"]:
        lines.append(f"  News: {' | '.join(collated['news'])}")

    result = {
        "collated":     collated,
        "sources_used": sources_used,
        "context_str":  "\n".join(lines),
    }

    with _CACHE_LOCK:
        _RESEARCH_CACHE[cache_k] = result

    return result


def research_deal_intel(
    company_name: str,
    openai_key: str = "",
    gemini_key: str = "",
    grok_key: str = "",
    nvidia_key: str = "",
) -> Dict[str, Any]:
    """
    Query LLM for M&A-specific intelligence: ownership pressure, comparable
    transactions, deal structure recommendation, and strategic fit score.
    """
    if not openai_key and not gemini_key and not grok_key and not nvidia_key:
        return {}

    cache_k = _cache_key(company_name, "deal_intel")
    with _CACHE_LOCK:
        if cache_k in _RESEARCH_CACHE:
            print(f"[llm_research] Cache hit: {company_name} (deal_intel)")
            return _RESEARCH_CACHE[cache_k]

    prompt = _DEAL_INTEL_PROMPT.format(company=company_name)
    raw, source = _call_any(prompt, openai_key, gemini_key, grok_key, nvidia_key, max_tokens=1500)
    if not raw:
        return {}

    def _comp_tx(v: Any) -> List[Dict]:
        if not isinstance(v, list):
            return []
        return [
            {
                "name":               i.get("name", ""),
                "year":               i.get("year", ""),
                "ev_revenue_multiple": i.get("ev_revenue_multiple", ""),
                "buyer":              i.get("buyer", ""),
            }
            for i in v[:4] if isinstance(i, dict)
        ]

    collated = {
        "strategic_rationale":           raw.get("strategic_rationale"),
        "ownership_pressure":            raw.get("ownership_pressure"),
        "comparable_transactions":       _comp_tx(raw.get("comparable_transactions")),
        "key_deal_risks":                _safe_list(raw.get("key_deal_risks"), 4),
        "integration_complexity":        raw.get("integration_complexity"),
        "integration_complexity_basis":  raw.get("integration_complexity_basis"),
        "estimated_ev_revenue_multiple": raw.get("estimated_ev_revenue_multiple"),
        "deal_structure_recommendation": raw.get("deal_structure_recommendation"),
        "strategic_fit_score":           raw.get("strategic_fit_score"),
        "strategic_fit_rationale":       raw.get("strategic_fit_rationale"),
    }

    lines = [f"[{source.upper()} DEAL INTEL]"]
    if collated.get("strategic_rationale"):
        lines.append(f"  M&A Rationale: {collated['strategic_rationale']}")
    if collated.get("ownership_pressure"):
        lines.append(f"  Ownership Pressure: {collated['ownership_pressure']}")
    if collated.get("estimated_ev_revenue_multiple"):
        lines.append(f"  EV/Rev Multiple: {collated['estimated_ev_revenue_multiple']}")
    if collated.get("deal_structure_recommendation"):
        lines.append(f"  Deal Structure: {collated['deal_structure_recommendation']}")
    if collated.get("integration_complexity"):
        lines.append(
            f"  Integration: {collated['integration_complexity']}"
            f" — {collated.get('integration_complexity_basis', '')}"
        )
    if collated.get("strategic_fit_score"):
        lines.append(
            f"  Fit Score: {collated['strategic_fit_score']}/10"
            f" — {collated.get('strategic_fit_rationale', '')}"
        )
    if collated.get("comparable_transactions"):
        comps = "; ".join(
            f"{c['name']} ({c.get('year','')}, {c.get('ev_revenue_multiple','')}x, acq by {c.get('buyer','')})"
            for c in collated["comparable_transactions"] if c.get("name")
        )
        if comps:
            lines.append(f"  Comparable Deals: {comps}")
    if collated.get("key_deal_risks"):
        lines.append(f"  Deal Risks: {' | '.join(collated['key_deal_risks'])}")

    result = {
        "collated":     collated,
        "sources_used": [source],
        "context_str":  "\n".join(lines),
    }

    with _CACHE_LOCK:
        _RESEARCH_CACHE[cache_k] = result

    return result


def research_synergy_model(
    acquirer: str,
    target: str,
    acq_llm: Dict,
    tgt_llm: Dict,
    tgt_deal_intel: Dict,
    openai_key: str = "",
    gemini_key: str = "",
    grok_key: str = "",
    nvidia_key: str = "",
) -> Dict[str, Any]:
    """
    Ask a capable external LLM (DeepSeek / OpenAI / Gemini) to compute a full
    quantified synergy model for the acquirer ↔ target pair.
    Returns a dict whose structure mirrors SynergyModelOutput.
    """
    if not openai_key and not gemini_key and not grok_key and not nvidia_key:
        return {}

    cache_k = _cache_key(f"{acquirer}::{target}", "synergy")
    with _CACHE_LOCK:
        if cache_k in _RESEARCH_CACHE:
            print(f"[llm_research] Cache hit: synergy {acquirer}/{target}")
            return _RESEARCH_CACHE[cache_k]

    # Build concise context blocks from already-computed LLM research
    acq_ctx = (acq_llm or {}).get("context_str", "") or ""
    tgt_ctx = (tgt_llm or {}).get("context_str", "") or ""
    di_ctx  = (tgt_deal_intel or {}).get("context_str", "") or ""

    acq_lc = (acq_llm or {}).get("collated", {})
    tgt_lc = (tgt_llm or {}).get("collated", {})
    di_lc  = (tgt_deal_intel or {}).get("collated", {})

    prompt = f"""\
Return JSON only. You are a senior V&A M&A analyst. Compute a rigorous synergy model.

ACQUIRER: {acquirer}
{acq_ctx[:600]}

TARGET: {target}
{tgt_ctx[:700]}

DEAL INTELLIGENCE FOR TARGET:
{di_ctx[:500]}

SECTOR BENCHMARKS TO USE:
- IT services EV/Rev: 1.5x–3.0x | SaaS: 4x–8x | Healthcare: 2x–5x | Consulting: 1x–2.5x
- Revenue synergy (cross-sell): 3-5% of smaller entity's annual revenue, Year 2-3
- Cost synergy (G&A): 10-15% of duplicate back-office headcount × $85K fully loaded
- Platform/tech overlap: $2M–$8M for <500-person targets, $5M–$20M for 500-2000
- Use employee count × $120K as revenue proxy for IT services when revenue unknown
- Minimum 2 synergy_items per deal; confidence=Low when using benchmarks

REQUIRED JSON KEYS:
{{
  "headline_rationale": "one sentence on why this deal makes strategic sense",
  "deal_structure": "Full acquisition | Strategic minority stake | Joint venture | Partnership agreement",
  "integration_complexity": "Low | Medium | High — one sentence reason",
  "suggested_ev_revenue_multiple": "e.g. 1.5x-2.5x (sector benchmark)",
  "capability_gaps_filled": ["list", "<=3 items"],
  "client_overlap": ["shared client names if any"],
  "geography_overlap": ["shared markets if any"],
  "key_assumptions": ["max 4 assumptions used"],
  "synergy_items": [
    {{
      "synergy_type": "Revenue — cross-sell | Cost — G&A consolidation | etc.",
      "basis": "factual basis in <=20 words",
      "estimated_value_low_usd_m": <number>,
      "estimated_value_high_usd_m": <number>,
      "confidence_level": "Low | Medium | High",
      "year_realizable": <1|2|3>
    }}
  ],
  "total_low_usd_m": <sum of low values>,
  "total_high_usd_m": <sum of high values>
}}"""

    raw, source = _call_any(prompt, openai_key, gemini_key, grok_key, nvidia_key, max_tokens=2000)
    if not raw:
        return {}

    # Normalise synergy_items
    items = []
    for it in (raw.get("synergy_items") or []):
        if not isinstance(it, dict):
            continue
        items.append({
            "synergy_type":              str(it.get("synergy_type") or ""),
            "basis":                     str(it.get("basis") or ""),
            "estimated_value_low_usd_m": float(it.get("estimated_value_low_usd_m") or 0),
            "estimated_value_high_usd_m": float(it.get("estimated_value_high_usd_m") or 0),
            "confidence_level":          str(it.get("confidence_level") or "Low"),
            "year_realizable":           int(it.get("year_realizable") or 2),
        })

    total_low  = float(raw.get("total_low_usd_m")  or sum(i["estimated_value_low_usd_m"]  for i in items))
    total_high = float(raw.get("total_high_usd_m") or sum(i["estimated_value_high_usd_m"] for i in items))

    collated = {
        "headline_rationale":          str(raw.get("headline_rationale") or ""),
        "deal_structure":              str(raw.get("deal_structure") or ""),
        "integration_complexity":      str(raw.get("integration_complexity") or ""),
        "suggested_ev_revenue_multiple": str(raw.get("suggested_ev_revenue_multiple") or ""),
        "capability_gaps_filled":      _safe_list(raw.get("capability_gaps_filled"), 3),
        "client_overlap":              _safe_list(raw.get("client_overlap"), 8),
        "geography_overlap":           _safe_list(raw.get("geography_overlap"), 6),
        "key_assumptions":             _safe_list(raw.get("key_assumptions"), 4),
        "synergy_items":               items,
        "total_low_usd_m":             total_low,
        "total_high_usd_m":            total_high,
    }

    result = {
        "collated":     collated,
        "sources_used": [source],
    }

    with _CACHE_LOCK:
        _RESEARCH_CACHE[cache_k] = result

    print(f"[llm_research] Synergy model ({source}): {target} — ${total_low}M–${total_high}M across {len(items)} items")
    return result


def research_discovery_targets(
    acquirer: str,
    thesis: Dict[str, str],
    openai_key: str = "",
    gemini_key: str = "",
    grok_key: str = "",
    nvidia_key: str = "",
) -> Dict[str, Any]:
    """Ask one LLM for acquisition target suggestions (up to 8 targets)."""
    if not openai_key and not gemini_key and not grok_key and not nvidia_key:
        return {}

    prompt = _DISCOVERY_PROMPT.format(
        acquirer=acquirer,
        sector=thesis.get("sector", ""),
        geography=thesis.get("geography", ""),
        capability_gap=thesis.get("capability_gap", ""),
        revenue_range=thesis.get("revenue_range", "$50M-$500M"),
    )
    raw, source = _call_any(prompt, openai_key, gemini_key, grok_key, nvidia_key, max_tokens=2000)
    if not raw:
        return {}

    targets = []
    for t in (raw.get("targets") or [])[:8]:
        if isinstance(t, dict) and t.get("name"):
            targets.append({
                "name":             t.get("name", ""),
                "hq":               t.get("hq", ""),
                "revenue":          t.get("revenue", ""),
                "employees":        t.get("employees", ""),
                "company_type":     t.get("company_type", ""),
                "ownership":        t.get("ownership", ""),
                "tech_focus":       t.get("tech_focus", []) if isinstance(t.get("tech_focus"), list) else [],
                "geography_focus":  t.get("geography_focus", []) if isinstance(t.get("geography_focus"), list) else [],
                "founded":          t.get("founded", ""),
                "glassdoor_rating": t.get("glassdoor_rating", ""),
                "rationale":        t.get("rationale", ""),
            })

    lines = [f"[{source.upper()} DISCOVERY]"]
    for t in targets:
        tech = ", ".join(t["tech_focus"]) if t["tech_focus"] else ""
        geo  = ", ".join(t["geography_focus"]) if t["geography_focus"] else t["hq"]
        own  = f" | Owner: {t['ownership']}" if t["ownership"] else ""
        emp  = f" | Emp: {t['employees']}" if t["employees"] else ""
        gd   = f" | GD: {t['glassdoor_rating']}" if t.get("glassdoor_rating") else ""
        lines.append(
            f"  {t['name']} | HQ: {t['hq']} | Rev: {t['revenue']}{emp}"
            f" | Type: {t['company_type']}{own}{gd}"
            f" | Tech: {tech} | Markets: {geo}"
            f" | {t['rationale']}"
        )

    return {
        "collated":     {"targets": targets},
        "sources_used": [source],
        "context_str":  "\n".join(lines),
        "target_names": [t["name"] for t in targets],
    }
